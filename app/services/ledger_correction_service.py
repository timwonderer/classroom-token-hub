"""Ledger-owned append-only correction boundary.

Money is reversed. Grants are voided. SPEC-OPS-001 §II.3 forbids treating the
two as interchangeable forms of undo, and INV-OPS-001 states the prohibition
directly: a monetary transaction MUST NOT be voided. So this module offers one
operation, and voiding lives with the grants in the Entitlements domain.
"""

from decimal import Decimal

from app.extensions import db
from app.services.ledger_command_service import create_idempotent_transaction
from app.models import Transaction, _quantize_currency

# FEAT-LED-002 §III.2.1: a compensating transaction persists REVERSAL as its
# type, never the business reason it was raised for.
REVERSAL_TRANSACTION_TYPE = "REVERSAL"


class TransactionAlreadyReversed(Exception):
    """Raised when a transaction that already carries a reversal is reversed again."""


class ReversalNotAuthorized(Exception):
    """Raised when the acting seat may not reverse this transaction."""


def check_reversal_authorization(actor_seat_id, transaction) -> None:
    """Guard required by FEAT-LED-002 §III.1.2 before any ledger mutation.

    SPEC-OPS-001 §XIII: reversal requires explicit governing-domain
    authorization, and absence of prohibition is not authorization. Two things
    are checked, both of which are properties of this boundary rather than of
    any one caller:

    1. An actor is named. A reversal with no actor cannot be audited under
       FEAT-LED-002 §V, which requires the operation attribute an outcome.
    2. The actor stands in the same class as the transaction. `class_id` is the
       isolation boundary, so an actor outside it has no authority over this row
       no matter what role they hold in their own class.

    Route-level checks (that the issue belongs to this class, that the
    transaction belongs to the submitting seat) remain the callers' business.
    They are narrower questions and cannot substitute for this one.
    """
    if actor_seat_id is None:
        raise ReversalNotAuthorized(
            "A reversal must name the acting seat (FEAT-LED-002 §III.1.2)."
        )
    if not transaction.class_id:
        raise ReversalNotAuthorized(
            "A transaction with no class scope cannot be reversed safely."
        )

    from app.models import Seat

    actor_seat = db.session.get(Seat, actor_seat_id)
    if actor_seat is None or actor_seat.class_id != transaction.class_id:
        raise ReversalNotAuthorized(
            "The acting seat is outside the class that owns this transaction."
        )


def reverse_transaction(
    transaction, *, description: str, compensation_type: str = "refund",
    idempotency_key: str | None = None, actor_seat_id: int | None = None,
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

    check_reversal_authorization(
        actor_seat_id if actor_seat_id is not None else transaction.actor_seat_id,
        transaction,
    )

    # INV-LED-013 / INV-OPS-005: one reversal per transaction, owned here rather
    # than by each caller. Idempotency only dedupes an identical key, and the
    # callers derive different keys for different operations — so a transaction
    # already reversed through an issue resolution could be reversed again
    # through the void route, crediting the student twice and dropping the first
    # reversal's link. An identical replay is still allowed through: it resolves
    # to the same reservation and returns the same row.
    existing_id = transaction.reversal_transaction_id
    if existing_id is not None:
        existing = db.session.get(Transaction, existing_id)
        if existing is not None and existing.idempotency_key == idempotency_key:
            return existing
        raise TransactionAlreadyReversed(
            f"Transaction #{transaction.id} was already reversed by "
            f"transaction #{existing_id}."
        )

    compensation_amount = _quantize_currency(-(transaction.amount or Decimal("0.00")))
    kwargs = dict(
        seat_id=transaction.seat_id, class_id=transaction.class_id,
        target_seat_id=transaction.target_seat_id,
        actor_seat_id=actor_seat_id or transaction.actor_seat_id,
        mechanism=transaction.mechanism,
        user_id=transaction.user_id, amount=compensation_amount,
        account_type=transaction.account_type or "checking",
        # The ledger vocabulary records what this row is; compensation_subtype
        # records why it was raised. Persisting the reason in `type` left the
        # canonical REVERSAL type unrepresented in history (FEAT-LED-002 §III.2.1).
        type=REVERSAL_TRANSACTION_TYPE,
        compensation_subtype=compensation_type,
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


__all__ = [
    "REVERSAL_TRANSACTION_TYPE",
    "ReversalNotAuthorized",
    "TransactionAlreadyReversed",
    "check_reversal_authorization",
    "reverse_transaction",
]
