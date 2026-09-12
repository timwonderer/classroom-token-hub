"""Regression: a session left open across a day boundary is closed on ITS day.

DOM-PROD-001 §312 requires every ``active`` session to terminate by end of day in
the canonical class timezone, with the ``inactive`` row "recorded using the same
date as the originating ``active`` entry". §314 separately requires a session that
reaches the configured daily limit to close at the limit.

``enforce_daily_limits_job`` implemented only §314, and it evaluated every open
session against *today's* day boundary — clamping the interval start with
``max(active_start, today_start)``. Two defects followed whenever the scheduler
missed a midnight (a stopped dev server, a restart, any outage spanning a day):

1. The prior day's session never received its end-of-day row at all. On the next
   run it was re-read as a session that began at today's 00:00, and the closing
   row was dated TODAY — which then trips the ``done_today`` gate in
   ``app/feats/prod.py`` and locks the student out of working today over a
   session opened yesterday.
2. A class with no configured daily limit was skipped entirely (``if not
   daily_limit: continue``), so §312 was never enforced for it by this job.

The job now evaluates each open session inside the canonical day of its own
``active`` row, and applies §312 whether or not a limit is configured.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from app import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession
from app.scheduled_tasks import enforce_daily_limits_job
from app.services.context_resolver import CanonicalContext
from app.services.payroll_settings_service import upsert_payroll_settings
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)
from tests.helpers.classroom_initializer import initialize


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _now_utc(classroom):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_teacher_ctx(classroom),
        primitive="current_time",
    ).canonical_now_utc


def _day_bounds(classroom, reference_time_utc):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_teacher_ctx(classroom),
        primitive="evaluation_day_boundaries",
        reference_time_utc=reference_time_utc,
    )


def _tap_in(classroom, seat, *, at):
    record_attendance_session(
        ctx=_teacher_ctx(classroom),
        target_seat_id=seat.id,
        actor_seat_id=classroom.teacher_seat.id,
        mechanism="teacher",
        status="active",
        idempotency_key=f"stale_sweep:active:{classroom.class_id}:{seat.id}",
        reference_time_utc=at,
    )
    db.session.commit()


def _configure_daily_limit(class_id, *, daily_limit_hours, idempotency_key):
    with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
        upsert_payroll_settings(
            class_id=class_id,
            settings_data={
                "block": None,
                "settings_mode": "simple",
                "daily_limit_hours": daily_limit_hours,
                "pay_rate": 0.25,
                "payroll_frequency_days": 14,
            },
        )
    db.session.commit()


def _aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def _closing_row(classroom, seat):
    return (
        AttendanceSession.query.filter_by(
            target_seat_id=seat.id,
            class_id=classroom.class_id,
            status="inactive",
        )
        .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
        .first()
    )


def test_DOM_PROD_001__stale_session_closes_at_its_own_day_end(client):
    """No daily limit configured — §312 still applies, unconditionally."""
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat

    # Tapped in two days ago and never tapped out: the scheduler was down.
    tap_in_at = _now_utc(classroom) - timedelta(days=2)
    _tap_in(classroom, seat, at=tap_in_at)

    enforce_daily_limits_job()

    close_row = _closing_row(classroom, seat)
    assert close_row is not None, "a session open across a day boundary must be closed"
    assert close_row.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value
    assert close_row.mechanism == "system"
    # Dated to the end of the ORIGINATING day, not to today.
    assert _aware(close_row.timestamp) == _day_bounds(classroom, tap_in_at).boundary_end_utc


def test_DOM_PROD_001__stale_session_limit_applies_within_its_own_day(client):
    """With a limit configured, §314's cap is measured from the real tap-in."""
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    daily_limit_hours = 1.0

    _configure_daily_limit(
        classroom.class_id,
        daily_limit_hours=daily_limit_hours,
        idempotency_key="stale_sweep:limit",
    )
    tap_in_at = _now_utc(classroom) - timedelta(days=2)
    _tap_in(classroom, seat, at=tap_in_at)

    enforce_daily_limits_job()

    close_row = _closing_row(classroom, seat)
    assert close_row is not None
    # The limit is measured from the actual tap-in, NOT from today's midnight.
    assert _aware(close_row.timestamp) == tap_in_at + timedelta(hours=daily_limit_hours)


def test_DOM_PROD_001__stale_closure_does_not_block_working_today(client):
    """The closing row must not land on today and trip the done_today gate."""
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat

    # A limit is configured so the §314 path is live: the pre-fix job reached it,
    # clamped the interval to TODAY's midnight, and dated the closure to today.
    _configure_daily_limit(
        classroom.class_id,
        daily_limit_hours=1.0,
        idempotency_key="stale_sweep:blocks_today",
    )
    tap_in_at = _now_utc(classroom) - timedelta(days=2)
    _tap_in(classroom, seat, at=tap_in_at)

    enforce_daily_limits_job()

    now_utc = _now_utc(classroom)
    today = _day_bounds(classroom, now_utc)
    done_today = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat.id,
        AttendanceSession.class_id == classroom.class_id,
        AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
        AttendanceSession.timestamp >= today.boundary_start_utc,
        AttendanceSession.timestamp < today.boundary_end_utc,
    ).count()
    assert done_today == 0, "yesterday's closure must not mark the student done today"

    # And the student can actually start work today.
    record_attendance_session(
        ctx=_teacher_ctx(classroom),
        target_seat_id=seat.id,
        actor_seat_id=classroom.teacher_seat.id,
        mechanism="teacher",
        status="active",
        idempotency_key=f"stale_sweep:today:{classroom.class_id}:{seat.id}",
        reference_time_utc=now_utc,
    )
    db.session.commit()


def test_DOM_PROD_001__session_opened_today_and_under_limit_is_left_open(client):
    """The sweep must not close a live session that is still inside its own day."""
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat

    _configure_daily_limit(
        classroom.class_id,
        daily_limit_hours=8.0,
        idempotency_key="stale_sweep:generous_limit",
    )
    now_utc = _now_utc(classroom)
    # Anchored to today's boundary so the seed stays "earlier today" at any hour.
    tap_in_at = max(now_utc - timedelta(minutes=30), _day_bounds(classroom, now_utc).boundary_start_utc)
    _tap_in(classroom, seat, at=tap_in_at)

    enforce_daily_limits_job()

    assert _closing_row(classroom, seat) is None
