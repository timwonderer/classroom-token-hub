from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, Issue, IssueCategory, Student
from app.utils.opaque_refs import make_opaque_ref


def test_teacher_must_close_issue_after_final_review(client):
    teacher = make_admin("teacher_issue_lifecycle", "secret")
    student = Student(first_name="Casey", last_initial="L", block="A", salt=b"salt")
    category = IssueCategory(
        name="Lifecycle Category",
        category_type="general",
        is_active=True,
    )
    db.session.add_all([teacher, student, category])
    db.session.flush()

    issue = Issue(
        student_id=student.id,
        student_first_name=student.first_name,
        student_last_initial=student.last_initial,
        opaque_student_reference="opaque-student-1",
        teacher_id=teacher.id,
        join_code="JOINLIFE1",
        class_label="Block A",
        category_id=category.id,
        issue_type="general",
        student_explanation="Balance looked incorrect after store purchase.",
        status=Issue.STATUS_TEACHER_REVIEW,
    )
    db.session.add(issue)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    issue_ref = make_opaque_ref("issue", issue.id)
    resolve_resp = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={
            "action_type": "manual_adjustment",
            "teacher_notes": "Reviewed logs and posted classroom correction separately.",
        },
        follow_redirects=False,
    )
    assert resolve_resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_TEACHER_FINAL_REVIEW
    assert issue.closed_at is None

    close_resp = client.post(
        f"/admin/issues/{issue_ref}/close",
        data={"resolution_summary": "Ledger verified and student was informed."},
        follow_redirects=False,
    )
    assert close_resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_CLOSED
    assert issue.closed_at is not None
    assert issue.closed_by_type == "teacher"
