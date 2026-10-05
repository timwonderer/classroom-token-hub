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
        issue_category="class",
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


def test_DOM_SUP_001__help_form_offers_account_and_named_class_topics(client):
    """The topic select names the active class; no stray scope caption remains."""
    from bs4 import BeautifulSoup
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)

    response = client.get("/admin/help-support")

    soup = BeautifulSoup(response.text, "html.parser")
    label = soup.find("label", attrs={"for": "issue_category"})
    assert label is not None and "I need help with" in label.get_text()
    options = {
        o["value"]: " ".join(o.get_text().split())
        for o in soup.select("select[name=issue_category] option")
        if o["value"]
    }
    assert options == {
        "account": "My own account and actions",
        "class": f"My class {classroom.economy.display_name}",
    }
    placeholder = soup.select_one("select[name=issue_category] option[value='']")
    assert placeholder is not None and placeholder.has_attr("selected")
    assert "Active class context" not in response.text


def test_DOM_SUP_001__account_topic_ticket_stays_class_scoped(client):
    """"My own account" is a topic, not a scope: the ticket keeps its class (§X)."""
    from app.utils.issue_categories import TEACHER_TOPIC_CATEGORIES
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)

    response = submit_support_ticket(
        client,
        issue_category="account",
        title="Cannot change my display name",
        description="The customization page rejects my new name.",
        expected_behavior="",
        page_url="/admin/customizations",
    )

    assert response.status_code == 200
    report = Issue.query.filter_by(title="Cannot change my display name").one()
    assert report.category.name == TEACHER_TOPIC_CATEGORIES["account"]["name"]
    assert report.category.category_type == "teacher"
    assert report.class_public_id == classroom.economy.class_public_id


def test_DOM_SUP_001__class_topic_category_does_not_carry_the_class_name(client):
    """The class name reaches support only through the consent checkbox."""
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)

    submit_support_ticket(
        client,
        issue_category="class",
        title="Roster import stalls",
        description="Import spinner never finishes.",
        expected_behavior="",
        page_url="/admin/students",
    )

    report = Issue.query.filter_by(title="Roster import stalls").one()
    assert report.category.name == "My class"
    assert classroom.economy.display_name not in report.category.name
    assert report.share_class_name_with_sysadmin is False


def test_DOM_SUP_001__unknown_help_topic_is_rejected(client):
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = submit_support_ticket(
        client,
        issue_category="bug",
        title="Legacy category value",
        description="Posted with a pre-topic category value.",
        expected_behavior="",
        page_url="",
    )

    assert b"Please choose what you need help with." in response.data
    assert Issue.query.filter_by(title="Legacy category value").first() is None
