"""The student rent card under advance billing — DOM-OBL-001 §V.7, §VIII.

During the bill preview window a student holds two bills: the current period's
and next period's, issued early. The card must show the oldest bill still owing
(the default payment target), not simply the newest, and an early-issued bill
must be payable. Before this, the card showed next period's bill as "not yet
due" with no Pay button and hid the unpaid current bill.

Reuses the real-clock lineage from test_rent_disablement_surviving_state:
cycle 1 began five days ago; cycle 2 is advance-assessed.
"""

from __future__ import annotations

from app.services.obligation_view_model import build_student_obligation_view
from tests.dom.obligations.test_rent_disablement_surviving_state import (
    _built,
    _fund,
    _pay,
    _rent_correlation,
)


def _card(classroom, seat_id):
    view = build_student_obligation_view(seat_id, classroom.class_id, "RENT")
    return view.current_period


def test_card_shows_the_unpaid_current_bill_not_next_periods(app):
    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        card = _card(classroom, seat_id)
        assert card["correlation_id"] == _rent_correlation(classroom, seat_id, 1)
        assert card["rent_is_active"] and not card["is_paid"]


def test_next_periods_bill_is_shown_and_payable_once_the_current_is_paid(app):
    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        _fund(classroom, seat_id)
        _pay(classroom, seat_id, _rent_correlation(classroom, seat_id, 1))

        card = _card(classroom, seat_id)
        assert card["correlation_id"] == _rent_correlation(classroom, seat_id, 2)
        assert card["is_preview_period"], "next period's bill is issued ahead of its period"
        assert card["rent_is_active"], "an issued bill is payable during the preview window"
        assert not card["is_paid"]


def test_card_shows_the_current_period_once_everything_is_paid(app):
    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        _fund(classroom, seat_id)
        _pay(classroom, seat_id, _rent_correlation(classroom, seat_id, 1))
        _pay(classroom, seat_id, _rent_correlation(classroom, seat_id, 2))

        card = _card(classroom, seat_id)
        assert card["correlation_id"] == _rent_correlation(classroom, seat_id, 1)
        assert card["is_paid"]
