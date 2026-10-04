from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import (
    AttendanceIntervalInvalidation,
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


def class_has_claimed_student_work(class_id: str) -> bool:
    """Whether any claimed student seat of ``class_id`` has work (DOM-PROD-001 §XIII.7).

    Work is a Start Work session, open or already completed. Every session
    opens with an ``active`` row, so one such row answers both cases; elapsed
    duration plays no part. Only seats claimed *now* count: work kept on a seat
    that was later unclaimed is retained but never displayed (DOM-IDEN-002 §VIII,
    "Participation and Visibility of an Unclaimed Seat", items 2 and 4).
    Read-only and scoped by ``class_id``.
    """
    if not class_id:
        return False
    return db.session.query(
        AttendanceSession.query
        .join(Seat, Seat.id == AttendanceSession.target_seat_id)
        .filter(
            AttendanceSession.class_id == class_id,
            AttendanceSession.status == "active",
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.user_id.isnot(None),
        )
        .exists()
    ).scalar()


def _current_evaluation_day_bounds(ctx, *, reference_time_utc=None):
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=reference_time_utc,
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


@dataclass(frozen=True)
class AttendanceInterval:
    opening_event_id: int
    closing_event_id: int | None
    opened_at: object
    closed_at: object
    credited_seconds: int
    opening_mechanism: str
    closing_mechanism: str | None
    bounded_at_day_end: bool = False

    def __iter__(self):
        return iter((self.opened_at, self.closed_at))

    def as_evidence(self):
        if self.closing_event_id is None:
            raise ValueError("Settlement requires a persisted closing event.")
        return {"opening_event_id": self.opening_event_id,
                "closing_event_id": self.closing_event_id,
                "opening_timestamp": ensure_utc(self.opened_at).isoformat(),
                "closing_timestamp": ensure_utc(self.closed_at).isoformat(),
                "credited_seconds": self.credited_seconds}


def list_attendance_interval_evidence(seat_id, class_id, *, ctx, as_of_utc=None, source_limit=None):
    """Pure PROD canonical pair projection; system closes are first-class evidence."""
    if ctx.class_id != class_id:
        raise ValueError("Attendance context does not authorize this class.")
    if as_of_utc is None:
        as_of_utc = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx, primitive="current_time").canonical_now_utc
    as_of_utc = ensure_utc(as_of_utc)
    query = AttendanceSession.query.filter_by(class_id=class_id, target_seat_id=seat_id).order_by(
        AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
    if source_limit is not None:
        if type(source_limit) is not int or not 1 <= source_limit <= 2000:
            raise ValueError("INVALID_INPUT")
        query = query.limit(source_limit + 1)
    with db.session.no_autoflush:
        rows = query.all()
    if source_limit is not None and len(rows) > source_limit:
        raise ValueError("EVIDENCE_LIMIT_EXCEEDED")
    intervals, opening = [], None
    consumed_closings = set()
    for row in rows:
        if row.id in consumed_closings:
            continue
        timestamp = ensure_utc(row.timestamp)
        if timestamp > as_of_utc:
            break
        if row.status == "active":
            if opening is None:
                opening = row
            elif timestamp >= _day_end_utc(ctx, opening.timestamp):
                # An unrecorded day-end remains unproven; do not invent an ID.
                end = _day_end_utc(ctx, opening.timestamp)
                boundary_close = next((candidate for candidate in rows
                    if candidate.id not in consumed_closings and candidate.status == "inactive"
                    and ensure_utc(candidate.timestamp) == end
                    and candidate.mechanism == "system"
                    and candidate.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value), None)
                intervals.append(AttendanceInterval(opening.id, boundary_close.id if boundary_close else None,
                    ensure_utc(opening.timestamp), end,
                    _elapsed_seconds(ctx, [(ensure_utc(opening.timestamp), end)]), opening.mechanism,
                    boundary_close.mechanism if boundary_close else None, bounded_at_day_end=True))
                if boundary_close is not None:
                    consumed_closings.add(boundary_close.id)
                opening = row
        elif row.status == "inactive" and opening is not None:
            start = ensure_utc(opening.timestamp)
            if timestamp < start or timestamp > _day_end_utc(ctx, start):
                end = _day_end_utc(ctx, start)
                intervals.append(AttendanceInterval(opening.id, None, start, end,
                    _elapsed_seconds(ctx, [(start, end)]), opening.mechanism, None,
                    bounded_at_day_end=(end == _day_end_utc(ctx, start))))
                opening = None
                continue
            intervals.append(AttendanceInterval(opening.id, row.id, start, timestamp,
                _elapsed_seconds(ctx, [(start, timestamp)]), opening.mechanism, row.mechanism))
            opening = None
    if opening is not None:
        start = ensure_utc(opening.timestamp)
        end = min(as_of_utc, _day_end_utc(ctx, start))
        intervals.append(AttendanceInterval(opening.id, None, start, end,
            _elapsed_seconds(ctx, [(start, end)]), opening.mechanism, None,
            bounded_at_day_end=(end == _day_end_utc(ctx, start))))
    return tuple(rows), tuple(intervals)


def list_attendance_intervals(seat_id, class_id, *, ctx, as_of_utc=None):
    """Pure canonical pairs from one scoped source snapshot."""
    return list_attendance_interval_evidence(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)[1]


def lock_attendance_seat(seat_id, class_id):
    """Shared serialization point for all attendance and settlement writers."""
    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).with_for_update().first()
    if seat is None:
        raise ValueError("Attendance target seat must belong to the canonical class.")
    return seat


