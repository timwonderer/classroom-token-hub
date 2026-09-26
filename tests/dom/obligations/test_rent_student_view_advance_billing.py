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


def test_before_the_first_bill_the_page_shows_the_class_terms_not_zeros(client, app):
    """Live test 2026-09-26: rent switched on minutes earlier, no bill yet, and
    the student page read "$0.00 · TBD · 0 days" instead of the class's terms."""
    from datetime import timedelta
    from decimal import Decimal

    from app.utils.canonical_temporal_resolver import utc_now
    from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
    from tests.helpers.classroom_initializer import initialize_as_student

    classroom, _student = initialize_as_student("chemistry_p1", client, app)
    first_due = utc_now() + timedelta(days=10)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        customize_rent_settings(
            classroom.class_id, frequency_type="monthly", rent_amount=Decimal("230.00"),
            first_rent_due_date=first_due, grace_period_days=5,
        )

    html = client.get("/student/rent").get_data(as_text=True)

    assert "The class rent is <strong>$230.00</strong>" in html
    assert "The class rent is <strong>$0.00</strong>" not in html
    assert "<strong>5 days</strong>" in html
    assert "Rent will be due starting soon" not in html



def _student_with_rent(client, app, *, checking, incremental=True):
    from decimal import Decimal
    from uuid import uuid4

    from app.feats.base import FEATContext
    from app.utils.canonical_temporal_resolver import utc_now
    from tests.dom.obligations.test_rent_disablement_surviving_state import (
        _configure_rent,
        _reconcile,
    )
    from tests.helpers.class_domain import customize_rent_settings
    from tests.helpers.classroom_initializer import initialize_as_student
    from tests.helpers.ledger import create_ledger_idempotent_transaction

    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _configure_rent(classroom)
        if not incremental:
            customize_rent_settings(classroom.class_id, allow_incremental_payment=False)
        _reconcile(classroom, utc_now())
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"fund:{uuid4().hex}", seat_id=student.seat.id,
                class_id=classroom.class_id, amount=Decimal(checking),
                account_type="checking", type="payroll", description="Test funding",
            )
    return classroom, student.seat.id


def test_incremental_payment_is_offered_when_checking_is_short(client, app):
    """Live test 2026-09-26: the class allowed incremental payment, but a student
    short of the full bill saw only "Insufficient Funds" and no way to pay part."""
    _student_with_rent(client, app, checking="20.00")

    html = client.get("/student/rent").get_data(as_text=True)

    assert 'name="payment_amount"' in html
    assert 'max="20.00"' in html, "a part payment is capped at what checking holds"


def test_part_payment_leaves_the_rest_of_the_bill_owing(client, app):
    from decimal import Decimal

    from app.services import obligations_service

    classroom, seat_id = _student_with_rent(client, app, checking="20.00")
    correlation = _rent_correlation(classroom, seat_id, 1)

    client.post(
        "/student/rent/pay/current",
        data={"correlation_id": correlation, "payment_amount": "20.00", "payment_nonce": "part"},
    )

    with app.app_context():
        state = obligations_service.get_obligation_state(correlation)
        assert state.is_outstanding
        assert state.remaining_amount == Decimal("30.00")


def test_no_part_payment_when_the_class_does_not_allow_it(client, app):
    _student_with_rent(client, app, checking="20.00", incremental=False)

    html = client.get("/student/rent").get_data(as_text=True)

    assert 'name="payment_amount"' not in html


def test_rent_payment_ledger_line_names_the_period_not_the_obligation_id(app):
    """Live test 2026-09-26: the teacher dashboard showed "Rent payment (cycle
    obligation rent:6191…:cycle:1)". The line now names the period paid for."""
    from app.models import Transaction

    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        _fund(classroom, seat_id)
        result = _pay(classroom, seat_id, _rent_correlation(classroom, seat_id, 1))

        row = Transaction.query.filter_by(
            class_id=classroom.class_id, seat_id=seat_id, type="rent_payment"
        ).one()
        assert row.description.startswith("Rent: ")
        assert " – " in row.description
        assert "rent:" not in row.description
        assert result.success
