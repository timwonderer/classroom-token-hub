"""Settlement must be triggered by the application, not only by the test suite.

``create_pending_transaction`` is the sole ledger write boundary and it creates
every effect PENDING. ``settle_balances`` is the only thing that admits an effect
to posted history — it assigns ``posting_sequence`` and advances
``LedgerBalanceSnapshot``. Between them sat the defect: nothing in the running
application ever called settlement, so no transaction ever posted, no snapshot
row was ever created, and every posted-balance read answered zero permanently.
Savings interest accrues on posted balances only (SPEC-ECON-001 §9.2), so no
student could earn interest and the savings projection was pinned flat at $0.00
while their balance card showed real money.

The reason the suite never caught it is that ``tests.helpers.ledger``
deliberately exposes ``settle_ledger_balances``, so every balance test supplies
the trigger the application was missing. These tests therefore never call that
helper. They drive the scheduled job, which is the thing that was absent.
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus
from app.scheduled_tasks import (
    SCHEDULED_JOB_SPECS,
    run_ledger_settlement_job,
    run_savings_interest_job,
)
from app.services.ledger_balance_query_service import (
    get_available_balance,
    get_posted_balance,
)
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _seed(seat_id, class_id, user_id, *, amount, account_type, key):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=key):
        create_ledger_idempotent_transaction(
            idempotency_key=key,
            seat_id=seat_id,
            class_id=class_id,
            user_id=user_id,
            amount=amount,
            account_type=account_type,
            type="payroll",
            description="Settlement job test funding",
        )


def test_ledger_effects_stay_unposted_until_the_settlement_job_runs(client, app):
    """The precondition the defect rested on: a fresh effect is not posted."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        seat_id, class_id = student.seat.id, classroom.class_id
        _seed(seat_id, class_id, student.user.id, amount=Decimal("120.00"),
              account_type="checking", key=f"settle-job-pre:{seat_id}")

        tx = Transaction.query.filter_by(seat_id=seat_id, class_id=class_id).one()
        assert tx.status == TransactionStatus.PENDING
        assert tx.posting_sequence is None
        assert LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat_id, class_id=class_id
        ).count() == 0
        assert get_posted_balance(seat_id, class_id, "checking") == Decimal("0.00")


def test_settlement_job_posts_pending_effects_and_advances_the_snapshot(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        seat_id, class_id = student.seat.id, classroom.class_id
        _seed(seat_id, class_id, student.user.id, amount=Decimal("120.00"),
              account_type="checking", key=f"settle-job-post:{seat_id}")

    with app.app_context():
        summary = run_ledger_settlement_job()
        assert summary["failed_contexts"] == 0
        assert summary["settled_contexts"] >= 1

    with app.app_context():
        tx = Transaction.query.filter_by(seat_id=seat_id, class_id=class_id).one()
        assert tx.status == TransactionStatus.POSTED
        assert tx.posting_sequence is not None
        assert tx.posted_at is not None

        snapshot = LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat_id, class_id=class_id, account_type="checking"
        ).one()
        assert snapshot.posted_balance_cents == 12000
        assert snapshot.reconciled_through_posting_sequence == tx.posting_sequence
        assert get_posted_balance(seat_id, class_id, "checking") == Decimal("120.00")


def test_settlement_job_is_idempotent(client, app):
    """A second tick must not re-post or double-count an already settled effect."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        seat_id, class_id = student.seat.id, classroom.class_id
        _seed(seat_id, class_id, student.user.id, amount=Decimal("75.00"),
              account_type="checking", key=f"settle-job-idem:{seat_id}")

    with app.app_context():
        run_ledger_settlement_job()
    with app.app_context():
        first_sequence = Transaction.query.filter_by(seat_id=seat_id).one().posting_sequence
        run_ledger_settlement_job()

    with app.app_context():
        tx = Transaction.query.filter_by(seat_id=seat_id, class_id=class_id).one()
        assert tx.posting_sequence == first_sequence
        snapshot = LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat_id, class_id=class_id, account_type="checking"
        ).one()
        assert snapshot.posted_balance_cents == 7500


def test_savings_projection_base_agrees_with_the_displayed_balance(client, app):
    """Alice's defect: the savings card and the projection quoted two numbers.

    The card reads posted + pending; the projection and interest forecast read
    posted alone. With nothing ever settling, the projection reported a $0.00
    base directly beneath a card showing real savings. Once settlement runs the
    two reads must agree.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        seat_id, class_id = student.seat.id, classroom.class_id
        _seed(seat_id, class_id, student.user.id, amount=Decimal("50.00"),
              account_type="savings", key=f"settle-job-savings:{seat_id}")

        # Before settlement the two reads disagree — that is the bug's signature.
        assert get_posted_balance(seat_id, class_id, "savings") == Decimal("0.00")
        assert get_available_balance(seat_id, class_id, "savings") == Decimal("50.00")

    with app.app_context():
        run_ledger_settlement_job()

    with app.app_context():
        posted = get_posted_balance(seat_id, class_id, "savings")
        assert posted == Decimal("50.00")
        assert posted == get_available_balance(seat_id, class_id, "savings")


def test_savings_interest_job_settles_the_ledger_before_computing(client, app):
    """Interest must never be computed against an unsettled base.

    Two independent hourly interval jobs have no ordering guarantee between
    them, so ``run_savings_interest_job`` discharges the dependency itself.
    Running only the interest job must therefore leave the ledger settled.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        seat_id, class_id = student.seat.id, classroom.class_id
        _seed(seat_id, class_id, student.user.id, amount=Decimal("200.00"),
              account_type="savings", key=f"settle-job-interest:{seat_id}")

    with app.app_context():
        run_savings_interest_job()

    with app.app_context():
        seeded = Transaction.query.filter_by(
            seat_id=seat_id, class_id=class_id, account_type="savings", type="payroll"
        ).one()
        assert seeded.status == TransactionStatus.POSTED, (
            "the savings-interest job computed against an unsettled ledger"
        )
        assert get_posted_balance(seat_id, class_id, "savings") == Decimal("200.00")


def test_settlement_job_is_registered_with_the_scheduler():
    """The function existed and worked; nothing scheduled it. Guard that.

    Asserted against the declared spec set rather than a live scheduler, because
    ``init_scheduled_tasks`` is skipped under TESTING and starting a real
    BackgroundScheduler in the suite would be worse than the coverage gap.
    """
    by_id = {spec.id: spec for spec in SCHEDULED_JOB_SPECS}
    assert "ledger_settlement" in by_id, (
        "ledger settlement has no scheduled job; no transaction will ever post"
    )
    spec = by_id["ledger_settlement"]
    assert spec.func is run_ledger_settlement_job
    assert spec.trigger == "interval"
    assert spec.trigger_kwargs == {"hours": 1}


def test_settlement_is_declared_before_savings_interest():
    order = [spec.id for spec in SCHEDULED_JOB_SPECS]
    assert order.index("ledger_settlement") < order.index("savings_interest_payout"), (
        "interest accrues on posted balances, so settlement is declared first"
    )


def test_every_scheduled_job_id_is_unique():
    ids = [spec.id for spec in SCHEDULED_JOB_SPECS]
    assert len(ids) == len(set(ids))
