from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import (
    AttendanceReasonCode,
    AttendanceSession,
    HallPassLog,
    PayrollEvent,
    Seat,
)
from app.services.hall_pass_request_queue import list_pending_hall_pass_requests_for_class
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


def get_attendance_session_counts_by_seat(
    class_id: str, window_start, window_end
) -> dict[int, int]:
    """Map ``target_seat_id`` → count of attendance sessions in ``[start, end)``.

    Read-only DOM-PROD-001 surface consumed by the Interpretation domain
    (SPEC-ITR-001 §5.3). ``AttendanceSession`` is the authoritative participation
    fact; Ledger is never consulted for participation (INV-ITR-016). Only seats
    with ≥1 session appear in the mapping — the caller supplies the enrolled
    population and treats absent seats as zero. Scoped by ``class_id`` and the
    half-open completed-cycle window.
    """
    if not class_id or window_start is None or window_end is None:
        return {}
    rows = (
        AttendanceSession.query
        .with_entities(
            AttendanceSession.target_seat_id,
            db.func.count(AttendanceSession.id),
        )
        .filter(
            AttendanceSession.class_id == class_id,
            AttendanceSession.timestamp >= ensure_utc(window_start),
            AttendanceSession.timestamp < ensure_utc(window_end),
        )
        .group_by(AttendanceSession.target_seat_id)
        .all()
    )
    return {seat_id: int(count) for seat_id, count in rows if seat_id is not None}


def _current_evaluation_day_bounds(ctx):
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
    )
    return evaluation.boundary_start_utc, evaluation.boundary_end_utc


def _current_evaluation_day_bounds_for_date(ctx, evaluation_date):
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        evaluation_date=evaluation_date,
    )
    return evaluation.boundary_start_utc, evaluation.boundary_end_utc


def _elapsed_seconds(ctx, intervals):
    if not intervals:
        return 0
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="elapsed_duration",
        intervals=intervals,
    )
    return evaluation.elapsed_seconds


def _pair_active_intervals(rows, *, end_boundary, start_boundary=None):
    intervals = []
    active_start = None
    for row in rows:
        timestamp = row.timestamp
        if row.status == "active":
            active_start = timestamp
            continue
        if row.status == "inactive" and active_start is not None:
            interval_start = active_start
            interval_end = timestamp
            if start_boundary and interval_end <= start_boundary:
                active_start = None
                continue
            if start_boundary and interval_start < start_boundary:
                interval_start = start_boundary
            if interval_end > end_boundary:
                interval_end = end_boundary
            if interval_end >= interval_start:
                intervals.append((interval_start, interval_end))
            active_start = None
    if active_start is not None:
        interval_start = active_start
        interval_end = end_boundary
        if start_boundary and interval_start < start_boundary:
            interval_start = start_boundary
        if interval_end >= interval_start:
            intervals.append((interval_start, interval_end))
    return intervals


def _derive_hall_pass_state(seat_id: int, class_id: str):
    """Return the latest non-returned hall-pass display state for a seat/class."""
    pending_requests = [
        request for request in list_pending_hall_pass_requests_for_class(class_id)
        if request.requested_by_seat_id == seat_id
    ]
    if pending_requests:
        latest_pending = pending_requests[-1]
        return {
            "id": latest_pending.request_id,
            "status": "pending",
            "reason": latest_pending.destination,
        }

    latest_pass = HallPassLog.query.filter_by(
        requested_by_seat_id=seat_id,
        class_id=class_id,
    ).order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc()).first()
    if latest_pass is None:
        return None

    rows = AttendanceSession.query.filter_by(
        target_seat_id=seat_id,
        class_id=class_id,
        hall_pass_id=latest_pass.hall_pass_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    left_row = next(
        (
            row for row in rows
            if row.status == "inactive"
            and row.reason_code == AttendanceReasonCode.HALL_PASS.value
        ),
        None,
    )
    return_row = next(
        (
            row for row in rows
            if left_row is not None
            and row.status == "active"
            and row.timestamp >= left_row.timestamp
        ),
        None,
    )
    if return_row is not None:
        return None
    status = "left" if left_row is not None else "approved"
    return {
        "id": latest_pass.id,
        "status": status,
        "reason": latest_pass.destination,
    }


# Stamped into ``payroll_event.summary_json["settlement_rule"]`` by every
# attendance-derived payroll event settled under the closed-session rule. A
# ``payroll`` event without it was settled by the earlier rule, which paid the
# elapsed part of a still-open session; see ``_legacy_paid_through``.
CLOSED_SESSION_SETTLEMENT_RULE = "closed_sessions"


@dataclass(frozen=True)
class SeatPayrollAttendance:
    """What a seat's attendance timeline owes, as of one instant.

    ``payable_seconds`` is closed, unpaid work: exactly what a payroll run at that
    instant settles. ``in_progress_seconds`` is the still-open session, which no
    run pays until it closes. Their sum is everything not yet paid.
    """

    payable_seconds: int
    in_progress_seconds: int

    @property
    def unpaid_seconds(self) -> int:
        return self.payable_seconds + self.in_progress_seconds


def _day_end_utc(ctx, timestamp):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=timestamp,
    ).boundary_end_utc


