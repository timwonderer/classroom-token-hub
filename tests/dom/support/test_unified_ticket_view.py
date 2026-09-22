"""The sysadmin ticket surface is one route/template regardless of origin.

Previously /user-reports/<ref> and /issues/<ref> were two separate routes and
templates over the same Issue model -- sysadmin sees only opaque public ids
either way, so there was no principled reason for a teacher-submitted,
never-escalated ticket and a student-escalated one to render differently.
Consolidated into sysadmin.view_issue() / sysadmin_view_issue.html; the action
panel now varies by the ticket's current lifecycle position, not by which of
the two old doors it came in through.

Also covers the UTC/class-time display toggle added to that unified surface
(INV-ARC-015 SS X.2): a presentation-only lens, resolved server-side, that
never grants sysadmin canonical class context and never touches the stored
Issue/correlation-pack data.
"""
from __future__ import annotations

from app.extensions import db
from app.models import Issue, IssueCategory
from app.utils.issue_helpers import create_issue
from app.utils.opaque_refs import make_opaque_ref
from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.support_domain import initialize_support_student, seed_support_issue_categories


def _submit_issue(classroom, student, *, explanation="Balance looks wrong."):
    seed_support_issue_categories()
    category = IssueCategory.query.order_by(IssueCategory.id.asc()).first()
    return create_issue(
        student.seat,
        student.user_id,
        classroom.class_id,
        category.id,
        explanation,
        correlation_id=f"test:unified-ticket:corr:{student.seat_id}",
        idempotency_key=f"test:unified-ticket:issue:{student.seat_id}",
    )


def _sysadmin_client(client, username="unified_ticket_operator"):
    sysadmin = create_sysadmin(username=username)
    login_sysadmin(client, username, sysadmin.id)
    return sysadmin


def test_a_never_escalated_ticket_is_viewable_on_the_unified_route(client):
    """This is the exact case /user-reports/<ref> used to own exclusively."""
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    _sysadmin_client(client)

    response = client.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")

    assert response.status_code == 200
    assert b"Update Ticket" in response.data, (
        "an OPEN, never-escalated ticket must show the direct update form, "
        "not the escalation/bug-bounty form"
    )
    assert b"Record Technical Resolution" not in response.data


def test_an_escalated_ticket_shows_the_resolution_form_not_the_update_form(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    login_teacher(client, classroom)
    resp = client.post(
        f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate",
        data={'escalation_reason': 'Needs developer investigation'},
    )
    assert resp.status_code == 302

    _sysadmin_client(client)
    response = client.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")

    assert response.status_code == 200
    assert b"Record Technical Resolution" in response.data
    assert b"Update Ticket" not in response.data


def test_update_ticket_form_transitions_a_direct_lifecycle_ticket(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    issue_id = issue.id
    _sysadmin_client(client)

    response = client.post(
        f"/sysadmin/issues/{make_opaque_ref('issue', issue_id)}/update",
        data={"status": "CLOSED", "admin_notes": "Not reproducible."},
        follow_redirects=True,
    )

    assert response.status_code == 200
    with client.application.app_context():
        refreshed = db.session.get(Issue, issue_id)
        assert refreshed.status == Issue.STATUS_CLOSED
        assert refreshed.sysadmin_notes == "Not reproducible."


def test_update_ticket_form_refuses_to_pull_an_escalated_ticket_out_of_workflow(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    issue_id = issue.id
    login_teacher(client, classroom)
    client.post(
        f"/admin/issues/{make_opaque_ref('issue', issue_id)}/escalate",
        data={'escalation_reason': 'Needs developer investigation'},
    )
    _sysadmin_client(client)

    client.post(
        f"/sysadmin/issues/{make_opaque_ref('issue', issue_id)}/update",
        data={"status": "CLOSED", "admin_notes": "trying to skip the workflow"},
    )

    with client.application.app_context():
        refreshed = db.session.get(Issue, issue_id)
        assert refreshed.status == Issue.STATUS_ESCALATED_TO_DEV, (
            "the direct-lifecycle form must not be able to close a ticket "
            "that is inside the escalation workflow"
        )


def test_time_display_defaults_to_utc_and_toggles_to_class_timezone(client):
    """Test classrooms default to America/Los_Angeles -- September there is PDT."""
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    _sysadmin_client(client)
    ref = make_opaque_ref('issue', issue.id)

    default_page = client.get(f"/sysadmin/issues/{ref}").data.decode()
    assert "UTC" in default_page
    assert "PDT" not in default_page and "PST" not in default_page

    class_page = client.get(f"/sysadmin/issues/{ref}?tz=class").data.decode()
    assert "PDT" in class_page or "PST" in class_page
    assert "America/Los_Angeles" in class_page
