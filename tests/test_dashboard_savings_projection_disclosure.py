"""The dashboard savings card and its interest projection must not contradict.

The card prints the *available* balance (posted + pending); SPEC-ECON-001 §9.2
accrues interest on the *posted* balance alone. Between a deposit and the next
settlement sweep those legitimately differ, and the dashboard printed the card
figure directly above a projection derived from a number it never showed. The
transfer page already discloses the gap; this holds the same line on the
dashboard.
"""

from __future__ import annotations

from decimal import Decimal

from app.feats.base import FEATContext
from app.scheduled_tasks import run_ledger_settlement_job
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _classroom_with_interest_and_unsettled_savings(client, app):
    """A student holding savings the engine has not yet posted, under a real APY.

    The projection line only renders when the Economic Engine has an APY (§11
    forbids a default one), so the rate has to be configured through the teacher
    surface before the contradiction is even reachable.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="banking")

    login_teacher(client, classroom)
    response = client.post(
        "/admin/banking/settings",
        data={
            "interest_apy": "4.00",
            "interest_calculation_type": "simple",
            "interest_payout_frequency": "monthly",
        },
    )
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    login_student(client, student)

    with app.app_context():
        key = f"dashboard-disclosure:{student.seat.id}"
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=key):
            create_ledger_idempotent_transaction(
                idempotency_key=key,
                seat_id=student.seat.id,
                class_id=classroom.class_id,
                user_id=student.user.id,
                amount=Decimal("50.00"),
                account_type="savings",
                type="payroll",
                description="Disclosure test funding",
            )

    return classroom, student


def test_unsettled_savings_are_disclosed_on_the_dashboard(client, app):
    """A $50.00 card above a projection on $0.00 has to explain itself."""
    _classroom_with_interest_and_unsettled_savings(client, app)

    body = client.get("/student/dashboard").get_data(as_text=True)

    assert "has not finished settling yet" in body, (
        "the savings card and the interest projection quoted different balances "
        "with no explanation"
    )
    assert "posted balance of <strong>$0.00</strong>" in body


def test_the_disclosure_clears_once_settlement_catches_up(client, app):
    """The two figures agree after settlement, so the warning must not linger."""
    _classroom_with_interest_and_unsettled_savings(client, app)

    with app.app_context():
        run_ledger_settlement_job()

    body = client.get("/student/dashboard").get_data(as_text=True)

    assert "has not finished settling yet" not in body
