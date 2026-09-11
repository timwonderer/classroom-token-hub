"""The /student/transfer savings projection must be honest and crash-free.

Regression for SPEC-ECON-001 §10/§11 at the route boundary: the projection was
previously computed with a hardcoded 4.5% APY fallback and bespoke math that
diverged from the runtime payout engine. The route now sources rate/cadence from
the Economic Engine and, when interest is unconfigured (the default provisioned
state, interest_rate IS NULL), must render a flat, honestly-labeled projection —
never a fabricated rate and never a 500.
"""

from __future__ import annotations

from decimal import Decimal

from app.feats.base import FEATContext
from app.scheduled_tasks import run_ledger_settlement_job
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def test_transfer_page_renders_flat_when_interest_unconfigured(client, app):
    """Default classroom has no interest_rate -> honest 'not configured' copy, 200."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    resp = client.get("/student/transfer", follow_redirects=False)
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    # Honest disclosure that interest is not configured...
    assert "not currently configured" in body
    # ...and NOT a fabricated default rate advertised as real.
    assert "4.5% annual simple interest" not in body


def test_unsettled_savings_are_disclosed_rather_than_left_contradicting(client, app):
    """The card and the projection may differ, but the page must say why.

    The savings card reads posted + pending; the projection and the interest
    forecast read posted alone. Between a deposit and the next settlement sweep
    the two legitimately disagree, and the page used to print both numbers with
    nothing reconciling them — a card reading $50.00 above a caption saying the
    posted balance was $0.00.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        key = f"transfer-disclosure:{student.seat.id}"
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

    body = client.get("/student/transfer").get_data(as_text=True)
    assert "has not finished settling yet" in body, (
        "the savings card and the projection quoted different balances with no explanation"
    )

    with app.app_context():
        run_ledger_settlement_job()

    body = client.get("/student/transfer").get_data(as_text=True)
    assert "has not finished settling yet" not in body, (
        "the balances agree after settlement, so the disclosure must not linger"
    )
