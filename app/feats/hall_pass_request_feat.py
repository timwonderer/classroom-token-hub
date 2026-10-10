"""Hall-pass request lifecycle through ``pending_actions`` (DOM-STORE-001 §VII.B, §IX).

Owner ruling 2026-10-01: a pending hall-pass request is a ``pending_actions``
row. These are the only paths that write or delete one.

* **Submit** — ``FEAT-STOR-002``. Store and Entitlements owns
  ``pending_actions`` and the hall-pass entitlement, and §VIII.E.6 says a
  hall-pass entitlement "support[s] pending action if the exercise requires
  approval". It is the same FEAT that submits a store item-use request
  (``entitlement_lifecycle_feat.execute_use_item_request``). The row names
  ``FEAT-PROD-002`` as its ``authoritative_feat``. A seat has at most one
  pending request: submitting a new one is the student withdrawing the earlier
  one, so the earlier row is deleted in the same transaction.
* **Approve** — ``FEAT-PROD-002``. In ONE transaction: lock and delete the row,
  then record the hall pass (``hall_pass_logs`` plus entitlement consumption).
  §VII.B: "A successful resolution SHALL atomically write the canonical durable
  record(s) the action produces ... and delete the pending action." If the write
  fails, the FEAT rolls back and the row is intact.
* **Reject** and **student cancel** — ``FEAT-PROD-002``. Each resolves the
  action with no durable record, by deleting the row.

None of these is a TTL: nothing deletes a row except a resolution here, or the
cascade when its seat or class is lawfully removed.
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import Seat
from app.services.hall_pass_request_queue import (
    HallPassRequestNotFound,
    PendingHallPassRequest,
    clear_pending_hall_pass_requests_for_seat,
    enqueue_hall_pass_request,
    new_request_id,
    pop_pending_hall_pass_request,
)


@requires_feat_context("FEAT-STOR-002")
def submit_hall_pass_request(
    *,
    ctx,
    destination: str,
    requested_at_utc: datetime,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> PendingHallPassRequest:
    """Persist the student's request for teacher approval."""
    from app.feats.prod import require_hall_pass_settings
    from app.services.entitlement_service import get_available_hall_pass_grant

    # Approval (FEAT-PROD-002 §III) is refused without settings, so a request
    # made without them could never be granted.
    require_hall_pass_settings(ctx.class_id, requested_at_utc)
    grant = get_available_hall_pass_grant(ctx.seat_id, ctx.class_id)
    if grant is None:
        raise ValueError("No hall passes available.")
    clear_pending_hall_pass_requests_for_seat(class_id=ctx.class_id, seat_id=ctx.seat_id)
    return enqueue_hall_pass_request(
        PendingHallPassRequest(
            request_id=new_request_id(),
            class_id=ctx.class_id,
            requested_by_seat_id=ctx.seat_id,
            destination=destination,
            requested_at_utc=requested_at_utc,
        ),
        entitlement_id=grant.entitlement_id,
    )


@requires_feat_context("FEAT-PROD-002")
def approve_hall_pass_request(
    *,
    ctx,
    request_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
):
    """Resolve the request by issuing the pass, atomically with the row's deletion."""
    from app.feats.prod import _record_hall_pass_log_impl

    request = pop_pending_hall_pass_request(request_id, class_id=ctx.class_id)
    if request is None:
        raise HallPassRequestNotFound(request_id)
    seat = db.session.get(Seat, request.requested_by_seat_id)
    if seat is None or seat.class_id != ctx.class_id:
        raise HallPassRequestNotFound(request_id)
    return _record_hall_pass_log_impl(
        ctx=ctx,
        requested_by_seat_id=seat.id,
        approved_by_seat_id=ctx.seat_id,
        destination=request.destination,
        reason="teacher_approved",
        idempotency_key=idempotency_key,
        hall_pass_entitlement_id=request.entitlement_id,
    )


@requires_feat_context("FEAT-PROD-002")
def reject_hall_pass_request(
    *,
    ctx,
    request_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> PendingHallPassRequest:
    """Resolve the request with no pass issued: delete the row."""
    request = pop_pending_hall_pass_request(request_id, class_id=ctx.class_id)
    if request is None:
        raise HallPassRequestNotFound(request_id)
    return request


@requires_feat_context("FEAT-PROD-002")
def cancel_hall_pass_request(
    *,
    ctx,
    request_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> PendingHallPassRequest:
    """The student withdraws their own request: delete the row."""
    request = pop_pending_hall_pass_request(request_id, class_id=ctx.class_id, seat_id=ctx.seat_id)
    if request is None:
        raise HallPassRequestNotFound(request_id)
    return request
