"""Seed a pending hall-pass request (a ``pending_actions`` row) for a test.

Production writes these only through ``submit_hall_pass_request``
(FEAT-STOR-002), which needs a student context and an available pass. Tests
that start from "a request is already pending" use this instead: it runs the
same domain command, ``enqueue_hall_pass_request``, under a test FEAT, and
names the seat's available grant as the entitlement acted upon when there is
one (a placeholder id otherwise, for tests of a request whose pass is gone).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.feats.base import FEATContext
from app.services.entitlement_service import get_available_hall_pass_grant
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    enqueue_hall_pass_request,
)

DEFAULT_REQUESTED_AT = datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc)


def seed_pending_hall_pass_request(
    *,
    class_id: str,
    seat_id: int,
    request_id: str | None = None,
    destination: str = "Bathroom",
    requested_at_utc: datetime = DEFAULT_REQUESTED_AT,
) -> PendingHallPassRequest:
    request = PendingHallPassRequest(
        request_id=request_id or str(uuid.uuid4()),
        class_id=class_id,
        requested_by_seat_id=seat_id,
        destination=destination,
        requested_at_utc=requested_at_utc,
    )
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"seed-hall-pass-request:{request.request_id}"):
        grant = get_available_hall_pass_grant(seat_id, class_id)
        entitlement_id = grant.entitlement_id if grant is not None else str(uuid.uuid4())
        enqueue_hall_pass_request(request, entitlement_id=entitlement_id)
    return request
