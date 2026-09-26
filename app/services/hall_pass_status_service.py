"""The single authority for a hall pass's lifecycle status.

A hall pass moves through exactly three states after approval: ``approved``
(issued, not yet departed), ``left`` (out of the room), ``returned``
(completed). Two surfaces need to answer "which state is this pass in right
now" -- the public verification page and the teacher's Hall Pass Management
page -- and until this module existed they answered it with two independent
implementations.

That mattered because they had drifted. The verification page reconstructed
the state from the full attendance sequence for the specific pass (a
``left_row`` followed by a later ``active`` row means returned) -- the correct,
v1-equivalent model. The teacher's page instead asked a single, cruder
question -- "is the seat's single latest attendance event inactive/hall_pass?"
-- with no representation of "returned" at all, so a completed round trip
looked identical to a pass that had never been used: both answered "no" to
that one question and fell into the same catch-all "Issued" bucket forever,
with a "Left Class" button that would send an already-returned student back
out if clicked.

DOM-POL-001 and DOM-PROD-001 do not name this three-state model explicitly, so
this module is the FIRST place it is written down; both routes now defer to
it, so it cannot drift between them a second time the way findings 34 and 44
did between other route pairs this same night.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import AttendanceReasonCode, AttendanceSession

HALL_PASS_STATUS_APPROVED = "approved"
HALL_PASS_STATUS_LEFT = "left"
HALL_PASS_STATUS_RETURNED = "returned"


@dataclass(frozen=True)
class HallPassLifecycleStatus:
    status: str  # one of the HALL_PASS_STATUS_* constants
    left_row: AttendanceSession | None
    return_row: AttendanceSession | None


def resolve_hall_pass_lifecycle_status(
    *,
    class_id: str,
    seat_id: int,
    hall_pass_id: str,
    day_boundary_start_utc=None,
    day_boundary_end_utc=None,
) -> HallPassLifecycleStatus:
    """Resolve one pass's lifecycle state from its own attendance sequence.

    Scoped by ``hall_pass_id``, not merely by seat: a seat's attendance
    timeline can carry activity unrelated to this specific pass (an ordinary
    clock-in, a different day's pass), and only rows carrying THIS pass's
    consumed-entitlement id are evidence about it.

    ``left_row`` is the first ``inactive``/``hall_pass`` row for this pass;
    ``return_row`` is the first ``active`` row at or after it. Both are ``None``
    for a pass that has been approved but not yet departed.

    The day boundary is OPTIONAL. The two "what is happening right now" callers
    (the public verification page, the teacher's Issued/Out tabs) scope to
    today, since that is the only period either surface is asking about. A
    History view has no such single day -- a caller there passes neither
    boundary and gets the pass's full attendance sequence regardless of when
    it falls, which is what a history record is for.
    """
    query = AttendanceSession.query.filter_by(
        class_id=class_id,
        target_seat_id=seat_id,
        hall_pass_id=hall_pass_id,
    )
    if day_boundary_start_utc is not None:
        query = query.filter(AttendanceSession.timestamp >= day_boundary_start_utc)
    if day_boundary_end_utc is not None:
        query = query.filter(AttendanceSession.timestamp < day_boundary_end_utc)
    attendance_rows = query.order_by(
        AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()
    ).all()

    left_row = next(
        (
            row for row in attendance_rows
            if row.status == "inactive"
            and row.reason_code == AttendanceReasonCode.HALL_PASS.value
        ),
        None,
    )
    return_row = next(
        (
            row for row in attendance_rows
            if left_row is not None
            and row.status == "active"
            and row.timestamp >= left_row.timestamp
        ),
        None,
    )

    if return_row is not None:
        status = HALL_PASS_STATUS_RETURNED
    elif left_row is not None:
        status = HALL_PASS_STATUS_LEFT
    else:
        status = HALL_PASS_STATUS_APPROVED

    return HallPassLifecycleStatus(status=status, left_row=left_row, return_row=return_row)
