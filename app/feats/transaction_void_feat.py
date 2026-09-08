from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import EntitlementEvent, StoreProduct, Transaction
from app.services import obligations_service
from app.services.ledger_correction_service import reverse_transaction
from app.services.ledger_posting_service import create_pending_transaction
# TODO (Phase 4): store_entitlement_service deleted; must query EntitlementEvent directly
# from app.services.store_entitlement_service import list_entitlement_history
from app.utils.seat_scope import seat_scoped_filter
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now
from app.utils.transaction_idempotency import build_transaction_idempotency_key, void_refund_key


@dataclass
class VoidTransactionResult:
    transaction_id: int
    reversal_transaction_id: int | None


class ImmediatePurchaseNotVoidable(ValueError):
    pass


class UsedDelayedPurchaseNotVoidable(ValueError):
    pass


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
) -> VoidTransactionResult:
    """Ledger-led FEAT for transaction void orchestration."""
    return _execute_void_transaction_impl(tx, reason=reason)


@requires_feat_context("FEAT-LED-002")
def execute_void_transactions(transactions: list[Transaction], *, correlation_id: str, idempotency_key: str, reason: str = "ADMIN_CORRECTION") -> list[VoidTransactionResult]:
    return [_execute_void_transaction_impl(tx, reason=reason) for tx in transactions]


def _execute_void_transaction_impl(tx: Transaction, *, reason: str) -> VoidTransactionResult:
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
    reversal_tx = reverse_transaction(
        tx,
        idempotency_key=void_refund_key(tx.id),
        description=void_description,
    )

    return VoidTransactionResult(
        transaction_id=tx.id,
        reversal_transaction_id=reversal_tx.id if reversal_tx else tx.reversal_transaction_id,
    )


def _void_purchase(tx: Transaction) -> None:
    purchase_match = re.match(
        r'^Purchase:\s*(?P<name>.+?)(?:\s+\(x(?P<qty>\d+)\))?(?:\s+\[.*\])?$',
        (tx.description or '').strip()
    )
    if not purchase_match:
        raise ValueError("This purchase transaction cannot be voided automatically.")

    item_name = (purchase_match.group('name') or '').strip()
    quantity = int(purchase_match.group('qty') or 1)
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")
    # Products are versioned (one row per edit), so a name can match several
    # rows in the same lineage. Any version answers the questions asked here —
    # item_type and lineage are lineage-stable — so take the newest.
    store_item = (
        StoreProduct.query
        .filter_by(class_id=tx.class_id, name=item_name)
        .order_by(StoreProduct.created_at.desc())
        .first()
    )
    if not store_item:
        raise ValueError("Purchase item record was not found. This transaction cannot be voided.")
    if store_item.item_type == 'immediate':
        raise ImmediatePurchaseNotVoidable
    if store_item.item_type != 'delayed':
        raise ValueError("Only delayed-use item purchases are voidable.")
    matching_items = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == tx.seat_id,
            EntitlementEvent.class_id == tx.class_id,
            EntitlementEvent.product_id == store_item.product_lineage_uuid,
            EntitlementEvent.event_type == "GRANTED",
        )
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )
    if not matching_items:
        raise ValueError("No matching student item was found for this purchase.")

    tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()

    def _distance(event):
        if not event.timestamp:
            return float('inf')
        return abs((ensure_utc(event.timestamp) - tx_ts).total_seconds())

    # Prefer the grants closest in time to the transaction being voided; break
    # ties on event_id so the choice is deterministic across runs.
    matching_items.sort(key=lambda ev: (_distance(ev), ev.event_id))

    # An entitlement that already reached a terminal state cannot be revoked —
    # the partial unique index permits one terminal event per lineage, so a
    # second one would fail at the database anyway. Skip them here so a partly
    # consumed purchase can still return its untouched units.
    terminal_ids = {
        row[0]
        for row in db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == tx.class_id,
            EntitlementEvent.entitlement_id.in_(
                [ev.entitlement_id for ev in matching_items]
            ),
            EntitlementEvent.event_type.in_(("CONSUMED", "EXPIRED", "REVOKED")),
        )
        .all()
    }

    selected_items = []
    for event in matching_items:
        if event.entitlement_id in terminal_ids:
            continue
        selected_items.append(event)
        if len(selected_items) >= quantity:
            break
    if len(selected_items) < quantity:
        raise ValueError("Transaction cannot be voided because selected entitlements are already consumed.")

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
        user_id=tx.user_id,
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
