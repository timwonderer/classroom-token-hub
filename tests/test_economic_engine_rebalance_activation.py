"""The rebalance form must name the cadence it actually applies on.

Rent is assessed per bill cycle, and a deferred rebalance is scheduled from the
rent timeline (``_get_rent_effective_at``) — the cycle after the upcoming bill.
The form nonetheless offered "Next Payroll Run" and submitted ``next_payroll``,
naming a cadence that has nothing to do with when the change lands.

The immediate-change warning had the same shape of problem: it was rendered
unconditionally beside a deferred selection, so the teacher was warned about a
consequence of a choice they had not made.
"""

from __future__ import annotations

from tests.helpers.class_domain import update_expected_weekly_hours
from tests.helpers.classroom_initializer import initialize_as_teacher


def _rebalance_page(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    update_expected_weekly_hours(client, "40")
    response = client.get("/admin/economic-engine?review_rebalance=1")
    assert response.status_code == 200, response.get_data(as_text=True)[:2000]
    return response.get_data(as_text=True)


def test_deferred_rebalance_is_offered_as_next_cycle(client, app):
    """The default choice names the bill cycle and submits the renewal mode."""
    body = _rebalance_page(client, app)

    assert 'value="next_renewal" checked' in body
    assert "Next Cycle (Recommended)" in body
    assert "Next Payroll Run" not in body
    assert 'value="next_payroll"' not in body


def test_immediate_change_warning_starts_hidden(client, app):
    """The warning belongs to the immediate choice, which is not the default."""
    body = _rebalance_page(client, app)

    assert 'id="immediateChangeWarning" hidden' in body
