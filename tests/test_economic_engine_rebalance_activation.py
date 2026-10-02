"""The rebalance form says when each change lands and offers no false choice.

Rent is assessed per bill cycle, and a rent change is dated from the rent
timeline (``_get_rent_effective_at``) — the first bill not yet sent. The form
once offered "Next Payroll Run", naming a cadence unrelated to when the change
lands; it then offered "Apply Immediately" beside "Next Cycle", but a bill
already sent keeps its frozen terms either way, so the two did the same thing.
Owner ruling 2026-09-30: the choice is removed (FEAT-ECON-001 §VI-§VIII).
"""

from __future__ import annotations

import re

from app.models import RentSettings
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.class_domain import update_expected_weekly_hours
from tests.helpers.classroom_initializer import initialize_as_teacher


def _rebalance_page(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    update_expected_weekly_hours(client, "40")
    response = client.get("/admin/economic-engine?review_rebalance=1")
    assert response.status_code == 200, response.get_data(as_text=True)[:2000]
    return response.get_data(as_text=True)


def test_the_form_offers_no_activation_choice(client, app):
    body = _rebalance_page(client, app)

    assert 'name="activation_mode"' not in body
    assert "Apply Immediately" not in body
    assert 'name="confirm_immediate"' not in body
    assert "Next Payroll Run" not in body


def test_the_form_says_when_each_change_lands(client, app):
    body = _rebalance_page(client, app)

    assert "first rent bill that has not been sent yet" in body
    assert "Store prices and the overdraft fee have no cycle to wait for" in body


def test_submitting_a_rent_change_appends_a_dated_rent_row(client, app):
    """Offering the mode is not the same as being able to submit it.

    The route once passed its FeatureSettings row into the ``class_id``
    parameter of the scheduling call, so the default choice raised instead of
    recording anything. Asserting the rendered radio could not see that. A
    deferred change is now an appended ``rent_settings`` row dated to the next
    rent period (DOM-CLASS-003 §VII).
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    update_expected_weekly_hours(client, "40")
    body = client.get("/admin/economic-engine?review_rebalance=1").get_data(as_text=True)
    offered = re.findall(r'name="selected_changes"[^>]*value="([^"]+)"', body)
    assert offered, "no rebalance change was offered, so the submit path is untested"
    with app.app_context():
        rows_before = RentSettings.query.filter_by(class_id=classroom.class_id).count()

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": offered},
    )

    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    with app.app_context():
        assert RentSettings.query.filter_by(class_id=classroom.class_id).count() == rows_before + 1
        assert get_rent_settings(classroom.class_id).rent_effective_at is not None
