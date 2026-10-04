"""Prior-day canonical closures must not terminate the following class day."""
from datetime import timedelta

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession
from app.services.attendance_service import is_done_for_day, list_attendance_intervals
from app.services.context_resolver import CanonicalContext
from app.services.payroll.settlement import settle_class_payroll_cycle
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver, ensure_utc
from tests.helpers.class_domain import put_payroll_setting_in_force
from tests.helpers.classroom_initializer import initialize


def _context(classroom, student=False):
    seat = classroom.students[0].seat if student else classroom.teacher_seat
    user = classroom.students[0].user if student else classroom.teacher_user
    return CanonicalContext(user_id=user.id, class_id=classroom.class_id,
                            seat_id=seat.id, actor_role="student" if student else "teacher")


def _now_and_bounds(ctx):
    now = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx, primitive="current_time").canonical_now_utc
    bounds = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx, primitive="evaluation_day_boundaries",
        reference_time_utc=now)
    return now, bounds


def test_payroll_prior_day_close_preserves_pair_and_allows_repeated_next_day_starts(app):
    classroom = initialize("chemistry_p1", app)
    teacher, student = _context(classroom), _context(classroom, student=True)
    put_payroll_setting_in_force(classroom.class_id, pay_rate=0.25,
                                max_time_per_day=None)
    now, bounds = _now_and_bounds(student)
    opened = record_attendance_session(ctx=student, status="active",
        reference_time_utc=bounds.boundary_start_utc - timedelta(hours=2),
        idempotency_key="overnight:start")
    opening = opened.session
    frozen = {column.name: getattr(opening, column.name)
              for column in AttendanceSession.__table__.columns}
    with FEATContext("FEAT-PROD-004", idempotency_key="overnight:payroll"):
        result = settle_class_payroll_cycle(class_id=classroom.class_id,
            payroll_cycle_id="overnight-payroll", boundary_utc=now,
            run_mechanism="TEACHER", actor_ctx=teacher)
    assert result.settled_seat_ids == [student.seat_id]
    closure = AttendanceSession.query.filter_by(class_id=classroom.class_id,
        target_seat_id=student.seat_id, status="inactive").one()
    assert ensure_utc(closure.timestamp) == bounds.boundary_start_utc
    assert closure.mechanism == "system"
    assert closure.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value
    pair = list_attendance_intervals(student.seat_id, classroom.class_id,
                                    ctx=student, as_of_utc=now)[0]
    assert (pair.opening_event_id, pair.closing_event_id) == (opening.id, closure.id)
    assert pair.credited_seconds == 7200
    before = AttendanceSession.query.count()
    assert not is_done_for_day(student.seat_id, classroom.class_id, ctx=student)
    assert AttendanceSession.query.count() == before  # terminal-state read is pure
    for index in range(2):
        record_attendance_session(ctx=student, status="active",
            hall_pass_id=f"today:break:{index - 1}" if index else None,
            reference_time_utc=now + timedelta(seconds=index * 60),
            idempotency_key=f"today:start:{index}")
        record_attendance_session(ctx=student, status="inactive",
            reason_code=AttendanceReasonCode.HALL_PASS,
            hall_pass_id=f"today:break:{index}",
            reference_time_utc=now + timedelta(seconds=index * 60 + 30),
            idempotency_key=f"today:break:{index}")
    db.session.refresh(opening)
    assert {column.name: getattr(opening, column.name)
            for column in AttendanceSession.__table__.columns} == frozen
    assert ensure_utc(closure.timestamp) == bounds.boundary_start_utc
    assert not is_done_for_day(student.seat_id, classroom.class_id, ctx=student)


@pytest.mark.parametrize("at_boundary", [False, True])
def test_current_day_or_unpaired_midnight_terminal_event_still_denies_start(app, at_boundary):
    classroom = initialize("chemistry_p1", app)
    ctx = _context(classroom, student=True)
    now, bounds = _now_and_bounds(ctx)
    at = bounds.boundary_start_utc if at_boundary else now
    if not at_boundary:
        record_attendance_session(ctx=ctx, status="active",
            reference_time_utc=at, idempotency_key="today:active")
    record_attendance_session(ctx=ctx, status="inactive",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,
        reference_time_utc=at, idempotency_key="today:done")
    assert is_done_for_day(ctx.seat_id, classroom.class_id, ctx=ctx)
    before = AttendanceSession.query.count()
    with pytest.raises(ValueError, match="done for the day"):
        record_attendance_session(ctx=ctx, status="active",
            reference_time_utc=now + timedelta(seconds=1), idempotency_key="today:denied")
    assert AttendanceSession.query.count() == before
