"""INV-LED-002 (Immutable Facts) enforcement on `ledger_transaction`.

DOM-LED-001 §VII: "Once inserted, a transaction row's protected fields are
immutable. No later lifecycle patching is allowed." INV-LED-003 pairs with it —
corrections arrive as new linked rows, never as edits — so an in-place rewrite of
`amount` would destroy the history the ledger exists to keep, and would do it
silently.

Creation assigns the immutable ordering sequence and audit linkage. Settlement
advances the account snapshot cursor; posting is a derived view of those facts.
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
from tests.helpers.ledger import provision_ledger_classroom, record_ledger_fixture
from app.services.ledger_settlement_service import settle_balances


def _posted_transaction(seat, *, idempotency_key, amount=Decimal("25.00"), posted=True):
    with FEATContext("FEAT-LED-001", idempotency_key=idempotency_key):
        tx = record_ledger_fixture(seat_id=seat.id, class_id=seat.class_id,
            amount=amount, posted=posted, description="Immutability fixture")
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


def test_INV_LED_007__posting_sequence_is_assigned_at_creation_and_frozen(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-007:seq")
    assert tx.posting_sequence > 0
    with pytest.raises(ValueError, match="posting_sequence"):
        with FEATContext("FEAT-LED-003", idempotency_key="inv-led-007:seq:restamp"):
            tx.posting_sequence += 1
            db.session.flush()
    db.session.rollback()


def test_INV_LED_002__posting_view_advances_only_through_account_reconciliation(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _posted_transaction(seat, idempotency_key="inv-led-002:posting", posted=False)
    facts = {field: getattr(tx, field) for field in _LEDGER_IMMUTABLE_FIELDS}
    assert tx.posting_state == TransactionStatus.PENDING
    with FEATContext("FEAT-LED-003", idempotency_key="inv-led-002:posting:settle"):
        settle_balances(seat.id, seat.class_id)
    db.session.commit()
    assert tx.posting_state == TransactionStatus.POSTED
    assert {field: getattr(tx, field) for field in _LEDGER_IMMUTABLE_FIELDS} == facts


@pytest.mark.parametrize("posted", [False, True])
@pytest.mark.parametrize("attempted", [TransactionStatus.PENDING, TransactionStatus.POSTED])
def test_INV_LED_002__posting_view_cannot_be_assigned(client, app, posted, attempted):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    tx = _posted_transaction(classroom.students[0].seat,
        idempotency_key=f"inv-led-002:readonly:{posted}:{attempted.value}", posted=posted)
    with pytest.raises(AttributeError):
        tx.posting_state = attempted
    assert "status" not in Transaction.__table__.columns


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

    with pytest.raises(sa.exc.DBAPIError, match="Immutable Ledger field: amount"):
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

    with pytest.raises(sa.exc.DBAPIError, match="Immutable Ledger field: timestamp"):
        db.session.execute(
            sa.text(
                "UPDATE ledger_transaction "
                "SET timestamp = timestamp - INTERVAL '8 days' WHERE id = :id"
            ),
            {"id": tx.id},
        )
    db.session.rollback()


def test_INV_LED_002__database_has_no_mutable_status_column(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    tx = _posted_transaction(classroom.students[0].seat, idempotency_key="inv-led-002:no-status")
    with pytest.raises(sa.exc.DBAPIError, match="column .*status.* does not exist"):
        _raw_update("status", "POSTED", tx.id)
    db.session.rollback()


def test_INV_LED_007__database_freezes_creation_posting_sequence(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    tx = _posted_transaction(classroom.students[0].seat, idempotency_key="inv-led-007:raw-seq")
    with pytest.raises(sa.exc.DBAPIError, match="Immutable Ledger field: posting_sequence"):
        _raw_update("posting_sequence", tx.posting_sequence + 1, tx.id)
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
        / "e7c2a9d4f610_derive_ledger_posting_from_reconciliation.py"
    )
    assert path.exists(), f"migration not found at {path}"
    spec = spec_from_file_location("_ledger_immutability_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert set(migration.IMMUTABLE) == set(_LEDGER_IMMUTABLE_FIELDS)
    assert set(migration.WRITE_ONCE) == set(_LEDGER_WRITE_ONCE_FIELDS)
