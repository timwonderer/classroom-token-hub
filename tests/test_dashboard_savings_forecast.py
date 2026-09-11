"""The dashboard savings forecast must come from the configured policy.

The transfer page was repaired for SPEC-ECON-001 §10/§11 and the dashboard was
left behind: it computed ``savings_balance * 0.045 / 12`` inline. That is a
hardcoded APY in a projection (§10), derived from the *available* balance rather
than the posted one accrual actually uses (§9.2), with bespoke math that ignores
the class's calculation type, compounding and payout cadence — and it labelled
the result "/month" regardless of the configured cadence.

A default classroom configures no interest rate, so the honest forecast there is
nothing at all, and the page must not advertise interest it will never pay.
"""

from __future__ import annotations

from decimal import Decimal

from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _fund_savings(classroom, student, app, amount="200.00"):
    with app.app_context():
        key = f"dashboard-forecast:{student.seat.id}"
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=key):
            create_ledger_idempotent_transaction(
                idempotency_key=key,
                seat_id=student.seat.id,
                class_id=classroom.class_id,
                user_id=student.user.id,
                amount=Decimal(amount),
                account_type="savings",
                type="payroll",
                description="Dashboard forecast funding",
            )


def test_dashboard_advertises_no_interest_when_none_is_configured(client, app):
    """No configured rate means no projection line, not a fabricated one."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    _fund_savings(classroom, student, app)

    response = client.get("/student/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Projected Interest" not in body
    assert "missing out on interest" not in body


def test_dashboard_forecast_matches_the_payout_engine(client, app):
    """The rendered figure is the engine's, on the engine's cadence."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    _fund_savings(classroom, student, app)

    with app.app_context():
        from app.services.economic_engine import savings_interest_for_payout_period
        from app.services.ledger_balance_query_service import get_posted_balance
        from app.services.ledger_interest_service import resolve_savings_policy

        policy = resolve_savings_policy(classroom.class_id)
        expected = savings_interest_for_payout_period(
            posted_balance=get_posted_balance(student.seat.id, classroom.class_id, "savings"),
            annual_rate=policy.annual_rate,
            calculation_type=policy.calculation_type,
            compound_frequency=policy.compound_frequency,
            payout_frequency=policy.payout_frequency,
        )

    body = client.get("/student/dashboard").get_data(as_text=True)

    # The unconfigured default pays nothing, so the inline 4.5% figure the old
    # code would have printed for this balance must be absent.
    assert expected == Decimal("0.00")
    assert "0.75" not in body
