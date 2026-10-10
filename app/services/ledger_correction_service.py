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
from app.services.ledger_command_service import create_idempotent_transaction, replay_reserved_reversal
from app.models import Transaction, _quantize_currency
from app.services.ledger_provenance_query_service import get_exact_reversal, has_exact_reversal

# FEAT-LED-002 §III.2.1: a compensating transaction persists REVERSAL as its
# type, never the business reason it was raised for.
REVERSAL_TRANSACTION_TYPE = "REVERSAL"

# Entitlement types whose purchase a reversal may revoke with a refund
# (SPEC-OPS-001 §3.4.5, §3.7.1). Reversing a purchase invalidates every
# entitlement it paid for (§3.3): a delayed-use item (FEAT-LED-002 §I), a
# collective-goal buy-in (DOM-STORE-001 §VIII.E.5) and a purchased hall pass
# (owner ruling 2026-10-08; DOM-STORE-001's direct-grant rule governs revoking a
# pass on its own, not propagation from a reversed purchase). The rest are
# excluded: immediate use is CONSUMED at purchase, insurance is never revoked or
# refunded, and a privilege is in force from the moment of purchase, so there is
# no unused value to refund (owner ruling 2026-10-07).
_REVERSIBLE_ENTITLEMENT_TYPES = frozenset({"DELAYED_USE", "COLLECTIVE_GOAL", "HALL_PASS"})


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
    reversed, carries no obligation provenance (§3.7.4), whose grants are of a
    type the Store domain lets a reversal revoke, none of which has a request
    still waiting, and whose grants to the buying seat are all still active
    (§6.1). Anything else takes a manual credit.

    The reverse action (FEAT-LED-002, ``transaction_void_feat``) gates on this
    same function, so the Reverse control and the action cannot disagree.

    Read-only: a GET may call this.
    """
    from app.models import EntitlementEvent
    from app.services import obligations_service

    if transaction is None or transaction.type != "purchase":
        return PurchaseResolutionEligibility(
            False, "Only a Store purchase can be reversed or refunded from an issue."
        )
    if has_exact_reversal(transaction):
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
    if any(grant.entitlement_type not in _REVERSIBLE_ENTITLEMENT_TYPES for grant in grants):
        return PurchaseResolutionEligibility(
            False, "This kind of item cannot be reversed or refunded. Use a manual credit instead."
        )
    # An item with a request still waiting (a hall-pass request or a redemption)
    # is not reversed out from under it (owner ruling 2026-10-09). The teacher
    # approves or rejects the request first; a rejected item is neither pending
    # nor used, so it can then take REVERSE or REFUND (DOM-SUP-001 §IX).
    from app.models import PendingAction

    pending = PendingAction.query.filter(
        PendingAction.class_id == transaction.class_id,
        PendingAction.entitlement_id.in_([grant.entitlement_id for grant in grants]),
    ).first()
    if pending is not None:
        return PurchaseResolutionEligibility(
            False,
            "A request for this item is still waiting. Approve or reject it first, then reverse.",
        )

    # All-or-nothing (§3.4): one used, expired or removed unit refuses the
    # reversal. A used hall pass is ended by its hall-pass log, not an event.
    from app.services.entitlement_read_service import ended_entitlement_ids

    if ended_entitlement_ids(transaction.class_id, [grant.entitlement_id for grant in grants]):
        return PurchaseResolutionEligibility(
            False,
            "A used, expired or removed item cannot be reversed or refunded. Use a manual credit instead.",
        )
    return PurchaseResolutionEligibility(True, None, tuple(grants))


def lock_and_resolve_purchase_eligibility(transaction) -> PurchaseResolutionEligibility:
    """``resolve_purchase_resolution_eligibility`` under the buyer's seat lock.

    For the commands that act on the answer. A purchase's hall passes can be
    used (a hall-pass log) or revoked (an entitlement event), and those live in
    different tables, so the reversal takes the same seat lock as approval
    before deciding (``lock_hall_pass_holder``). The read-only function stays
    lock-free for GET handlers.
    """
    from app.services.entitlement_service import lock_hall_pass_holder

    if transaction is not None and transaction.seat_id and transaction.class_id:
        lock_hall_pass_holder(transaction.seat_id, transaction.class_id)
    return resolve_purchase_resolution_eligibility(transaction)


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
    idempotency_key: str | None = None, actor_seat_id: int | None = None, banking_directive=None, creation_evidence=(), mechanism: str = "teacher",
):
    """Counteract a monetary transaction by appending a compensating one.

    The original is left standing as historical fact. A reversal may not
    represent it as never having occurred (SPEC-OPS-001 §3.2), so nothing on
    it changes. The new effect identifies its original and preserves the
    economic correlation; scoped effect queries establish reversal uniqueness
    (INV-LED-013, INV-OPS-005).

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

    if transaction.amount_cents > 0 and actor_seat_id is None:
        raise ReversalNotAuthorized("Positive-credit recovery requires the current acting seat.")

    check_reversal_authorization(
        actor_seat_id if actor_seat_id is not None else transaction.actor_seat_id,
        transaction,
    )

    # A reversal is terminal: neither it nor its original may be reversed again
    # (SPEC-OPS-001 §3.6, §3.7.3). The compensating row's own immutable type
    # prevents reversing the compensation itself.
    if transaction.type == REVERSAL_TRANSACTION_TYPE:
        raise ReversalNotAuthorized(
            f"Transaction #{transaction.id} is itself a reversal and cannot be reversed."
        )

    # Serialize every reversal with settlement and other corrections before
    # checking immutable children. The seat/economy/original lock order also
    # covers purchase debits, whose reversals are positive credits.
    from app.feats.base import get_active_feat_name
    from app.services.ledger_recovery_service import lock_recovery_scope, ledger_origin_locator

    lock_recovery_scope(
        transaction.class_id, transaction.seat_id, ledger_origin_locator(transaction)
    )
    existing = get_exact_reversal(transaction)
    if existing is not None:
        if (existing.idempotency_key == idempotency_key
                and existing.feat_code == get_active_feat_name()):
            if existing.compensation_subtype != compensation_type:
                raise ValueError("Replay fingerprint mismatch for reversal compensation subtype.")
            return replay_reserved_reversal(
                original=transaction, principal=existing,
                actor_seat_id=actor_seat_id or transaction.actor_seat_id,
                mechanism=mechanism if transaction.amount_cents > 0 else transaction.mechanism,
                compensation_subtype=compensation_type, idempotency_key=idempotency_key,
            )
        raise TransactionAlreadyReversed(
            f"Transaction #{transaction.id} was already reversed by "
            f"transaction #{existing.id}."
        )

    if transaction.amount_cents > 0:
        if banking_directive is None:
            raise ReversalNotAuthorized('Positive-credit reversal requires Class-owned funding directive.')
        from app.services.ledger_recovery_service import lock_recovery_scope,ledger_origin_locator,get_credit_compensation_proof,resolve_credit_recovery,apply_credit_recovery
        from app.services.ledger_balance_query_service import get_account_posting_boundary
        locator=ledger_origin_locator(transaction)
        lock_recovery_scope(transaction.class_id,transaction.seat_id,locator)
        proof=get_credit_compensation_proof(class_id=transaction.class_id,target_seat_id=transaction.seat_id,
            origin_locator=locator,through_posting_sequence=get_account_posting_boundary(transaction.seat_id,transaction.class_id,transaction.account_type) or 0,creation_evidence=creation_evidence)
        plan=resolve_credit_recovery(proof=proof,recovery_kind='EXACT_REVERSAL',
            correction_intent_locator=f'ledger-reversal:v1:{transaction.id}',banking_directive=banking_directive,
            compensation_type=compensation_type,
            actor_seat_id=actor_seat_id or transaction.actor_seat_id,mechanism=mechanism,description=description)
        return apply_credit_recovery(plan=plan,idempotency_key=idempotency_key)['principal']

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
        # every path: FEAT-LED-002 §II.2 requires the exact original
        # correlation, and SPEC-OPS-001 §3.1A requires REVERSE and REFUND to share
        # it. Leaving it unset let the active FEAT's correlation stand in, which
        # for a scheduled collective-goal refund named an unrelated operation.
        correlation_id=transaction.correlation_id,
    )
    reversal_tx, _created = create_idempotent_transaction(
        idempotency_key=idempotency_key, **kwargs
    )
    db.session.flush()
    return reversal_tx


__all__ = [
    "REVERSAL_TRANSACTION_TYPE",
    "ReversalNotAuthorized",
    "TransactionAlreadyReversed",
    "check_reversal_authorization",
    "reverse_transaction",
]
