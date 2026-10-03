from __future__ import annotations

from typing import Any

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import PendingAction


@requires_feat_context("FEAT-STOR-002")
def execute_use_item_immediate(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    product_id: int,
    entitlement_type: str,
    acquisition_type: str,
    item_type: str,
    details: str | None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Execute immediate item consumption."""
    from app.services.entitlement_service import consume_entitlement

    consume_entitlement(
        entitlement_id=entitlement_id,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=target_seat_id,
        product_id=product_id,
        entitlement_type=entitlement_type,
        acquisition_type=acquisition_type,
        correlation_id=correlation_id or f"immediate_use_{entitlement_id}",
        payload={
            "outcome": "APPROVED",
            "source": "api.use_item",
            "item_type": item_type,
            "details": details,
        },
    )


@requires_feat_context("FEAT-STOR-002")
def execute_use_item_request(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    action_payload: dict[str, Any],
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Create a pending action for item use request."""
    pending_action = PendingAction(
        class_id=class_id,
        seat_id=seat_id,
        entitlement_id=entitlement_id,
        correlation_id=correlation_id or idempotency_key or f"pending_{entitlement_id}",
        authoritative_feat="FEAT-STOR-002",
        payload=action_payload,
    )
    db.session.add(pending_action)


def _request_facts(pending_action: PendingAction) -> dict[str, Any]:
    """The request facts a decision carries forward onto its durable event.

    DOM-STORE-001 §VII.B deletes the pending row on resolution, so whatever the
    teacher needs to read the decision later — what the student wrote, when
    they asked — has to travel onto the event that outlives it.
    """
    payload = pending_action.payload or {}
    submitted_at = pending_action.submitted_at
    return {
        "pending_action_id": pending_action.pending_action_id,
        "request_submitted_at": submitted_at.isoformat() if submitted_at else None,
        "details": payload.get("details") or None,
    }


def _ensure_unresolved(pending_action: PendingAction, entitlement: Any) -> None:
    payload = pending_action.payload or {}
    if payload.get("outcome"):
        raise ValueError("Redemption request has already been resolved")
    if (
        pending_action.entitlement_id != entitlement.entitlement_id
        or pending_action.class_id != entitlement.class_id
        or pending_action.seat_id != entitlement.target_seat_id
    ):
        raise ValueError("Redemption request does not belong to this entitlement")


@requires_feat_context("FEAT-STOR-002")
def execute_approve_redemption(
    *,
    entitlement: Any,
    store_item: Any,
    pending_action: PendingAction,
    ctx: Any,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Approve a redemption: record CONSUMED and close the request.

    DOM-STORE-001 §VIII.E.4 records ``CONSUMED`` on successful redemption, and
    §VII.B requires the resolution to write that record and delete the pending
    action in one transaction. The decision is final: once the row is gone
    there is nothing left to decide, and the terminal event forbids another.
    """
    from app.services.entitlement_service import consume_entitlement
    from app.services.redemption_query_service import APPROVAL_SOURCE

    _ensure_unresolved(pending_action, entitlement)
    if store_item.item_type == "hall_pass":
        # A hall pass is exercised by Productivity through hall_pass_logs, never
        # by a Store-owned CONSUMED (FEAT-STOR-002 §VII), and its requests are
        # resolved by FEAT-PROD-002. The Store no longer accepts one.
        raise ValueError("Hall-pass requests are resolved from the Hall Passes page.")

    consume_entitlement(
        entitlement_id=entitlement.entitlement_id,
        class_id=entitlement.class_id,
        target_seat_id=entitlement.target_seat_id,
        actor_seat_id=ctx.seat_id,
        product_id=entitlement.product_id,
        entitlement_type=entitlement.entitlement_type,
        acquisition_type=entitlement.acquisition_type,
        correlation_id=pending_action.correlation_id,
        payload={
            "outcome": "APPROVED",
            "source": APPROVAL_SOURCE,
            "item_type": store_item.item_type,
            **_request_facts(pending_action),
        },
    )
    db.session.delete(pending_action)
    db.session.flush()


@requires_feat_context("FEAT-STOR-002")
def execute_deny_redemption(
    *,
    entitlement: Any,
    store_item: Any,
    pending_action: PendingAction,
    ctx: Any,
    decision_note: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Deny a redemption: record REVOKED and close the request.

    While a request waits, the only record is its pending action; the
    entitlement's terminal event is written when the request is resolved
    (owner ruling 2026-10-03): ``CONSUMED`` for an approval, ``REVOKED`` for a
    denial (DOM-STORE-001 §VIII.E.4), nothing for a return.

    A redemption request is a use. Refunds and voids belong to the stage
    before it, while the student holds the item unused (SPEC-OPS-001
    §III–§V). Once the student asks, the teacher decides by the class's own
    norms, which CTH cannot know, so any request may be denied however the
    item was acquired, and a denial moves no money.
    """
    from app.services.entitlement_service import revoke_entitlement
    from app.services.redemption_query_service import DENIAL_SOURCE

    _ensure_unresolved(pending_action, entitlement)
    if store_item.item_type == "hall_pass":
        raise ValueError("Hall-pass requests are resolved from the Hall Passes page.")

    note = (decision_note or "").strip() or None
    revoke_entitlement(
        entitlement_id=entitlement.entitlement_id,
        class_id=entitlement.class_id,
        target_seat_id=entitlement.target_seat_id,
        actor_seat_id=ctx.seat_id,
        product_id=entitlement.product_id,
        entitlement_type=entitlement.entitlement_type,
        acquisition_type=entitlement.acquisition_type,
        correlation_id=pending_action.correlation_id,
        payload={
            "outcome": "DENIED",
            "source": DENIAL_SOURCE,
            "item_type": store_item.item_type,
            "decision_note": note[:500] if note else None,
            **_request_facts(pending_action),
        },
    )
    db.session.delete(pending_action)
    db.session.flush()


@requires_feat_context("FEAT-STOR-002")
def execute_return_redemption(
    *,
    entitlement: Any,
    pending_action: PendingAction,
    ctx: Any,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Return a redemption: close the request and give the item back unused.

    The third disposition beside approve and deny (owner ruling 2026-10-03).
    The teacher declines this request without spending the item, so the
    student still holds it and may ask again. No entitlement event is written:
    the entitlement's lifecycle did not move, and DOM-STORE-001 §VII.B deletes
    the pending action on resolution. A returned request therefore leaves no
    durable record of its own.
    """
    _ensure_unresolved(pending_action, entitlement)
    db.session.delete(pending_action)
    db.session.flush()


IMMEDIATE_USE_ACKNOWLEDGEMENT = "immediate_use_acknowledgement"


def record_immediate_use_acknowledgement(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    product_id: str | None,
    policy_uuid: str | None,
) -> PendingAction:
    """Queue an immediate-use purchase for the teacher (DOM-STORE-001 §VIII.E.3).

    A FEAT-STOR-002 domain command, not a FEAT entry: the purchase FEAT calls
    it inside its own transaction, the same way it coordinates the instant-use
    ``CONSUMED`` (FEAT-STOR-002 §X), so exactly one FEAT executes. The row is a
    reminder: the entitlement is already ``CONSUMED``, and the only resolution
    is the teacher marking it complete.
    """
    pending_action = PendingAction(
        class_id=class_id,
        seat_id=seat_id,
        entitlement_id=entitlement_id,
        correlation_id=f"immediate_use_ack:{class_id}:{entitlement_id}",
        authoritative_feat="FEAT-STOR-002",
        payload={
            "kind": IMMEDIATE_USE_ACKNOWLEDGEMENT,
            "product_id": product_id,
            "policy_uuid": policy_uuid,
        },
    )
    db.session.add(pending_action)
    return pending_action


@requires_feat_context("FEAT-STOR-002")
def execute_complete_immediate_use(
    *,
    pending_action: PendingAction,
    ctx: Any,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Mark an immediate-use purchase complete: delete its reminder.

    The only resolution an immediate-use pending action has (DOM-STORE-001
    §VIII.E.3). It writes no entitlement event, because the entitlement was
    already ``CONSUMED`` at purchase.
    """
    if (pending_action.payload or {}).get("kind") != IMMEDIATE_USE_ACKNOWLEDGEMENT:
        raise ValueError("This is not an immediate-use purchase.")
    if pending_action.class_id != ctx.class_id:
        raise ValueError("This purchase is not in this class.")
    db.session.delete(pending_action)
    db.session.flush()
