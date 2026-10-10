from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import EntitlementEvent, StoreProduct, Transaction
from app.services import obligations_service
from app.services.ledger_correction_service import (
    lock_and_resolve_purchase_eligibility,
    reverse_transaction,
)
from app.services.ledger_posting_service import create_pending_transaction
# TODO (Phase 4): store_entitlement_service deleted; must query EntitlementEvent directly
# from app.services.store_entitlement_service import list_entitlement_history
from app.utils.seat_scope import seat_scoped_filter
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.transaction_idempotency import build_transaction_idempotency_key, void_refund_key


@dataclass
class VoidTransactionResult:
    transaction_id: int
    reversal_transaction_id: int | None


class PurchaseNotReversible(ValueError):
    """Raised when a Store purchase fails the reversal eligibility gate.

    The message is the teacher-facing reason from
    ``resolve_purchase_resolution_eligibility``.
    """


class ObligationTransactionNotVoidable(ValueError):
    """Raised when a void/reversal is attempted on an obligation-related transaction.

    Per SPEC-OPS-001 §VII and INV-OPS-008, obligation-related monetary transactions
    are neither voidable nor reversible. This is determined by provenance, not
    representation. Monetary remediation, where authorized, must occur through a
    new, independently authorized adjustment transaction (INV-OPS-009); it must
    never carry machine semantics asserting reversal of the obligation.
    """
    pass


@requires_feat_context("FEAT-LED-002")
def execute_void_transaction(
    tx: Transaction,
    *,
    correlation_id: str,
    idempotency_key: str,
    reason: str = "ADMIN_CORRECTION",
    actor_seat_id: int | None = None,
) -> VoidTransactionResult:
    """Ledger-led FEAT for transaction void orchestration."""
    return _execute_void_transaction_impl(tx, reason=reason, actor_seat_id=actor_seat_id)


@requires_feat_context("FEAT-LED-002")
def execute_void_transactions(
    transactions: list[Transaction],
    *,
    correlation_id: str,
    idempotency_key: str,
    reason: str = "ADMIN_CORRECTION",
    actor_seat_id: int | None = None,
) -> list[VoidTransactionResult]:
    if transactions:
        class_ids = {tx.class_id for tx in transactions}
        if len(class_ids) != 1:
            raise ValueError("Reversal batch must remain within one class.")
        from app.services.ledger_recovery_service import lock_ledger_seats

        lock_ledger_seats(next(iter(class_ids)), [tx.seat_id for tx in transactions])
    return [
        _execute_void_transaction_impl(tx, reason=reason, actor_seat_id=actor_seat_id)
        for tx in transactions
    ]


def _execute_void_transaction_impl(
    tx: Transaction, *, reason: str, actor_seat_id: int | None = None
) -> VoidTransactionResult:
    # SPEC-OPS-001 §VII / INV-OPS-008: obligation-related monetary transactions are
    # neither voidable nor reversible. Reject at the canonical void/reversal boundary
    # BEFORE any compensating transaction can be created, so no ledger mutation occurs
    # on rejection. Obligation-relatedness is determined by provenance (an obligation
    # event references this ledger transaction), not by transaction representation/type.
    if obligations_service.is_obligation_related_transaction(tx.id):
        raise ObligationTransactionNotVoidable(
            f"Transaction #{tx.id} is obligation-related. Under SPEC-OPS-001 "
            "(INV-OPS-008), obligation-related monetary transactions are neither "
            "voidable nor reversible; monetary remediation must be a new, "
            "independently authorized adjustment (INV-OPS-009)."
        )

    # "Refund" is permitted as user-facing language for a reversal (§8.2);
    # "void" is not, because voiding money is the thing CTH does not do.
    void_description = f"Refund for transaction #{tx.id} ({reason}): {tx.description}"[:255]

    # A purchase carries downstream grants, which reversal must invalidate in
    # the same operation (SPEC-OPS-001 §3.5, INV-OPS-004). Doing it first means
    # an ineligible grant refuses the whole correction before any money moves.
    if tx.type == 'purchase':
        _void_purchase(tx)

    # One path, settled or not. Money is only ever reversed — a monetary
    # transaction must not be voided (INV-OPS-001), and marking the original
    # void alongside its reversal used to drop an unsettled debit while the
    # credit still posted, returning money that was never taken.
    recovery_inputs = {}
    if tx.amount_cents > 0:
        from app.feats.ledger_proof_inputs import positive_reversal_inputs
        from app.services.identity_service import resolve_teacher_seat_for_class
        actor_seat_id = actor_seat_id or resolve_teacher_seat_for_class(tx.class_id).id
        recovery_inputs = dict(positive_reversal_inputs(tx), mechanism="teacher")
    reversal_tx = reverse_transaction(
        tx,
        idempotency_key=void_refund_key(tx.id),
        description=void_description,
        actor_seat_id=actor_seat_id or tx.actor_seat_id,
        **recovery_inputs,
    )

    return VoidTransactionResult(
        transaction_id=tx.id,
        reversal_transaction_id=reversal_tx.id if reversal_tx else None,
    )


