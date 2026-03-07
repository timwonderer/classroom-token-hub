from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db
from app.models import (
    Admin,
    Issue,
    IssueCategory,
    IssueResolutionAction,
    Student,
    SystemAdmin,
    Transaction,
    TransactionStatus,
)
from app.utils.opaque_refs import make_opaque_ref


def test_sysadmin_resolve_issue_issues_bug_reward_transaction(client):
    teacher = Admin(username="teacher_issue_reward", totp_secret="secret")
    sysadmin = SystemAdmin(username="sysadmin_issue_reward", totp_secret="secret")
    student = Student(first_name="Bug", last_initial="R", block="A", salt=b"salt")
    category = IssueCategory(
        name="Bug Report Category",
        category_type="general",
        is_active=True,
    )
    db.session.add_all([teacher, sysadmin, student, category])
    db.session.flush()

    issue = Issue(
        student_id=student.id,
        student_first_name=student.first_name,
        student_last_initial=student.last_initial,
        opaque_student_reference="opaque-ref-123",
        teacher_id=teacher.id,
        join_code="JOINBUG123",
        class_label="Block A",
        category_id=category.id,
        issue_type="general",
        student_explanation="Found a reproducible bug in the app.",
        student_expected_outcome="Expected behavior should work.",
        status=Issue.STATUS_ESCALATED_TO_DEV,
        eligible_for_reward=True,
    )
    db.session.add(issue)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    issue_ref = make_opaque_ref("issue", issue.id)
    resp = client.post(
        f"/sysadmin/issues/{issue_ref}/resolve",
        data={
            "resolution_note": "Confirmed and fixed.",
            "eligible_for_reward": "on",
            "reward_amount": "4.50",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_DEV_RESOLVED
    assert issue.eligible_for_reward is True
    assert issue.sysadmin_id == sysadmin.id
    assert issue.sysadmin_resolved_at is not None

    reward_tx = Transaction.query.filter(
        Transaction.student_id == student.id,
        Transaction.teacher_id == teacher.id,
        Transaction.join_code == "JOINBUG123",
        Transaction.type == "bug_reward",
    ).first()
    assert reward_tx is not None
    assert reward_tx.amount == Decimal("4.50")
    assert reward_tx.account_type == "checking"
    assert reward_tx.status == TransactionStatus.PENDING
    assert "Issue" in (reward_tx.description or "")

    reward_action = IssueResolutionAction.query.filter_by(
        issue_id=issue.id,
        action_type="bug_reward_issued",
    ).first()
    assert reward_action is not None
    assert reward_action.related_transaction_id == reward_tx.id
