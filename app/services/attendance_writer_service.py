"""PROD-owned attendance append command (DOM-PROD-001 V–VII).

Composed in an existing authorized FEAT context; never opens another FEAT.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.extensions import db
from app.models import AttendanceSession, AttendanceReasonCode, Seat
from app.services.context_resolver import CanonicalContext
from app.services.attendance_service import (
    invalidate_canonical_seat_rows_cache,
    is_done_for_day,
    is_live_session,
    lock_attendance_seat,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION, SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver,
)

@dataclass(frozen=True)
class AttendanceSessionResult:
    session: AttendanceSession


def _append_hanging_pass_closure(*, ctx, left_row) -> AttendanceSession:
    """DOM-PROD-001 §XI.1: resolve a hanging pass at the end of the day it left on.

    The ``active`` row names the pass, so the pass reads as ended; the pair is
    zero-length, so it earns nothing. Caller holds the seat lock.
    """
    from app.services.identity_service import resolve_teacher_seat_for_class

    day_end = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=left_row.timestamp,
    ).boundary_end_utc
    actor_seat_id = resolve_teacher_seat_for_class(ctx.class_id).id
    closing_row = None
    for status, reason_code, hall_pass_id in (
        ("active", AttendanceReasonCode.START_WORK, left_row.hall_pass_id),
        ("inactive", AttendanceReasonCode.DONE_FOR_DAY, None),
    ):
        closing_row = AttendanceSession(
            target_seat_id=left_row.target_seat_id,
            actor_seat_id=actor_seat_id,
            class_id=left_row.class_id,
            status=status,
            reason_code=reason_code.value,
            timestamp=day_end,
            mechanism="system",
            hall_pass_id=hall_pass_id,
        )
        db.session.add(closing_row)
        db.session.flush()
    invalidate_canonical_seat_rows_cache(left_row.target_seat_id, ctx.class_id)
    return closing_row


def _latest_seat_event(seat_id, class_id):
    return AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc()).first()


def _is_hall_pass_exit(row) -> bool:
    return (
        row is not None
        and row.status == "inactive"
        and row.reason_code == AttendanceReasonCode.HALL_PASS.value
    )


def close_due_hanging_hall_pass(*, ctx, seat_id, as_of_utc):
    """PROD command: close every open pass of this seat whose day has ended.

    An open pass has an exit and no ``active`` row naming it. It may no longer be
    the seat's latest event: the student can start work the next day before the
    sweep runs. The closure is dated to the day it left on, so it sorts before that.
    """
    lock_attendance_seat(seat_id, ctx.class_id)
    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == ctx.class_id,
        AttendanceSession.hall_pass_id.isnot(None),
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    ended = {row.hall_pass_id for row in rows if row.status == "active"}
    closed = []
    for row in rows:
        if not _is_hall_pass_exit(row) or row.hall_pass_id in ended:
            continue
        day_end = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="evaluation_day_boundaries",
            reference_time_utc=row.timestamp,
        ).boundary_end_utc
        if not canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="later_than", candidate=day_end, reference=as_of_utc,
        ).is_later:
            closed.append(_append_hanging_pass_closure(ctx=ctx, left_row=row))
    return tuple(closed)


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

    existing_active = _latest_seat_event(resolved_target_seat_id, ctx.class_id)
    # Leaving needs a session to leave; returning needs this pass to be the one out.
    if (
        status == "inactive"
        and reason_code == AttendanceReasonCode.HALL_PASS
        and not is_live_session(ctx, existing_active, reference_time_utc=event_time)
    ):
        raise ValueError("Student has no work session to leave on a hall pass.")
    if status == "active" and hall_pass_id is not None and not (
        _is_hall_pass_exit(existing_active) and existing_active.hall_pass_id == hall_pass_id
    ):
        raise ValueError("Student is not out on this hall pass.")

    if status == "active":
        if is_done_for_day(
            resolved_target_seat_id, ctx.class_id, ctx=ctx,
            reference_time_utc=event_time,
        ):
            raise ValueError("Student is done for the day and cannot start work again until the next canonical day.")

        # Close any existing active session with done_for_day
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
            same_day_hanging_pass = canonical_temporal_resolver(
                SYSTEM_LEVEL_EVALUATION, primitive="between_boundaries",
                candidate=event_time,
                start_boundary=hall_pass_day_bounds.boundary_start_utc,
                end_boundary=hall_pass_day_bounds.boundary_end_utc,
            ).is_between
            returning_from_this_pass = (
                hall_pass_id is not None
                and hall_pass_id == existing_active.hall_pass_id
            )
            if same_day_hanging_pass and not returning_from_this_pass:
                raise ValueError(
                    "Student is currently out on a hall pass and must check in "
                    "before a new work session can start."
                )
            # The pass ended with its day and the sweep records that: a return
            # resumes nothing, and a start_work is simply a new session.
            if not same_day_hanging_pass and returning_from_this_pass:
                raise ValueError("This hall pass ended with the day the student left on.")

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
    # This is the sole writer of AttendanceSession rows: a reader cached this
    # scope's rows earlier in this same request (audit O4) must not keep
    # answering from before this write. Invalidating here, after the flush
    # that made this row (and, above, any closing row) visible, covers every
    # caller later in the request regardless of which of the two branches ran.
    invalidate_canonical_seat_rows_cache(resolved_target_seat_id, ctx.class_id)
    return AttendanceSessionResult(session=session)
