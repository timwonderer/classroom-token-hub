"""Regression: running payroll before payroll settings exist is a precondition, not a 500.

Production, 2026-10-02 13:40 UTC: a teacher who had just signed up pressed
"Run Payroll Now" before saving payroll settings. Settlement correctly failed
closed (no setting governs the rate), but ``_run_payroll`` caught the refusal in
its catch-all and answered HTTP 500 "Unexpected error during payroll." The teacher
saved settings forty seconds later; nothing told them that was the fix.

The refusal must stay (no rate, no pay), but the route reports it as a 409 that
tells the teacher what to do, and records nothing.
"""

from __future__ import annotations

from app.models import PayrollEvent, Transaction
from app.services.payroll.settings import class_has_payroll_settings
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _no_payroll_recorded(class_id: str) -> bool:
    return (
        PayrollEvent.query.filter_by(class_id=class_id).count() == 0
        and Transaction.query.filter_by(class_id=class_id, type="payroll").count() == 0
    )


def test_run_payroll_without_settings_returns_409_with_guidance(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    assert not class_has_payroll_settings(classroom.class_id)

    response = client.post(
        "/admin/run_payroll",
        json={},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 409, response.data
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "Save your payroll settings" in payload["message"]
    assert _no_payroll_recorded(classroom.class_id)


def test_run_payroll_form_post_without_settings_redirects_with_guidance(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")

    response = client.post("/admin/run_payroll", follow_redirects=True)

    assert response.status_code == 200
    assert b"Save your payroll settings" in response.data
    assert b"Unexpected error during payroll" not in response.data
    assert _no_payroll_recorded(classroom.class_id)


def _run_payroll_button(html: str) -> str:
    start = html.index('id="runPayrollBtn"')
    return html[html.rindex("<button", 0, start):html.index(">", start) + 1]


def test_payroll_page_disables_run_button_until_settings_are_saved(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")

    html = client.get("/admin/payroll").get_data(as_text=True)

    assert "disabled" in _run_payroll_button(html)
    assert 'id="runPayrollHint"' in html


def test_payroll_page_enables_run_button_once_settings_exist(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    assert class_has_payroll_settings(classroom.class_id)

    html = client.get("/admin/payroll").get_data(as_text=True)

    assert "disabled" not in _run_payroll_button(html)
    assert 'id="runPayrollHint"' not in html