def _split_sessions(rows, *, ctx, as_of_utc):
    """Pair the timeline into closed sessions plus at most one open session.

    An ``active`` row opens a session and the next ``inactive`` row closes it. A
    further ``active`` row while a session is open continues that session rather
    than restarting it, so no elapsed time is dropped. DOM-PROD-001 §VI.1
    terminates every session at the end of its class-local day, so a session whose
    day has ended is closed at that boundary even if the ``done_for_day`` row has
    not been written yet, and a later-dated row cannot extend it overnight.
    """
    closed = []
    open_start = None
    open_day_end = None
    for row in rows:
        timestamp = ensure_utc(row.timestamp)
        if timestamp > as_of_utc:
            break
        if open_start is not None and timestamp >= open_day_end:
            closed.append((open_start, open_day_end))
            open_start = None
        if row.status == "active":
            if open_start is None:
                open_start = timestamp
                open_day_end = _day_end_utc(ctx, timestamp)
        elif row.status == "inactive" and open_start is not None:
            closed.append((open_start, timestamp))
            open_start = None

    in_progress = None
    if open_start is not None:
        if open_day_end <= as_of_utc:
            closed.append((open_start, open_day_end))
        else:
            in_progress = (open_start, as_of_utc)
    return closed, in_progress


def _legacy_paid_through(legacy_times, session_end):
    """Latest legacy payroll instant strictly inside a session, else ``None``.

    A payroll event settled before the closed-session rule paid a session that was
    open at that instant up to the instant itself. That part is already paid, so a
    session closing afterwards is settled only from the latest such instant.
    """
    earlier = [instant for instant in legacy_times if instant < session_end]
    return max(earlier) if earlier else None


@dataclass(frozen=True)
class SeatPayrollIntervals:
    """The intervals behind :class:`SeatPayrollAttendance`, as of one instant.

    ``payable`` holds the closed, unpaid part of each session a run at that
    instant settles; each interval ends when its session closed, which is the
    instant that decides the setting that prices it (DOM-PROD-001 §XV.3).
    ``in_progress`` is the still-open session, if any.
    """

    payable: tuple
    in_progress: tuple


def calculate_seat_payroll_intervals(
    seat_id: int, class_id: str, *, ctx, as_of_utc=None
) -> SeatPayrollIntervals:
    """The single PROD reading of what a seat's attendance owes (DOM-PROD-001 §VI.3).

    A session is payable once it has closed after the seat's last ``payroll``
    event, and it is paid in full by the payroll window in which it closes. A
    still-open session is never payable. Every session is therefore paid exactly
    once and never split across windows. The payroll run and every unpaid-time
    preview read this function, so what a teacher is shown and what the run pays
    cannot diverge.
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_seat_payroll_attendance requires seat_id and class_id.")
    if as_of_utc is None:
        as_of_utc = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="current_time",
        ).canonical_now_utc
    as_of_utc = ensure_utc(as_of_utc)

    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    closed, in_progress = _split_sessions(rows, ctx=ctx, as_of_utc=as_of_utc)

    payroll_events = (
        PayrollEvent.query.with_entities(PayrollEvent.recorded_at, PayrollEvent.summary_json)
        .filter(
            PayrollEvent.class_id == class_id,
            PayrollEvent.target_seat_id == seat_id,
            PayrollEvent.payroll_event_type == "payroll",
            PayrollEvent.recorded_at <= as_of_utc,
        )
        .all()
    )
    paid_through = max((ensure_utc(e.recorded_at) for e in payroll_events), default=None)
    legacy_times = [
        ensure_utc(e.recorded_at)
        for e in payroll_events
        if (e.summary_json or {}).get("settlement_rule") != CLOSED_SESSION_SETTLEMENT_RULE
    ]

    payable = []
    for start, end in closed:
        if paid_through is not None and end <= paid_through:
            continue
        legacy = _legacy_paid_through(legacy_times, end)
        if legacy is not None and legacy > start:
            start = legacy
        if end > start:
            payable.append((start, end))

    open_intervals = []
    if in_progress is not None:
        start, end = in_progress
        legacy = _legacy_paid_through(legacy_times, end)
        if legacy is not None and legacy > start:
            start = legacy
        if end > start:
            open_intervals.append((start, end))

    return SeatPayrollIntervals(payable=tuple(payable), in_progress=tuple(open_intervals))


def elapsed_attendance_seconds(ctx, intervals) -> int:
    """Elapsed seconds across ``intervals`` under the canonical temporal resolver."""
    return _elapsed_seconds(ctx, list(intervals))


def calculate_seat_payroll_attendance(
    seat_id: int, class_id: str, *, ctx, as_of_utc=None
) -> SeatPayrollAttendance:
    """Seconds of :func:`calculate_seat_payroll_intervals`: payable and in progress."""
    intervals = calculate_seat_payroll_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    return SeatPayrollAttendance(
        payable_seconds=_elapsed_seconds(ctx, list(intervals.payable)),
        in_progress_seconds=_elapsed_seconds(ctx, list(intervals.in_progress)),
    )


def calculate_unpaid_attendance_seconds(seat_id: int, class_id: str, *, ctx):
    """Everything not yet paid: closed unpaid work plus the open session."""
    return calculate_seat_payroll_attendance(seat_id, class_id, ctx=ctx).unpaid_seconds


def calculate_payable_attendance_seconds(seat_id: int, class_id: str, *, ctx, as_of_utc=None):
    """Closed unpaid work only: what a payroll run at ``as_of_utc`` settles."""
    return calculate_seat_payroll_attendance(
        seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc
    ).payable_seconds


def calculate_worked_attendance_seconds_for_date(seat_id: int, class_id: str, evaluation_date, *, ctx):
    """Return authoritative worked seconds for one class-local date.

    PRODUCTIVITY consumers receive a duration only; they never interpret
    AttendanceSession rows or reason codes. Still-active sessions are clipped
    at the canonical now so a claim cannot count time that has not elapsed.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds_for_date(ctx, evaluation_date)
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    end_boundary = min(day_end_utc, now_evaluation.canonical_now_utc)
    if end_boundary <= day_start_utc:
        return 0
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    intervals = _pair_active_intervals(
        canonical_rows,
        start_boundary=day_start_utc,
        end_boundary=end_boundary,
    )
    return _elapsed_seconds(ctx, intervals)