def close_due_attendance_intervals(*, ctx, seat_id, as_of_utc):
    """PROD command: append due system closures within the caller's FEAT transaction."""
    from app.services.attendance_writer_service import record_attendance_session_command
    from app.services.payroll.settings import current_daily_limit_seconds
    lock_attendance_seat(seat_id, ctx.class_id)
    now = ensure_utc(as_of_utc)
    intervals = list_attendance_intervals(seat_id, ctx.class_id, ctx=ctx, as_of_utc=now)
    created = []
    for interval in intervals:
        if interval.closing_event_id is not None:
            continue
        limit = current_daily_limit_seconds(ctx.class_id, as_of=interval.opened_at)
        day_end = _day_end_utc(ctx, interval.opened_at)
        due = day_end
        if limit:
            bounds = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx, primitive="evaluation_day_boundaries",
                reference_time_utc=interval.opened_at)
            previous = sum(i.credited_seconds for i in intervals
                if i.closing_event_id is not None and bounds.boundary_start_utc <= i.opened_at < interval.opened_at)
            remaining = max(0, int(limit) - previous)
            capped = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx, primitive="shift_timestamp",
                timestamp=interval.opened_at, elapsed_seconds=remaining,
                reference_time_utc=now).shifted_timestamp_utc
            due = min(due, capped)
        if due <= now:
            result = record_attendance_session_command(ctx=ctx, status="inactive", target_seat_id=seat_id,
                mechanism="system", reason_code=AttendanceReasonCode.DONE_FOR_DAY,
                reference_time_utc=due,
                idempotency_key=f"system-close:{interval.opening_event_id}:{due.isoformat()}")
            created.append(result.session)
    return tuple(created)


