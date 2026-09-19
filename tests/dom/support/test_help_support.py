from app.models import Issue
from tests.helpers.support_domain import (
    initialize_support_teacher,
    seed_support_issue_categories,
    submit_support_ticket,
)


def test_DOM_SUP_001__help_support_page_renders_support_ticket_form(client):
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = client.get("/admin/help-support", follow_redirects=False)

    assert response.status_code == 200
    assert b"Submit Support Ticket" in response.data
    from bs4 import BeautifulSoup
    from tests.test_accessibility import _audit_html_accessibility
    _audit_html_accessibility(response.text)
    assert not BeautifulSoup(response.text, "html.parser").select("select[name=class_id]")
    assert b"My account (not class-specific)" not in response.data


def test_DOM_SUP_001__teacher_can_submit_class_scoped_support_ticket_via_admin_route(client):
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)
    seed_support_issue_categories()

    response = submit_support_ticket(
        client,
        issue_category="general",
        title="Roster sync issue",
        description="Student roster did not sync after update.",
        expected_behavior="Roster should sync immediately.",
        page_url="/admin/students",
    )

    assert response.status_code == 200
    assert b"submitted directly to system administration" in response.data

    report = Issue.query.filter_by(
        actor_public_id=classroom.teacher_seat.public_id,
        student_expected_outcome="Roster should sync immediately.",
    ).first()
    assert report is not None
    assert report.student_expected_outcome == "Roster should sync immediately."
    assert report.issue_type == "general"
    assert report.student_explanation == "Student roster did not sync after update."
    assert report.class_public_id == classroom.economy.class_public_id
    assert report.share_class_name_with_sysadmin is False
    assert report.support_permissions == {"student_report": True}
    assert report.context_snapshot['user_agent']
