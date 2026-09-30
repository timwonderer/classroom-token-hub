"""System support sees a student ticket only after its teacher escalates it.

DOM-SUP-001 §VIII makes `OPEN` -> `TEACHER_REVIEW`, the escalation itself, and
closure of a never-escalated ticket teacher (or system) acts; system support's
only transition is `ESCALATED_TO_DEV` -> `DEV_RESOLVED`. FEAT-SUP-001: student
input cannot grant system-support access to class data, and escalation is the
teacher act that does. v1 held that line by keeping teacher reports in their
own table and filtering every sysadmin issue query to escalated states.

In v2 both kinds of ticket share `issues`, and the sysadmin console selected
teacher tickets by `issue_type == 'general'` -- which every general student
ticket also is -- and counted every `OPEN`/`TEACHER_REVIEW` ticket as its own.
A student ticket therefore reached system support the moment it was filed,
with its page URL, IP address and browser, and the update form let system
support close it before the teacher saw it.

Every test here drives the production routes: the student submits through
/student/help-support, the teacher reviews and escalates through /admin/issues,
and system support reads and acts through /sysadmin.
"""
from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import unquote

from bs4 import BeautifulSoup

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Issue, IssueCategory, IssueStatusHistory, Transaction
from app.utils.opaque_refs import make_opaque_ref, resolve_opaque_ref
from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.support_domain import (
    initialize_support_student,
    seed_support_issue_categories,
)

BROWSER = "BoundaryProbeBrowser/7.1"
SUPPORT_LIST_URLS = (
    "/sysadmin/support",
    "/sysadmin/support?tab=reports",
    "/sysadmin/support?tab=reports&status=open",
    "/sysadmin/support?tab=reports&status=closed",
    "/sysadmin/support?tab=reports&status=TEACHER_FINAL_REVIEW",
    "/sysadmin/support?tab=issues",
)


# -- setup through the production routes ------------------------------------

def _student_submits(client, category_type="general", *, explanation, transaction_id=None):
    seed_support_issue_categories()
    category = (
        IssueCategory.query.filter_by(category_type=category_type, is_active=True)
        .order_by(IssueCategory.id).first()
    )
    url = (
        f"/student/help-support/transaction/{transaction_id}/report"
        if transaction_id else "/student/help-support/submit-issue"
    )
    response = client.post(
        url,
        data={"category_id": category.id, "explanation": explanation, "expected_outcome": "Fixed."},
        headers={"User-Agent": BROWSER},
    )
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    return Issue.query.filter_by(student_explanation=explanation).one()


def _teacher_submits(client, *, title):
    seed_support_issue_categories()
    response = client.post("/admin/help-support", data={
        "issue_category": "bug", "title": title, "description": "Teacher-written report.",
    }, headers={"User-Agent": BROWSER})
    assert response.status_code == 302
    return Issue.query.filter_by(title=title).one()


def _teacher_escalates(client, classroom, issue, **permissions):
    login_teacher(client, classroom)
    data = {"escalation_reason": "Needs developer investigation"}
    data.update({f"share_{name}": "on" for name, granted in permissions.items() if granted})
    response = client.post(f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate", data=data)
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Issue, issue.id).status == Issue.STATUS_ESCALATED_TO_DEV


def _teacher_denies_and_closes(client, classroom, issue):
    login_teacher(client, classroom)
    ref = make_opaque_ref("issue", issue.id)
    assert client.post(f"/admin/issues/{ref}/resolve", data={
        "action_type": "deny_issue", "denial_reason": "Working as intended.",
    }).status_code == 302
    assert client.post(f"/admin/issues/{ref}/close", data={
        "resolution_summary": "Explained to the student.",
    }).status_code == 302
    db.session.expire_all()
    closed = db.session.get(Issue, issue.id)
    assert closed.status == Issue.STATUS_CLOSED and closed.escalated_at is None


def _operator(app, username):
    sysadmin = create_sysadmin(username=username)
    operator = app.test_client()
    login_sysadmin(operator, username, sysadmin.id)
    return operator


# -- what system support can observe -----------------------------------------

def _listed_issue_ids(html):
    refs = re.findall(r"/sysadmin/issues/([^\"'/?\s<]+)", html)
    return {resolve_opaque_ref("issue", unquote(ref)) for ref in refs} - {None}


def _stat(html, label):
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(class_="sysadmin-stat-label", string=re.compile(rf"^\s*{label}\s*$"))
    assert node is not None, f"no {label!r} stat on the page"
    return int(node.find_previous_sibling(class_="sysadmin-stat-value").get_text(strip=True))


def _open_ticket_count(operator):
    response = operator.get("/sysadmin/dashboard")
    assert response.status_code == 200
    return _stat(response.get_data(as_text=True), "Open Tickets")


