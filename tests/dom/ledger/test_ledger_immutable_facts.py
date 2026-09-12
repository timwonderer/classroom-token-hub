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
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa

from app import db
from app.feats.base import FEATContext
from app.models import (
    Transaction,
    TransactionStatus,
    _LEDGER_IMMUTABLE_FIELDS,
    _LEDGER_WRITE_ONCE_FIELDS,
)
from tests.helpers.ledger import provision_ledger_classroom


def _posted_transaction(
    seat, *, idempotency_key, amount=Decimal("25.00"), status=TransactionStatus.POSTED
):
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
            status=status,
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
    """The guard must not freeze the lifecycle it exists to protect the facts of.

    Settlement is the one lawful post-insert status write, and it runs in exactly
    this direction: a pending row becomes posted. Asserting the reverse would
    prove the guard permits the rewrite it is supposed to reject.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(
        seat,
        idempotency_key="inv-led-002:status",
        status=TransactionStatus.PENDING,
    )
    assert tx.status == TransactionStatus.PENDING

    with FEATContext("FEAT-LED-003", idempotency_key="inv-led-002:status:settle"):
        tx.status = TransactionStatus.POSTED
        db.session.flush()
    db.session.commit()

    assert tx.status == TransactionStatus.POSTED


@pytest.mark.parametrize(
    "seeded, attempted",
    [
        (TransactionStatus.POSTED, TransactionStatus.PENDING),
        (TransactionStatus.POSTED, TransactionStatus.VOID),
        (TransactionStatus.PENDING, TransactionStatus.VOID),
        (TransactionStatus.VOID, TransactionStatus.POSTED),
    ],
)
def test_INV_LED_002__status_moves_only_forward_through_settlement(
    client, app, seeded, attempted
):
    """Every status write that is not PENDING -> POSTED is rejected.

    INV-LED-003 requires a void or reversal to arrive as a new linked row. An
    in-place standing change is that correction with its history deleted, so the
    guard refuses it even inside a valid FEAT context.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    key = f"inv-led-002:status:{seeded.value}:{attempted.value}"
    tx = _posted_transaction(seat, idempotency_key=key, status=seeded)

    with pytest.raises(ValueError, match="status may not move"):
        with FEATContext("FEAT-LED-003", idempotency_key=f"{key}:patch"):
            tx.status = attempted
            db.session.flush()
    db.session.rollback()


# ---------------------------------------------------------------------------
# Database-level enforcement (migration f1a9c3e60b72)
# ---------------------------------------------------------------------------
#
# Everything above drives the ORM. `_guard_ledger_immutability` is a mapper-level
# `before_update` listener, so it only ever sees an ORM unit-of-work flush — a
# Core `update()`, a bulk `Query.update()`, `session.execute(text(...))`, a
# migration, a maintenance script, or a `psql` session all miss it entirely.
# DOM-LED-001 §VII says the protected fields are immutable "once inserted",
# without qualifying by access path, so the tests below assert the guard where
# the write actually lands rather than where the ORM happens to be standing.
#
# They deliberately use raw SQL. That is not a shortcut around the test helpers;
# it is the whole point — an ORM-driven assertion here would pass against an
# ORM-only guard and prove nothing about the property being claimed.


def _raw_update(column, value, row_id):
    """Update one column through Core SQL, bypassing the mapper listener."""
    db.session.execute(
        sa.text(f"UPDATE ledger_transaction SET {column} = :value WHERE id = :id"),
        {"value": value, "id": row_id},
    )


def test_INV_LED_002__database_rejects_a_raw_sql_rewrite_of_a_frozen_amount(client, app):
    """The guard holds against SQL the ORM never sees."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:raw-amount")
    row_id = tx.id

    with pytest.raises(sa.exc.DBAPIError, match="amount is immutable"):
        _raw_update("amount", Decimal("999.00"), row_id)
    db.session.rollback()

    assert db.session.execute(
        sa.text("SELECT amount FROM ledger_transaction WHERE id = :id"), {"id": row_id}
    ).scalar() == Decimal("25.00")


def test_INV_LED_002__database_rejects_a_raw_sql_backdate(client, app):
    """`timestamp` is a fact the Ledger stamps, not a column a fixture may retune.

    This is the exact write `tests/test_insurance_transaction_economics.py` used
    to perform, with a raw `UPDATE` chosen specifically to slip past the mapper
    listener. It is now rejected, which is what makes the ORM guard's promise
    true rather than merely stated.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:raw-backdate")

    with pytest.raises(sa.exc.DBAPIError, match="timestamp is immutable"):
        db.session.execute(
            sa.text(
                "UPDATE ledger_transaction "
                "SET timestamp = timestamp - INTERVAL '8 days' WHERE id = :id"
            ),
            {"id": tx.id},
        )
    db.session.rollback()


def test_INV_LED_002__database_rejects_a_raw_sql_void_of_a_posted_row(client, app):
    """A void must arrive as a new linked row (INV-LED-003), not as a status patch."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:raw-void")

    with pytest.raises(sa.exc.DBAPIError, match="status may not move"):
        _raw_update("status", "VOID", tx.id)
    db.session.rollback()


def test_INV_LED_002__database_still_permits_settlement_through_raw_sql(client, app):
    """The trigger must not freeze the one transition settlement depends on.

    A guard that rejected everything would pass every rejection test above while
    breaking the ledger, so the lawful direction is asserted in the same layer.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(
        seat, idempotency_key="inv-led-002:raw-settle", status=TransactionStatus.PENDING
    )
    row_id = tx.id

    _raw_update("status", "POSTED", row_id)
    db.session.commit()

    assert db.session.execute(
        sa.text("SELECT status FROM ledger_transaction WHERE id = :id"), {"id": row_id}
    ).scalar() == "POSTED"


def test_INV_LED_007__database_allows_one_posting_sequence_stamp_then_freezes_it(client, app):
    """Write-once means NULL -> value exactly once, at every layer."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-007:raw-seq")
    row_id = tx.id

    _raw_update("posting_sequence", 1, row_id)
    db.session.commit()

    with pytest.raises(sa.exc.DBAPIError, match="posting_sequence is write-once"):
        _raw_update("posting_sequence", 2, row_id)
    db.session.rollback()


def test_INV_LED_002__database_guard_covers_exactly_the_fields_the_orm_guard_does(client, app):
    """The two layers must protect the same columns or one of them is a fiction.

    Migration `f1a9c3e60b72` restates the model's field sets in plpgsql, and a
    restatement drifts. Opening a column in `app/models.py` without opening it in
    the trigger produces a write the ORM permits and the database rejects; the
    reverse produces a column the ledger claims to guard and does not. Both fail
    here rather than in production.
    """
    # `migrations/` is not an importable package (no `__init__.py`, by Alembic's
    # design), so the module is loaded from its path rather than by name.
    path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "f1a9c3e60b72_enforce_ledger_immutability_in_database.py"
    )
    assert path.exists(), f"migration not found at {path}"
    spec = spec_from_file_location("_ledger_immutability_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert set(migration._IMMUTABLE_COLUMNS) == set(_LEDGER_IMMUTABLE_FIELDS)
    assert set(migration._WRITE_ONCE_COLUMNS) == set(_LEDGER_WRITE_ONCE_FIELDS)
