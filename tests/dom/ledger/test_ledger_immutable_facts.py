"""INV-LED-002 (Immutable Facts) enforcement on `ledger_transaction`.

DOM-LED-001 §VII: "Once inserted, a transaction row's protected fields are
immutable. No later lifecycle patching is allowed." INV-LED-003 pairs with it —
corrections arrive as new linked rows, never as edits — so an in-place rewrite of
`amount` would destroy the history the ledger exists to keep, and would do it
silently.

The lawful post-insert writes must keep working: settlement stamps
`posting_sequence`/`posted_at`, correction links `reversal_transaction_id`, the
audit emitter stamps lineage. Those are write-once, not free.
"""

from decimal import Decimal

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from tests.helpers.ledger import provision_ledger_classroom


def _posted_transaction(seat, *, idempotency_key, amount=Decimal("25.00")):
    with FEATContext("FEAT-LED-001", idempotency_key=idempotency_key):
        tx = Transaction(
            user_id=seat.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=amount,
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Immutability fixture",
        )
        db.session.add(tx)
        db.session.flush()
    db.session.commit()
    return tx


@pytest.mark.parametrize(
    "field, value",
    [
        ("amount", Decimal("999.00")),
        ("account_type", "savings"),
        ("target_seat_id", 999999),
        ("type", "Withdrawal"),
        ("description", "rewritten after the fact"),
    ],
)
def test_INV_LED_002__protected_fields_cannot_be_patched(client, app, field, value):
    """Editing a settled fact is rejected even inside a valid FEAT context."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key=f"inv-led-002:{field}")

    with pytest.raises(ValueError, match="immutable"):
        with FEATContext("FEAT-LED-002", idempotency_key=f"inv-led-002:{field}:patch"):
            setattr(tx, field, value)
            db.session.flush()
    db.session.rollback()


def test_INV_LED_002__class_id_cannot_be_repointed(client, app):
    """Moving a posted row into another class is rejected.

    The pre-existing actor-seat scope check in `_enforce_transaction_integrity`
    fires first here and raises its own message, so this asserts the rejection
    rather than which of the two guards spoke.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:class")

    with pytest.raises(ValueError):
        with FEATContext("FEAT-LED-002", idempotency_key="inv-led-002:class:patch"):
            tx.class_id = "some-other-class"
            db.session.flush()
    db.session.rollback()


def test_INV_LED_002__amount_cents_cannot_drift_from_a_frozen_amount(client, app):
    """`amount_cents` is the integer face of `amount` and cannot be set apart from it.

    `_enforce_transaction_integrity` re-derives it from `amount` on every write,
    so a direct patch is discarded rather than rejected — the row still cannot
    end up asserting a cent figure its decimal amount contradicts.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:cents", amount=Decimal("25.00"))

    with FEATContext("FEAT-LED-002", idempotency_key="inv-led-002:cents:patch"):
        tx.amount_cents = 1
        db.session.flush()
    db.session.commit()

    assert tx.amount_cents == 2500


def test_INV_LED_007__posting_sequence_is_assignable_once_then_frozen(client, app):
    """Settlement may stamp a sequence on a NULL column; it may not restamp one."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-007:seq")
    assert tx.posting_sequence is None

    with FEATContext("FEAT-LED-003", idempotency_key="inv-led-007:seq:assign"):
        tx.posting_sequence = 1
        db.session.flush()
    db.session.commit()
    assert tx.posting_sequence == 1

    with pytest.raises(ValueError, match="posting_sequence"):
        with FEATContext("FEAT-LED-003", idempotency_key="inv-led-007:seq:restamp"):
            tx.posting_sequence = 2
            db.session.flush()
    db.session.rollback()


def test_INV_LED_002__status_still_advances_through_settlement(client, app):
    """The guard must not freeze the lifecycle it exists to protect the facts of."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:status")

    with FEATContext("FEAT-LED-003", idempotency_key="inv-led-002:status:settle"):
        tx.status = TransactionStatus.PENDING
        db.session.flush()
    db.session.commit()

    assert tx.status == TransactionStatus.PENDING
