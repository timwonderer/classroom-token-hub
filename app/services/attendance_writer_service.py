"""PROD-owned attendance append command (DOM-PROD-001 V–VII).

Composed in an existing authorized FEAT context; never opens another FEAT.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.extensions import db
from app.models import AttendanceSession, AttendanceReasonCode, Seat
from app.services.context_resolver import CanonicalContext
from app.services.attendance_service import is_done_for_day, lock_attendance_seat
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

@dataclass(frozen=True)
class AttendanceSessionResult:
    session: AttendanceSession


def record_attendance_session_command(
    *,
    ctx: CanonicalContext,
    status: str,
    target_seat_id: int | None = None,
    actor_seat_id: int | None = None,
    mechanism: str = "self",
    reason: str | None = None,
    reason_code: AttendanceReasonCode | None = None,
    hall_pass_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> AttendanceSessionResult:
    """Productivity DOMAIN command: record one attendance session row.

    Runs within the CALLING FEAT's single context — not a FEAT executor
    (INV-ARC-006, INV-ARC-021 §V.2). ``record_attendance_session`` is the thin
    FEAT-PROD-001 boundary for a top-level (route) ingress; a caller that
    already owns a context — the daily-limit enforcement job, which closes many
    seats under one envelope — composes this command directly.
    """
    if ctx is None or not getattr(ctx,'class_id',None) or not getattr(ctx,'seat_id',None):
        raise ValueError('CanonicalContext must include class_id and seat_id.')
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    event_time = evaluation.canonical_now_utc

    if status not in {"active", "inactive"}:
        raise ValueError("Attendance status must be 'active' or 'inactive'.")

    # Resolve reason_code for inactive status
    if status == "inactive" and reason_code is None and reason:
        normalized_reason = reason.strip().lower().replace(" ", "_")
        if normalized_reason == "hall_pass":
            reason_code = AttendanceReasonCode.HALL_PASS
        elif normalized_reason == "done_for_day":
            reason_code = AttendanceReasonCode.DONE_FOR_DAY
    if status == "inactive" and reason_code is None:
        raise ValueError("Inactive attendance sessions require a reason_code.")
    if status == "inactive" and reason_code == AttendanceReasonCode.HALL_PASS and not hall_pass_id:
        raise ValueError("Hall-pass attendance sessions require hall_pass_id.")

    resolved_actor_seat_id = actor_seat_id or ctx.seat_id
    resolved_target_seat_id = target_seat_id or ctx.seat_id
    if mechanism not in {"self", "teacher", "system"}:
        raise ValueError("Attendance mechanism must be 'self', 'teacher', or 'system'.")

    target_seat = lock_attendance_seat(resolved_target_seat_id, ctx.class_id)
    if target_seat is None or target_seat.class_id != ctx.class_id:
        raise ValueError("Attendance target seat must belong to the canonical class.")
    # Attendance is paid time, so recording it against an unclaimed seat is what
    # made that seat payroll-eligible. An unclaimed seat has no activated runtime
    # participation to record (DOM-IDEN-005 §VII).
    if target_seat.claimed_at is None or target_seat.user_id is None:
        raise ValueError("Attendance target seat must be claimed.")
    if resolved_actor_seat_id:
        actor_seat = db.session.get(Seat, resolved_actor_seat_id)
        if actor_seat is None or actor_seat.class_id != ctx.class_id:
            raise ValueError("Attendance actor seat must belong to the canonical class.")

    if status == "active":
        if is_done_for_day(
            resolved_target_seat_id, ctx.class_id, ctx=ctx,
            reference_time_utc=event_time,
        ):
            raise ValueError("Student is done for the day and cannot start work again until the next canonical day.")

        # Close any existing active session with done_for_day
        existing_active = AttendanceSession.query.filter(
            AttendanceSession.target_seat_id == resolved_target_seat_id,
            AttendanceSession.class_id == ctx.class_id,
        ).order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc()).first()
        if existing_active is not None and existing_active.status == "active":
            # DOM-PROD-001 §312: the auto-close `inactive` entry must be dated to
            # the SAME canonical day as the originating `active` entry. If the new
            # tap-in is on a later day, the prior day's open session terminates at
            # that prior day's end-of-day boundary — never carried to today.
            existing_day_bounds = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="evaluation_day_boundaries",
                reference_time_utc=existing_active.timestamp,
            )
            closing_timestamp = min(event_time, existing_day_bounds.boundary_end_utc)
            closing_row = AttendanceSession(
                target_seat_id=existing_active.target_seat_id,
                actor_seat_id=resolved_actor_seat_id,
                class_id=existing_active.class_id,
                status="inactive",
                reason_code=AttendanceReasonCode.DONE_FOR_DAY.value,
                timestamp=closing_timestamp,
                mechanism=mechanism,
                hall_pass_id=None,
            )
            db.session.add(closing_row)
            db.session.flush()

        elif (
            existing_active is not None
            and existing_active.status == "inactive"
            and existing_active.reason_code == AttendanceReasonCode.HALL_PASS.value
        ):
            # A "hanging hall pass" (DOM-PROD-001 §318): the seat's latest event
            # is inactive/hall_pass, meaning the student is out of the room with
            # no return recorded yet. Nothing distinguishes that from an ordinary
            # break using only the seat's latest event, so a plain start_work call
            # — one that names no hall_pass_id — was silently accepted here and
            # overwrote the open-pass state with an unrelated active session. That
            # desynchronized the hall-pass log's issued/out classification from
            # ground truth: the teacher's page stopped showing the student as out,
            # even though they still were, and there was no longer a "Return"
            # control anywhere for either side to recover with — two extra
            # teacher actions (re-mark left, then return) were needed to walk the
            # state back to something coherent. Reproduced live on 2026-09-21.
            #
            # The legitimate return path IS a status="active" call while this
            # branch is true — checkin_hall_pass and the teacher's "return" action
            # both are — so the two are distinguished by whether the caller names
            # the SAME pass it is returning from, not by status alone.
            hall_pass_day_bounds = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="evaluation_day_boundaries",
                reference_time_utc=existing_active.timestamp,
            )
            same_day_hanging_pass = (
                hall_pass_day_bounds.boundary_start_utc
                <= event_time
                < hall_pass_day_bounds.boundary_end_utc
            )
            returning_from_this_pass = (
                hall_pass_id is not None
                and hall_pass_id == existing_active.hall_pass_id
            )
            if same_day_hanging_pass and not returning_from_this_pass:
                raise ValueError(
                    "Student is currently out on a hall pass and must check in "
                    "before a new work session can start."
                )

    resolved_reason_code = (
        reason_code.value if reason_code else AttendanceReasonCode.START_WORK.value
    ) if status == "active" else (
        reason_code.value if reason_code else None
    )

    session = AttendanceSession(
        target_seat_id=resolved_target_seat_id,
        actor_seat_id=resolved_actor_seat_id,
        class_id=ctx.class_id,
        status=status,
        reason_code=resolved_reason_code,
        timestamp=event_time,
        mechanism=mechanism,
        hall_pass_id=hall_pass_id,
    )
    db.session.add(session)
    db.session.flush()
    return AttendanceSessionResult(session=session)
