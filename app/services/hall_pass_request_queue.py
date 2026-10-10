"""Pending hall-pass requests, persisted as ``pending_actions`` rows.

DOM-STORE-001 §IX names "a hall-pass request remains pending until the
authoritative FEAT resolves it" as a pending action, and §VII.B makes those
rows persisted, with no generic TTL, deleted only by lawful resolution or with
the governing class boundary. Owner ruling 2026-10-01.

Until 2026-10-01 the queue was a module-level dict, so each gunicorn worker had
its own copy. With two workers a request enqueued by one was invisible to the
other, and Approve, Reject and Cancel answered "Pending request not found."
about half the time. A table row is seen by every worker, and survives restarts
and deploys.

Row shape (§VII.B):

* ``pending_action_id`` — the request id the routes and pages use;
* ``class_id`` / ``seat_id`` — the class boundary and the requesting seat;
* ``entitlement_id`` — the hall-pass grant available at submission, i.e. the
  entitlement lifecycle being acted upon;
* ``correlation_id`` — ``hall_pass_request:{class_id}:{pending_action_id}``;
* ``authoritative_feat`` — ``FEAT-PROD-002``, the one FEAT that resolves it;
* ``payload`` — the typed envelope ``{"kind": "hall_pass_request",
  "requested_by_seat_id", "destination"}``: the inputs FEAT-PROD-002 takes
  when the pass is recorded. No names.
* ``submitted_at`` — the class-canonical request time, authoritative.

Reads here are pure and take no locks; GET handlers call them (INV-ARC-007).
The commands (``enqueue``, ``pop``, ``clear``) flush, so they only run inside
the owning FEAT (``app/feats/hall_pass_request_feat.py``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.extensions import db
from app.models import PendingAction

KIND = "hall_pass_request"
AUTHORITATIVE_FEAT = "FEAT-PROD-002"


class HallPassRequestNotFound(LookupError):
    """No pending request with that id in this class (or not the caller's)."""


@dataclass(frozen=True)
class PendingHallPassRequest:
    request_id: str
    class_id: str
    requested_by_seat_id: int
    destination: str
    requested_at_utc: datetime
    # The pass this request is for (DOM-STORE-001 §IX): approval uses exactly it.
    entitlement_id: str | None = None


def new_request_id() -> str:
    return str(uuid.uuid4())


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        # The column is timestamptz; a naive value here can only be UTC.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hall_pass_rows(class_id: str):
    return PendingAction.query.filter(
        PendingAction.class_id == class_id,
        PendingAction.authoritative_feat == AUTHORITATIVE_FEAT,
        PendingAction.payload["kind"].as_string() == KIND,
    )


def _to_request(row: PendingAction) -> PendingHallPassRequest:
    payload = row.payload or {}
    return PendingHallPassRequest(
        request_id=row.pending_action_id,
        class_id=row.class_id,
        requested_by_seat_id=int(payload.get("requested_by_seat_id", row.seat_id)),
        destination=str(payload.get("destination") or ""),
        requested_at_utc=_aware_utc(row.submitted_at),
        entitlement_id=row.entitlement_id,
    )


# ---------------------------------------------------------------------------
# Pure reads
# ---------------------------------------------------------------------------

def get_pending_hall_pass_request(request_id: str, *, class_id: str) -> PendingHallPassRequest | None:
    if not request_id or not class_id:
        return None
    row = _hall_pass_rows(class_id).filter(PendingAction.pending_action_id == str(request_id)).one_or_none()
    return _to_request(row) if row is not None else None


def list_pending_hall_pass_requests_for_class(class_id: str) -> list[PendingHallPassRequest]:
    rows = (
        _hall_pass_rows(class_id)
        .order_by(PendingAction.submitted_at.asc(), PendingAction.pending_action_id.asc())
        .all()
    )
    return [_to_request(row) for row in rows]


# ---------------------------------------------------------------------------
# Domain commands — run only inside the owning FEAT
# ---------------------------------------------------------------------------

def enqueue_hall_pass_request(
    request: PendingHallPassRequest, *, entitlement_id: str,
) -> PendingHallPassRequest:
    """Persist one submitted request as a ``pending_actions`` row."""
    requested_at = request.requested_at_utc
    if not isinstance(requested_at, datetime) or requested_at.tzinfo is None:
        raise ValueError("requested_at_utc must be a timezone-aware datetime.")
    if not entitlement_id:
        raise ValueError("A hall-pass request must name the entitlement it acts upon.")
    db.session.add(PendingAction(
        pending_action_id=request.request_id,
        class_id=request.class_id,
        seat_id=request.requested_by_seat_id,
        entitlement_id=entitlement_id,
        correlation_id=f"{KIND}:{request.class_id}:{request.request_id}",
        authoritative_feat=AUTHORITATIVE_FEAT,
        payload={
            "kind": KIND,
            "requested_by_seat_id": int(request.requested_by_seat_id),
            "destination": request.destination,
        },
        submitted_at=_aware_utc(requested_at),
    ))
    db.session.flush()
    return request


def pop_pending_hall_pass_request(
    request_id: str, *, class_id: str, seat_id: int | None = None,
) -> PendingHallPassRequest | None:
    """Lock, then delete, one request; return it, or None if it is not there.

    ``SELECT ... FOR UPDATE`` serialises concurrent resolutions of the same row
    across workers: a second transaction waits for the first, and once the first
    commits its delete the row is gone and the second gets None. The delete is
    part of the caller's FEAT transaction, so if the resolution fails the row
    comes back with the rollback (DOM-STORE-001 §VII.B: a failed resolution
    leaves the pending action intact).

    ``seat_id`` restricts the take to that seat's own request (student cancel).
    """
    if not request_id or not class_id:
        return None
    query = _hall_pass_rows(class_id).filter(PendingAction.pending_action_id == str(request_id))
    if seat_id is not None:
        query = query.filter(PendingAction.seat_id == seat_id)
    row = query.with_for_update().populate_existing().one_or_none()
    if row is None:
        return None
    request = _to_request(row)
    db.session.delete(row)
    db.session.flush()
    return request


def clear_pending_hall_pass_requests_for_seat(*, class_id: str, seat_id: int) -> int:
    """Delete the seat's own pending requests in this class; return how many."""
    rows = (
        _hall_pass_rows(class_id)
        .filter(PendingAction.seat_id == seat_id)
        .with_for_update()
        .all()
    )
    for row in rows:
        db.session.delete(row)
    if rows:
        db.session.flush()
    return len(rows)