@dataclass(frozen=True)
class SeatPayrollIntervals:
    """The intervals behind :class:`SeatPayrollAttendance`, as of one instant.

    ``payable`` holds the closed, unpaid part of each session a run at that
    instant settles; each interval ends when its session closed, which is the
    instant that decides the setting that prices it (DOM-PROD-001 §XV.3).
    ``in_progress`` is the still-open session, if any. ``unprovable`` identifies
    historical overlaps excluded from estimates and blocked for settlement.
    """

    payable: tuple
    in_progress: tuple
    unprovable: tuple = ()


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

    identified = list_attendance_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    closed = [i for i in identified if i.closing_event_id is not None]
    in_progress = next((i for i in reversed(identified) if i.closing_event_id is None), None)

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
    historical, settled_pairs, legacy_times = [], set(), []
    invalid_evidence = False
    pair_evidence = {(i.opening_event_id, i.closing_event_id): i.as_evidence()
        for i in closed}
    for event in payroll_events:
        summary = event.summary_json
        if not isinstance(summary, dict):
            invalid_evidence = True
            continue
        if type(summary.get("allocation_version")) is not int or summary.get("allocation_version") != 1:
            historical.append(event)
            if summary.get("settlement_rule") != CLOSED_SESSION_SETTLEMENT_RULE:
                legacy_times.append(ensure_utc(event.recorded_at))
            continue
        try:
            shares = summary["pricing"]
            if not isinstance(shares, list) or not shares:
                raise ValueError("Missing frozen pricing shares.")
            for share in shares:
                sources = share["intervals"]
                if not isinstance(sources, list) or not sources or sum(i["credited_seconds"] for i in sources) != share["seconds"]:
                    raise ValueError("Invalid frozen membership.")
                for source in sources:
                    key = (source["opening_event_id"], source["closing_event_id"])
                    if key in settled_pairs or pair_evidence.get(key) != source:
                        raise ValueError("Unprovable frozen source pair.")
                    settled_pairs.add(key)
        except (KeyError, TypeError, ValueError, AttributeError):
            invalid_evidence = True
    paid_through = max((ensure_utc(e.recorded_at) for e in historical), default=None)
    if invalid_evidence:
        return SeatPayrollIntervals(payable=(), in_progress=(), unprovable=tuple(identified))

    invalidated_pairs = set(db.session.query(AttendanceIntervalInvalidation.opening_event_id, AttendanceIntervalInvalidation.closing_event_id).filter_by(class_id=class_id, target_seat_id=seat_id).all())
    payable, unprovable = [], []
    for interval in closed:
        start, end = interval
        if (interval.opening_event_id, interval.closing_event_id) in settled_pairs or (interval.opening_event_id, interval.closing_event_id) in invalidated_pairs:
            continue
        if paid_through is not None and end <= paid_through:
            continue
        if any(start < instant < end for instant in legacy_times):
            unprovable.append(interval)
            continue
        if end > start:
            payable.append(interval)

    open_intervals = []
    if in_progress is not None:
        start, end = in_progress
        if any(start < instant < end for instant in legacy_times):
            unprovable.append(in_progress)
            start = end
        if end > start:
            open_intervals.append((start, end))

    return SeatPayrollIntervals(payable=tuple(payable), in_progress=tuple(open_intervals), unprovable=tuple(unprovable))


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


def is_done_for_day(seat_id: int, class_id: str, *, ctx, reference_time_utc=None) -> bool:
    """Whether the seat has already recorded ``done_for_day`` in the current
    class-local day.

    A terminal state for the day (DOM-PROD-001): once true, a fresh
    ``start_work`` for this seat/class is refused server-side
    (``record_attendance_session_command``) until the next canonical day. The
    single computation shared by ``get_class_attendance_status`` (page render
    and the polling endpoint) and the tap route (``/api/tap``'s own response),
    which previously computed attendance facts independently and never
    surfaced this one at all.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds(
        ctx, reference_time_utc=reference_time_utc
    )
    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.status == "inactive",
        AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
        AttendanceSession.timestamp >= day_start_utc,
        AttendanceSession.timestamp < day_end_utc,
    ).all()
    if not rows:
        return False
    if any(ensure_utc(row.timestamp) != day_start_utc for row in rows):
        return True
    # The prior day's exact end is today's start. Its persisted closing event
    # belongs to the originating pair, not today's terminal state (§XV.7).
    # Exclude only proven prior-day pairs; orphan/current-day closures still deny.
    prior_day_closings = {
        interval.closing_event_id
        for interval in list_attendance_intervals(
            seat_id, class_id, ctx=ctx, as_of_utc=day_start_utc
        )
        if interval.opened_at < day_start_utc
    }
    return any(row.id not in prior_day_closings for row in rows)



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
