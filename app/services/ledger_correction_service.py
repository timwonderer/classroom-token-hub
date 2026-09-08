"""Ledger-owned append-only correction boundary.

Money is reversed. Grants are voided. SPEC-OPS-001 §II.3 forbids treating the
two as interchangeable forms of undo, and INV-OPS-001 states the prohibition
directly: a monetary transaction MUST NOT be voided. So this module offers one
operation, and voiding lives with the grants in the Entitlements domain.
"""

from decimal import Decimal

from app.extensions import db
from app.services.ledger_command_service import create_idempotent_transaction
from app.models import _quantize_currency


def reverse_transaction(
    transaction, *, description: str, compensation_type: str = "refund",
    idempotency_key: str | None = None,
):
    """Counteract a monetary transaction by appending a compensating one.

    The original is left standing as historical fact. A reversal may not
    represent it as never having occurred (SPEC-OPS-001 §3.2), so nothing on
    it changes but the link forward to its reversal — which is also what keeps
    reversal unique (INV-LED-013, INV-OPS-005).

    This is one path whether or not the charge has settled. Marking the
    original void instead would drop the debit at settlement while the credit
    still posted, handing the student the price of a purchase they made, and
    would leave the balance snapshot permanently at odds with a rebuild from
    history that INV-LED-006 requires to agree.

    Callers may present the result to users as a refund; §8.2 allows the word,
    and the operation underneath remains a reversal.
    """
    if not idempotency_key:
        raise ValueError("Ledger corrections require a command idempotency reservation.")
    compensation_amount = _quantize_currency(-(transaction.amount or Decimal("0.00")))
    kwargs = dict(
        seat_id=transaction.seat_id, class_id=transaction.class_id,
        target_seat_id=transaction.target_seat_id,
        actor_seat_id=transaction.actor_seat_id, mechanism=transaction.mechanism,
        user_id=transaction.user_id, amount=compensation_amount,
        account_type=transaction.account_type or "checking", type=compensation_type,
        description=description, original_transaction_id=transaction.id,
        policy_id=transaction.policy_id,
    )
    reversal_tx, _created = create_idempotent_transaction(
        idempotency_key=idempotency_key, **kwargs
    )
    db.session.flush()
    transaction.reversal_transaction_id = reversal_tx.id
    db.session.flush()
    return reversal_tx


__all__ = ["reverse_transaction"]
