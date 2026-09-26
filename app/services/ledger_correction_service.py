"""Ledger-owned append-only correction boundary.

Money is reversed. Entitlements are resolved separately. SPEC-OPS-001 §II.3
forbids treating the two as interchangeable forms of undo, and INV-OPS-001
states the prohibition directly: a monetary transaction MUST NOT be voided.
This module owns the append-only monetary correction; the caller owns the
domain-specific entitlement outcome.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services.ledger_command_service import create_idempotent_transaction
from app.models import Transaction, _quantize_currency

# FEAT-LED-002 §III.2.1: a compensating transaction persists REVERSAL as its
# type, never the business reason it was raised for.
REVERSAL_TRANSACTION_TYPE = "REVERSAL"

_TERMINAL_ENTITLEMENT_EVENTS = ("CONSUMED", "EXPIRED", "REVOKED")


@dataclass(frozen=True)
class PurchaseResolutionEligibility:
    """Whether a transaction may take the REVERSE or REFUND issue outcome."""

    eligible: bool
    reason: str | None = None
    grants: tuple = ()


def resolve_purchase_resolution_eligibility(transaction) -> PurchaseResolutionEligibility:
    """Decide whether an issue may REVERSE or REFUND this transaction.

    Reversal is not universally available, and the absence of a prohibition is
    not authorization (SPEC-OPS-001 §3.7). The authorization that exists is
    narrow: FEAT-LED-002 §I resolves an eligible pre-use Store purchase, and
    DOM-SUP-001 §IX offers REVERSE and REFUND only for an unused or pending
    item. So the transaction must be a Store purchase that has not been
    reversed, carries no obligation provenance (§3.7.4), and whose grants to the
    buying seat are all still active (§6.1). Anything else takes a manual credit.

    Read-only: a GET may call this.
    """
    from app.models import EntitlementEvent
    from app.services import obligations_service

    if transaction is None or transaction.type != "purchase":
        return PurchaseResolutionEligibility(
            False, "Only a Store purchase can be reversed or refunded from an issue."
        )
    if transaction.reversal_transaction_id is not None:
        return PurchaseResolutionEligibility(False, "This transaction has already been reversed.")
    if obligations_service.is_obligation_related_transaction(transaction.id):
        return PurchaseResolutionEligibility(
            False, "An obligation-related transaction cannot be reversed or refunded."
        )
    if not transaction.correlation_id:
        return PurchaseResolutionEligibility(False, "This purchase has no traceable item grant.")

    grants = (
        EntitlementEvent.query.filter_by(
            class_id=transaction.class_id,
            target_seat_id=transaction.seat_id,
            correlation_id=transaction.correlation_id,
            acquisition_type="PURCHASE",
            event_type="GRANTED",
        )
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )
    if not grants:
        return PurchaseResolutionEligibility(False, "This purchase has no traceable item grant.")
    if any(grant.entitlement_type == "INSURANCE" for grant in grants):
        # Coverage is never revoked or refunded; it expires (FEAT-STOR-002 §IX.C).
        return PurchaseResolutionEligibility(False, "Insurance coverage cannot be reversed or refunded.")
    terminal = EntitlementEvent.query.filter(
        EntitlementEvent.class_id == transaction.class_id,
        EntitlementEvent.entitlement_id.in_([grant.entitlement_id for grant in grants]),
        EntitlementEvent.event_type.in_(_TERMINAL_ENTITLEMENT_EVENTS),
    ).first()
    if terminal is not None:
        return PurchaseResolutionEligibility(
            False,
            "A used, expired or removed item cannot be reversed or refunded. Use a manual credit instead.",
        )
    return PurchaseResolutionEligibility(True, None, tuple(grants))


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

    ``compensation_type`` records the governing reason (for example,
    ``issue_reversal`` or ``issue_refund``); the persisted ledger type remains
    ``REVERSAL``. The entitlement outcome is deliberately not performed here.
    """
    if not idempotency_key:
        raise ValueError("Ledger corrections require a command idempotency reservation.")

    check_reversal_authorization(
        actor_seat_id if actor_seat_id is not None else transaction.actor_seat_id,
        transaction,
    )

    # A reversal is terminal: neither it nor its original may be reversed again
    # (SPEC-OPS-001 §3.6, §3.7.3). The link below marks the original; this marks
    # the compensating row, which carries no reversal link of its own.
    if transaction.type == REVERSAL_TRANSACTION_TYPE:
        raise ReversalNotAuthorized(
            f"Transaction #{transaction.id} is itself a reversal and cannot be reversed."
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
        amount=compensation_amount,
        account_type=transaction.account_type or "checking",
        # The ledger vocabulary records what this row is; compensation_subtype
        # records why it was raised. Persisting the reason in `type` left the
        # canonical REVERSAL type unrepresented in history (FEAT-LED-002 §III.2.1).
        type=REVERSAL_TRANSACTION_TYPE,
        compensation_subtype=compensation_type,
        description=description, original_transaction_id=transaction.id,
        policy_id=transaction.policy_id,
        # The compensating row inherits the original's economic correlation, on
        # every path: FEAT-LED-002 §II.2 requires it to inherit or extend the
        # original, and SPEC-OPS-001 §3.1A requires REVERSE and REFUND to share
        # it. Leaving it unset let the active FEAT's correlation stand in, which
        # for a scheduled collective-goal refund named an unrelated operation.
        correlation_id=transaction.correlation_id,
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