def calculate_worked_attendance_seconds_today(seat_id: int, class_id: str, *, ctx):
    """Return authoritative worked seconds for the CURRENT class-local day.

    Same day-bounded, now-clipped semantics as
    ``calculate_worked_attendance_seconds_for_date`` but anchored to the class's
    current evaluation day. This is the value the student UI labels "Time Today";
    it must never be the unbounded unpaid-since-payroll figure, which can span
    many days when payroll has not run.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds(ctx)
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    end_boundary = min(day_end_utc, now_evaluation.canonical_now_utc)
    if end_boundary <= day_start_utc:
        return 0
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    intervals = _pair_active_intervals(
        canonical_rows,
        start_boundary=day_start_utc,
        end_boundary=end_boundary,
    )
    return _elapsed_seconds(ctx, intervals)


def is_done_for_day(seat_id: int, class_id: str, *, ctx) -> bool:
    """Whether the seat has already recorded ``done_for_day`` in the current
    class-local day.

    A terminal state for the day (DOM-PROD-001): once true, a fresh
    ``start_work`` for this seat/class is refused server-side
    (``_record_attendance_session_impl``) until the next canonical day. The
    single computation shared by ``get_class_attendance_status`` (page render
    and the polling endpoint) and the tap route (``/api/tap``'s own response),
    which previously computed attendance facts independently and never
    surfaced this one at all.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds(ctx)
    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.status == "inactive",
        AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
        AttendanceSession.timestamp >= day_start_utc,
        AttendanceSession.timestamp < day_end_utc,
    ).first()
    return rows is not None


def get_class_attendance_status(student, *, class_id: str, ctx=None):
    """Return PROD attendance facts for one canonical class scope."""
    if not class_id:
        raise ValueError("get_class_attendance_status requires class_id.")
    if ctx is None:
        raise ValueError("get_class_attendance_status requires CanonicalContext.")

    seat_id = getattr(ctx, "seat_id", None) or getattr(student, "id", None)
    if not seat_id:
        raise ValueError("get_class_attendance_status requires seat_id.")

    seat = Seat.query.filter(
        Seat.id == seat_id,
        Seat.class_id == class_id,
        Seat.role == 'student',
        Seat.claimed_at.isnot(None),
    ).first()
    if seat is None:
        raise ValueError("Seat is not claimed in the requested class scope.")

    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat.id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    latest = rows[-1] if rows else None
    is_active = bool(latest and latest.status == "active")

    done = is_done_for_day(seat.id, class_id, ctx=ctx)
    duration = calculate_unpaid_attendance_seconds(seat.id, class_id, ctx=ctx)
    # "Time Today" must be the day-bounded worked figure, not the unbounded
    # unpaid-since-payroll duration (which can span days if payroll has not run).
    duration_today = calculate_worked_attendance_seconds_today(
        seat.id, class_id, ctx=ctx
    )

    return {
        "active": is_active,
        "done": done,
        "duration": duration,
        "duration_today": duration_today,
        "projected_pay": None,
        "hall_pass": _derive_hall_pass_state(seat.id, class_id),
    }
