"""DB CHECK constraint on ``ledger_transaction.type`` (DOM-LED-001 INV-LED-017).

Migration ``a4d7e9c2f1b6`` adds ``ck_ledger_transaction_type_closed_vocabulary``
as the only lawful set of ``Transaction.type`` values (plus NULL), enumerating
INV-LED-017's full canonical/legacy table. This constraint alone does not
require canonical spelling on new rows — the write-time casing validator that
retires the legacy aliases is a separate, later PR (SPEC-ITR-001 §6.6,
FEAT-LED-005 §IX) — so every legacy-cased value here must still pass.

Rows go through the real Ledger creation path (``record_ledger_fixture`` /
``create_pending_transaction``), not a hand-built ``INSERT``: a deferred
constraint trigger (``require_ledger_v3_creation_lineage``) requires genuine
audit-chain lineage on every new row, checked at COMMIT. Going through the
real creation path is also the more honest test — it proves the constraint
holds for rows shaped exactly like production ones, not a synthetic row that
happens to satisfy only the one trigger under test.
"""

from decimal import Decimal

import pytest
import sqlalchemy as sa

from app import db
from app.feats.base import FEATContext
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.ledger import (
    compensate_ledger_posted_transaction,
    create_ledger_idempotent_transaction,
    provision_ledger_classroom,
    record_ledger_fixture,
)

# Mirrors models.py Transaction.__table_args__ / migration a4d7e9c2f1b6 exactly.
_ALLOWED_TYPES = (
    "interest", "Interest",
    "reversal", "REVERSAL",
    "withdrawal", "Withdrawal",
    "deposit", "Deposit",
    "internal_transfer",
    "insurance_reimbursement",
    "insurance_premium",
    "purchase",
    "refund",
    "overdraft_fee",
    "payroll",
    "payroll_correction",
    "manual_payment",
    "bug_reward",
    "issue_reversal",
    "issue_compensation",
    "rent_payment",
    "void_item_removed",
)


def _create(seat, idempotency_key, type_value):
    with FEATContext("FEAT-LED-001", idempotency_key=idempotency_key):
        tx = record_ledger_fixture(
            seat_id=seat.id, class_id=seat.class_id,
            amount=Decimal("1.00"), type=type_value,
            description="INV-LED-017 vocabulary fixture",
        )
    db.session.commit()
    return tx


def _create_exact_reversal(classroom, seat, idempotency_key):
    """'REVERSAL' (exact casing) is enforced by its own trigger: it requires a
    real original transaction, negating it exactly, in the same correlation and
    scope — so it cannot go through the generic fixture above."""
    with FEATContext("FEAT-LED-001", idempotency_key=f"{idempotency_key}:origin"):
        origin, _ = create_ledger_idempotent_transaction(
            idempotency_key=f"{idempotency_key}:origin",
            seat_id=seat.id, class_id=classroom.class_id,
            amount=Decimal("1.00"), account_type="checking", type="payroll",
            description="INV-LED-017 reversal-origin fixture",
            actor_seat_id=classroom.teacher_seat_id,
        )
        settle_balances(origin.seat_id, origin.class_id)
    db.session.commit()

    with FEATContext("FEAT-LED-002", idempotency_key=f"{idempotency_key}:reversal"):
        tx = compensate_ledger_posted_transaction(
            origin, description="INV-LED-017 reversal fixture",
            idempotency_key=f"{idempotency_key}:reversal",
        )
    db.session.commit()
    return tx


@pytest.mark.parametrize("type_value", [t for t in _ALLOWED_TYPES if t != "REVERSAL"])
def test_INV_LED_017__every_enumerated_type_is_accepted(client, app, type_value):
    """Every canonical and legacy spelling in the closed vocabulary still inserts."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _create(seat, f"inv-led-017:accept:{type_value}", type_value)

    assert tx.type == type_value


def test_INV_LED_017__exact_reversal_type_is_accepted(client, app):
    """'REVERSAL' (exact casing) — the one value with its own origin-linkage
    trigger — still inserts through the real reversal path."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _create_exact_reversal(classroom, seat, "inv-led-017:accept:REVERSAL")

    assert tx.type == "REVERSAL"


def test_INV_LED_017__null_type_is_accepted(client, app):
    """NULL remains a lawful type — the constraint only closes the non-NULL set."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _create(seat, "inv-led-017:accept:null", None)

    assert tx.type is None


@pytest.mark.parametrize(
    "type_value",
    [
        "WITHDRAWAL",  # wrong casing, not one of the two lawful spellings
        "InTeReSt",
        "void",  # truncation of the real value 'void_item_removed'
        "deleted",
        "",
        "payroll ",  # trailing whitespace
    ],
)
def test_INV_LED_017__out_of_vocabulary_type_is_rejected(client, app, type_value):
    """A value outside the closed vocabulary is rejected at the database level.

    Mutation proof: confirmed red (the write would succeed) against the schema
    from before migration a4d7e9c2f1b6 — verified manually via
    `flask db downgrade f6c8d0e2a4b5`, then re-confirmed green across
    `flask db upgrade`.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    with pytest.raises(sa.exc.IntegrityError, match="ck_ledger_transaction_type_closed_vocabulary"):
        _create(seat, f"inv-led-017:reject:{type_value}", type_value)
    db.session.rollback()
