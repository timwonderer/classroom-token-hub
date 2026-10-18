"""F9: the roster's batch balance read is one statement, and earnings exclude
non-earned deposits.

``get_batch_balances_by_class_seat`` (the only caller is
``roster_view_model.py``, behind the teacher's Student Management roster)
used to read the posted snapshot and the pending-transaction sum as two
separate statements. ``_available_balance_expression`` (the single-seat read)
already documents exactly this race (#1364): a settlement committing between
the two round trips moves a transaction out of "pending" after the first
statement already read the stale posted figure, and the amount is counted in
neither. This is proven the decisive way (statement text, not a hold-and-wait
race) for the same reason ``test_hall_pass_concurrency_guards.py`` gives: an
implicit lock from a foreign key can make a timing-based test pass whether or
not the real fix is present, but there is no such table-level trick for
"how many SQL statements were sent" — that is exactly what changed.

Separately, "earnings" on the roster only excluded "Transfer"-prefixed
deposits, so the automatic overdraft-protection funding leg and reversal
refund credits (type REVERSAL) both inflated it.

PR #1550 review: the REVERSAL exclusion (``Transaction.type != "REVERSAL"``)
is not null-safe. ``type`` is nullable, and SQL's ``!=`` against NULL is
neither true nor false, so an untyped historical credit was silently
dropped from the WHERE clause and vanished from earnings entirely. Fixed
with an explicit ``type IS NULL`` branch.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Transaction
from app.services.ledger_balance_query_service import get_batch_balances_by_class_seat
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import (
    compensate_ledger_posted_transaction,
    create_ledger_idempotent_transaction,
    create_ledger_pending_transaction,
    settle_ledger_balances,
)


@pytest.fixture
def seat(app, client):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    return {"class_id": classroom.class_id, "seat_id": student.seat.id, "student": student}


def _fund_posted(student, class_id, amount, tag):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9:{tag}:{student.seat.id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"f9-fund:{tag}:{student.seat.id}",
            seat_id=student.seat.id, class_id=class_id, amount=amount,
            account_type="checking", type="payroll", description="Payroll",
        )
    db.session.commit()


def test_F9__batch_balance_read_is_one_statement(app, seat):
    """Both the posted snapshot and the pending sum come from one SQL
    statement — proven by counting statements that touch each table, not by
    racing a settlement against the read.
    """
    with app.app_context():
        _fund_posted(seat["student"], seat["class_id"], Decimal("50.00"), "stmt")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-pending:{seat['seat_id']}"):
            create_ledger_pending_transaction(
                seat_id=seat["seat_id"], class_id=seat["class_id"], amount=Decimal("5.00"),
                account_type="checking", type="manual_payment", description="Pending credit",
            )
        db.session.commit()

        statements: list[str] = []

        def record(_conn, _cursor, statement, *_args):
            statements.append(" ".join(statement.split()))

        sa.event.listen(db.engine, "before_cursor_execute", record)
        try:
            get_batch_balances_by_class_seat([(seat["class_id"], seat["seat_id"])])
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", record)

        combined = [
            s for s in statements
            if "ledger_balance_snapshot" in s and "ledger_transaction" in s
        ]
        snapshot_only = [
            s for s in statements
            if "ledger_balance_snapshot" in s and "ledger_transaction" not in s
        ]
        assert combined, "no single statement joins the snapshot and pending reads; see F9"
        assert not snapshot_only, (
            "the snapshot was read by a statement that did not also read "
            "pending transactions — the two-statement race is back"
        )


def test_F9__balance_reflects_posted_plus_pending(app, seat):
    """Sanity check that the merged query still returns the right number."""
    with app.app_context():
        _fund_posted(seat["student"], seat["class_id"], Decimal("50.00"), "value")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-pending2:{seat['seat_id']}"):
            create_ledger_pending_transaction(
                seat_id=seat["seat_id"], class_id=seat["class_id"], amount=Decimal("5.00"),
                account_type="checking", type="manual_payment", description="Pending credit",
            )
        db.session.commit()

        balances = get_batch_balances_by_class_seat([(seat["class_id"], seat["seat_id"])])
        scoped = balances[(str(seat["class_id"]), seat["seat_id"])]
        assert Decimal(scoped["checking_cents"]) / 100 == Decimal("55.00")


def test_F9__pending_transaction_before_any_snapshot_still_counts(app, seat):
    """A seat with a pending transaction but no snapshot row yet (never
    settled) must not read as 0 — the posted-snapshot LEFT JOIN must not drop
    pending-only pairs.
    """
    from app.models import LedgerBalanceSnapshot

    with app.app_context():
        assert LedgerBalanceSnapshot.query.filter_by(
            seat_id=seat["seat_id"], class_id=seat["class_id"],
        ).count() == 0

        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-nosnap:{seat['seat_id']}"):
            create_ledger_pending_transaction(
                seat_id=seat["seat_id"], class_id=seat["class_id"], amount=Decimal("7.00"),
                account_type="checking", type="manual_payment", description="Pending credit",
            )
        db.session.commit()

        balances = get_batch_balances_by_class_seat([(seat["class_id"], seat["seat_id"])])
        scoped = balances[(str(seat["class_id"]), seat["seat_id"])]
        assert Decimal(scoped["checking_cents"]) / 100 == Decimal("7.00")


def test_F9__earnings_excludes_overdraft_protection_and_refund_credits(app, seat):
    with app.app_context():
        class_id = seat["class_id"]
        seat_id = seat["seat_id"]

        _fund_posted(seat["student"], class_id, Decimal("30.00"), "earn")

        # "Deposit" isn't in IDEMPOTENT_TRANSACTION_TYPES (it's the generic
        # transfer-leg type, created directly rather than via the idempotent
        # command path) — create it pending, then settle, same as the real
        # overdraft-protection funding leg does.
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-odp:{seat_id}"):
            create_ledger_pending_transaction(
                seat_id=seat_id, class_id=class_id, amount=Decimal("20.00"),
                account_type="checking", type="Deposit",
                description="Overdraft protection transfer from savings",
            )
        db.session.commit()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-odp-settle:{seat_id}"):
            settle_ledger_balances(seat_id, class_id)
        db.session.commit()

        # A real refund is the reversal of a prior debit: create a $10
        # purchase debit, then reverse it (the production path — the DB
        # trigger enforcing exact-reversal invariants rejects a hand-built
        # REVERSAL row that doesn't negate a real original).
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-purchase:{seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"f9-purchase-tx:{seat_id}",
                seat_id=seat_id, class_id=class_id, amount=Decimal("-10.00"),
                account_type="checking", type="purchase", description="Store purchase",
            )
        db.session.commit()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-settle-purchase:{seat_id}"):
            settle_ledger_balances(seat_id, class_id)
        db.session.commit()

        purchase = Transaction.query.filter_by(
            seat_id=seat_id, class_id=class_id, type="purchase",
        ).one()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-refund:{seat_id}"):
            compensate_ledger_posted_transaction(
                purchase, description=f"Refund for transaction #{purchase.id} (teacher correction): Store purchase",
                idempotency_key=f"f9-refund-tx:{seat_id}",
            )
        db.session.commit()

        balances = get_batch_balances_by_class_seat([(class_id, seat_id)])
        scoped = balances[(str(class_id), seat_id)]
        # Only the $30.00 payroll deposit is earnings; the overdraft-protection
        # transfer and the refund must not inflate it.
        assert Decimal(scoped["earnings"]) == Decimal("30.00")


def test_PR1550_review__earnings_includes_untyped_historical_credits(app, seat):
    """``type`` is nullable (``Transaction.type``, no ``nullable=False``), and
    a bare ``Transaction.type != "REVERSAL"`` is neither true nor false for a
    NULL type in SQL, so that row is dropped from the WHERE clause entirely —
    an untyped positive credit silently vanished from earnings, even though
    it is an ordinary non-transfer, non-reversal credit (PR #1550 review).
    ``type IS NULL`` must count as "not a reversal".
    """
    with app.app_context():
        class_id, seat_id = seat["class_id"], seat["seat_id"]

        # Transaction.type is immutable once written (app/models.py's ORM
        # guard, backed by the prevent_ledger_transaction_rewrite() DB
        # trigger on UPDATE) — a real untyped row only exists from before
        # ``type`` was always populated. create_pending_transaction's
        # non-idempotent path (no idempotency_key) writes Transaction.type
        # through with no whitelist check and no UPDATE afterward, so it
        # reproduces that directly rather than mutating a row after creation.
        from app.services.ledger_posting_service import create_pending_transaction

        # FEATContext.__enter__ sets the session's active_correlation_id to
        # its own correlation_id, and the ledger insert guard rejects any
        # first-in-flush row whose correlation_id differs from it — so the
        # transaction's correlation_id must be the FEAT's own, read back
        # from the session rather than guessed at.
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f9-pr1550-untyped:{seat_id}"):
            corr = db.session.info["active_correlation_id"]
            create_pending_transaction(
                seat_id=seat_id, class_id=class_id, target_seat_id=seat_id, actor_seat_id=seat_id,
                mechanism="self", amount=Decimal("30.00"), account_type="checking",
                type=None, description="Untyped historical credit", correlation_id=corr,
            )
        db.session.commit()

        balances = get_batch_balances_by_class_seat([(class_id, seat_id)])
        scoped = balances[(str(class_id), seat_id)]
        assert Decimal(scoped["earnings"]) == Decimal("30.00")