def _void_purchase(tx: Transaction) -> None:
    """Revoke the grants this purchase produced, resolved by provenance.

    The grants are found through ``correlation_id``, not by parsing the item
    name out of the description. Two defects lived in that parse:

    * ``store_products.name`` carries no uniqueness constraint, so two lineages
      in one class can share a name. Ordering versions by ``created_at`` could
      return a version of lineage B for a purchase made against lineage A, and
      the void then either refused or revoked the student's units of the wrong
      product while the ledger reversed the charge for the other one.
    * The ``(xN)`` in the description could disagree with the units granted:
      when one purchase granted several units but wrote ``(x1)``, the reversal
      refunded the whole charge and left the other units GRANTED — a partially
      reversible purchase, which SPEC-OPS-001 §3.5 does not permit.

    Both fall away once the units are counted rather than parsed: the purchase
    writes every grant under the transaction's own correlation, so that
    correlation names exactly the units this charge paid for.
    """
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")

    # One gate decides reversibility for the Reverse control, issue resolution
    # and this action alike. It used to be decided twice: the banking page
    # offered Reverse on any active non-insurance purchase while this action
    # accepted delayed-use items only, so a collective-goal buy-in, which
    # DOM-STORE-001 §VIII.E lets a reversal revoke with a refund, showed a
    # Reverse button that always failed. The gate also enforces SPEC-OPS-001
    # §3.4: every grant from this charge must still be active, because a
    # reversal is all-or-nothing and refunding units already spent would hand
    # back money for value the student consumed.
    eligibility = lock_and_resolve_purchase_eligibility(tx)
    if not eligibility.eligible:
        raise PurchaseNotReversible(eligibility.reason)
    selected_items = list(eligibility.grants)

    # Every unit of one purchase shares a lineage. Any version of it answers the
    # question asked here (the name for the item-removal row), so take the newest.
    store_item = (
        StoreProduct.query
        .filter_by(class_id=tx.class_id, product_lineage_uuid=selected_items[0].product_id)
        .order_by(StoreProduct.created_at.desc())
        .first()
    )
    if not store_item:
        raise ValueError("Purchase item record was not found. This transaction cannot be voided.")

    # Terminate the entitlements. Without this the purchase's units stay
    # GRANTED forever: stock remaining and per-student limits are both derived
    # by counting events, so a correction that only reverses money would
    # silently consume inventory that no student holds.
    #
    # The state written is REVOKED, the same state a directly authorized grant
    # void writes (SPEC-OPS-001 §3.3): the student is left holding nothing
    # either way, so the capability reads identically. What differs is the
    # cause, and INV-OPS-002 requires the cause to stay recoverable — hence the
    # reversed transaction is named in the payload rather than the state.
    revoked_at = utc_now()
    for event in selected_items:
        db.session.add(
            EntitlementEvent(
                class_id=event.class_id,
                entitlement_id=event.entitlement_id,
                target_seat_id=event.target_seat_id,
                actor_seat_id=tx.actor_seat_id or event.actor_seat_id,
                product_id=event.product_id,
                entitlement_type=event.entitlement_type,
                acquisition_type=event.acquisition_type,
                event_type="REVOKED",
                correlation_id=event.correlation_id,
                payload={
                    "reason": "reversal_propagated",
                    "reversed_transaction_id": tx.id,
                },
                timestamp=revoked_at,
            )
        )

    create_pending_transaction(
        seat_id=tx.seat_id,
        class_id=tx.class_id,
        target_seat_id=tx.seat_id,
        actor_seat_id=tx.actor_seat_id or tx.seat_id,
        mechanism=tx.mechanism.value if getattr(tx, "mechanism", None) else "system",
        amount=Decimal('0.00'),
        account_type=tx.account_type or 'checking',
        type='void_item_removed',
        description=f"item removed - {store_item.name}",
        idempotency_key=build_transaction_idempotency_key(
            "void", "purchase", tx.id, "item-removal"
        ),
    )
    # Canonical entitlement state is authoritative; the void path only records
    # the compensating ledger effect here.