def _assert_invisible(operator, issue):
    """No sysadmin read surface lists, counts or discloses the ticket."""
    for url in SUPPORT_LIST_URLS:
        response = operator.get(url)
        assert response.status_code == 200, url
        html = response.get_data(as_text=True)
        assert issue.id not in _listed_issue_ids(html), f"{url} links to the ticket"
        assert BROWSER not in html, f"{url} discloses the reporter's browser"
        assert issue.actor_public_id[:8] not in html, f"{url} discloses the reporter reference"

    assert _open_ticket_count(operator) == 0
    support = operator.get("/sysadmin/support").get_data(as_text=True)
    assert _stat(support, "New Teacher Issues") == 0
    assert _stat(support, "Pending Issues") == 0

    # Direct access by reference fails exactly as a ticket that does not exist.
    missing = operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', 10**9)}")
    for suffix in ("", "?tz=class"):
        response = operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}{suffix}")
        assert response.status_code == missing.status_code == 404
        assert BROWSER not in response.get_data(as_text=True)


def _assert_invisible_except(operator, issue):
    """`_assert_invisible` for one ticket while other, visible tickets exist."""
    for url in SUPPORT_LIST_URLS:
        assert issue.id not in _listed_issue_ids(operator.get(url).get_data(as_text=True)), url
    response = operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")
    assert response.status_code == 404
    _assert_operator_cannot_mutate(operator, issue)


def _assert_operator_cannot_mutate(operator, issue):
    before = db.session.get(Issue, issue.id)
    status, notes = before.status, before.sysadmin_notes
    history = IssueStatusHistory.query.filter_by(issue_id=issue.id).count()
    ref = make_opaque_ref("issue", issue.id)

    for target in (Issue.STATUS_CLOSED, Issue.STATUS_DEV_RESOLVED, Issue.STATUS_OPEN):
        response = operator.post(f"/sysadmin/issues/{ref}/update", data={
            "status": target, "admin_notes": "operator note",
        })
        assert response.status_code == 404, target
    assert operator.post(f"/sysadmin/issues/{ref}/start-review").status_code == 404
    assert operator.post(f"/sysadmin/issues/{ref}/resolve", data={
        "resolution_note": "fixed", "eligible_for_reward": "on", "reward_amount": "5.00",
    }).status_code == 404

    db.session.expire_all()
    after = db.session.get(Issue, issue.id)
    assert (after.status, after.sysadmin_notes, after.sysadmin_reviewed_at) == (status, notes, None)
    assert IssueStatusHistory.query.filter_by(issue_id=issue.id).count() == history
    assert Transaction.query.filter_by(type="bug_reward").count() == 0


# -- tests -------------------------------------------------------------------

def test_DOM_SUP_001__student_ticket_invisible_to_sysadmin_until_teacher_escalation(client):
    app = client.application
    classroom, _student = initialize_support_student("chemistry_p1", client, app)
    issue = _student_submits(client, explanation="Boundary: pending teacher review.")
    assert issue.status == Issue.STATUS_OPEN and issue.issue_type == "general"
    operator = _operator(app, "boundary_operator")

    _assert_invisible(operator, issue)
    _assert_operator_cannot_mutate(operator, issue)

    # A second ticket from the same student stays with the teacher.
    held = _student_submits(client, explanation="Boundary: still with the teacher.")
    _teacher_escalates(client, classroom, issue)

    listed = operator.get("/sysadmin/support?tab=issues").get_data(as_text=True)
    assert issue.id in _listed_issue_ids(listed) and held.id not in _listed_issue_ids(listed)
    assert _open_ticket_count(operator) == 1
    detail = operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")
    assert detail.status_code == 200
    page = detail.get_data(as_text=True)
    assert "Record Technical Resolution" in page
    # The reporter's ticket count is a projection too: it must not reveal the held ticket.
    assert re.search(r"Total Tickets:</strong>\s*1\b", page)
    _assert_invisible_except(operator, held)


def test_student_transaction_ticket_is_invisible_to_sysadmin_until_escalation(client):
    """The transaction-category path: `issue_type` is not what gates visibility."""
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="boundary:tx:seed"):
        tx, _ = create_ledger_idempotent_transaction(
            idempotency_key=f"boundary:tx:{student.seat.id}",
            seat_id=student.seat.id, class_id=classroom.class_id,
            amount=Decimal("12.00"), account_type="checking", type="payroll",
            description="Boundary payroll",
        )
        tx_id = tx.id
    issue = _student_submits(
        client, "transaction", explanation="Boundary: wrong amount.", transaction_id=tx_id,
    )
    assert issue.issue_type == "transaction"

    operator = _operator(app, "boundary_tx_operator")
    _assert_invisible(operator, issue)
    _assert_operator_cannot_mutate(operator, issue)

    _teacher_escalates(client, classroom, issue, transaction=True)
    listed = operator.get("/sysadmin/support?tab=issues").get_data(as_text=True)
    assert issue.id in _listed_issue_ids(listed)
    assert operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}").status_code == 200


