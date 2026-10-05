"""A teacher's own support ticket never enters the teacher's student-issue queue.

Regression for a production defect: a ticket a teacher filed through Help &
Support (a direct report to system support, DOM-SUP-001 §X) was marked
DEV_RESOLVED by sysadmin and then appeared in the same teacher's
"Student Issues" queue, among real student tickets, as something to review.
The queue and the review actions select by class only; they now also exclude
tickets authored by a teacher seat.
"""
from __future__ import annotations

from app.models import Issue
from app.utils.opaque_refs import make_opaque_ref
from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.support_domain import seed_support_issue_categories, submit_support_ticket

TEACHER_TITLE = "TEACHER-DIRECT-TICKET-MARKER"
STUDENT_TEXT = "STUDENT-TICKET-EXPLANATION-MARKER"


def _teacher_ticket_resolved_by_sysadmin(client, app):
    """The teacher files a ticket; sysadmin resolves it; the teacher signs back in."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    seed_support_issue_categories()
    response = submit_support_ticket(
        client, issue_category="general", title=TEACHER_TITLE, description="It's broken",
    )
    assert response.status_code == 200
    issue = Issue.query.filter_by(title=TEACHER_TITLE).one()

    with client.session_transaction() as sess:
        sess.clear()
    sysadmin = create_sysadmin(username="teacher_ticket_operator")
    login_sysadmin(client, "teacher_ticket_operator", sysadmin.id)
    response = client.post(
        f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}/update",
        data={"status": Issue.STATUS_DEV_RESOLVED, "admin_notes": "fixed"},
    )
    assert response.status_code == 302
    issue = Issue.query.filter_by(id=issue.id).one()
    assert issue.status == Issue.STATUS_DEV_RESOLVED

    with client.session_transaction() as sess:
        sess.clear()
    login_teacher(client, classroom)
    return classroom, issue


def test_dev_resolved_teacher_ticket_is_absent_from_student_issue_queue(client, app):
    classroom, issue = _teacher_ticket_resolved_by_sysadmin(client, app)

    response = client.get("/admin/issues")

    assert response.status_code == 200
    assert TEACHER_TITLE.encode() not in response.data
    assert b"Dev Resolved" not in response.data
    assert issue.class_public_id == classroom.economy.class_public_id, (
        "the ticket is in the teacher's own class, so only authorship excludes it"
    )


def test_teacher_ticket_cannot_be_opened_or_acted_on_as_a_student_issue(client, app):
    _, issue = _teacher_ticket_resolved_by_sysadmin(client, app)
    ref = make_opaque_ref("issue", issue.id)

    assert client.get(f"/admin/issues/{ref}").status_code == 404
    assert client.post(f"/admin/issues/{ref}/resolve", data={"action_type": "deny_issue"}).status_code == 404
    assert client.post(f"/admin/issues/{ref}/escalate", data={"escalation_reason": "x"}).status_code == 404
    assert client.post(f"/admin/issues/{ref}/close", data={"resolution_summary": "x"}).status_code == 404
    assert Issue.query.filter_by(id=issue.id).one().status == Issue.STATUS_DEV_RESOLVED


def test_student_ticket_still_appears_next_to_teacher_ticket(client, app):
    """The filter removes only teacher-authored tickets, not the queue's real content."""
    classroom, issue = _teacher_ticket_resolved_by_sysadmin(client, app)
    from app.extensions import db
    from app.models import IssueCategory

    student = classroom.students[0]
    category = IssueCategory.query.order_by(IssueCategory.id.asc()).first()
    student_issue = Issue(
        actor_public_id=student.seat.public_id,
        class_public_id=classroom.economy.class_public_id,
        category_id=category.id,
        issue_type="general",
        student_explanation=STUDENT_TEXT,
        status=Issue.STATUS_DEV_RESOLVED,
    )
    from app.feats.base import FEATContext
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="teacher_ticket_queue:student"):
        db.session.add(student_issue)
        db.session.flush()
    db.session.commit()

    body = client.get("/admin/issues").get_data(as_text=True)

    assert STUDENT_TEXT in body
    assert TEACHER_TITLE not in body
    assert client.get(f"/admin/issues/{make_opaque_ref('issue', student_issue.id)}").status_code == 200