def test_teacher_closed_unescalated_ticket_never_becomes_visible(client):
    app = client.application
    classroom, _student = initialize_support_student("chemistry_p1", client, app)
    issue = _student_submits(client, explanation="Boundary: denied by teacher.")
    _teacher_denies_and_closes(client, classroom, issue)

    operator = _operator(app, "boundary_closed_operator")
    _assert_invisible(operator, issue)
    _assert_operator_cannot_mutate(operator, issue)


def test_escalated_ticket_is_visible_and_progresses_only_by_the_escalation_workflow(client):
    app = client.application
    classroom, _student = initialize_support_student("chemistry_p1", client, app)
    issue = _student_submits(client, explanation="Boundary: escalated with report.")
    _teacher_escalates(client, classroom, issue, student_report=True)
    operator = _operator(app, "boundary_escalated_operator")
    ref = make_opaque_ref("issue", issue.id)

    support = operator.get("/sysadmin/support").get_data(as_text=True)
    assert _stat(support, "Pending Issues") == 1
    assert "Boundary: escalated with report." in support  # the teacher shared it
    assert operator.post(f"/sysadmin/issues/{ref}/start-review").status_code == 302

    # The direct-lifecycle form owns no transition on an escalated ticket.
    operator.post(f"/sysadmin/issues/{ref}/update", data={"status": "CLOSED", "admin_notes": "x"})
    db.session.expire_all()
    assert db.session.get(Issue, issue.id).status == Issue.STATUS_ESCALATED_TO_DEV

    assert operator.post(f"/sysadmin/issues/{ref}/resolve", data={
        "resolution_note": "Fixed in the next release.",
    }).status_code == 302
    db.session.expire_all()
    assert db.session.get(Issue, issue.id).status == Issue.STATUS_DEV_RESOLVED

    # DEV_RESOLVED -> CLOSED is the teacher's (DOM-SUP-001 §VIII), not system support's.
    operator.post(f"/sysadmin/issues/{ref}/update", data={"status": "CLOSED", "admin_notes": "x"})
    db.session.expire_all()
    resolved = db.session.get(Issue, issue.id)
    assert resolved.status == Issue.STATUS_DEV_RESOLVED and resolved.closed_at is None

    resolved_list = operator.get("/sysadmin/support?tab=issues").get_data(as_text=True)
    assert issue.id in _listed_issue_ids(resolved_list)
    assert operator.get(f"/sysadmin/issues/{ref}").status_code == 200


def test_escalated_ticket_without_report_permission_renders_and_withholds_the_report(client):
    app = client.application
    classroom, _student = initialize_support_student("chemistry_p1", client, app)
    issue = _student_submits(client, explanation="Boundary: private student words.")
    _teacher_escalates(client, classroom, issue)  # no permissions selected
    operator = _operator(app, "boundary_withheld_operator")

    for url in SUPPORT_LIST_URLS:
        response = operator.get(url)
        assert response.status_code == 200, url
        assert "Boundary: private student words." not in response.get_data(as_text=True)
    listed = operator.get("/sysadmin/support?tab=issues").get_data(as_text=True)
    assert issue.id in _listed_issue_ids(listed)
    detail = operator.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")
    assert detail.status_code == 200
    assert "Boundary: private student words." not in detail.get_data(as_text=True)


def test_teacher_submitted_ticket_reaches_sysadmin_directly(client):
    from tests.helpers.support_domain import initialize_support_teacher
    app = client.application
    initialize_support_teacher("chemistry_p1", client, app)
    issue = _teacher_submits(client, title="Boundary teacher report")
    assert issue.escalated_at is None
    operator = _operator(app, "boundary_teacher_operator")
    ref = make_opaque_ref("issue", issue.id)

    assert _open_ticket_count(operator) == 1
    support = operator.get("/sysadmin/support").get_data(as_text=True)
    assert issue.id in _listed_issue_ids(support)
    assert _stat(support, "New Teacher Issues") == 1
    detail = operator.get(f"/sysadmin/issues/{ref}")
    assert detail.status_code == 200 and "Update Ticket" in detail.get_data(as_text=True)

    operator.post(f"/sysadmin/issues/{ref}/update", data={"status": "CLOSED", "admin_notes": "Done."})
    db.session.expire_all()
    closed = db.session.get(Issue, issue.id)
    assert closed.status == Issue.STATUS_CLOSED and closed.sysadmin_notes == "Done."
    assert _open_ticket_count(operator) == 0
    assert issue.id in _listed_issue_ids(operator.get("/sysadmin/support?status=closed").get_data(as_text=True))
