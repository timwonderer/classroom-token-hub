"""Regression: "Time Today" must be day-bounded, not unpaid-since-payroll.

The student dashboard labels a duration "Time Today". It was being fed the
unbounded unpaid-since-payroll figure, so a session that began before the
current class-local day (e.g. a student who never clocked out yesterday, or a
class where payroll has not run) reported many hours — 21h 44m in the field
report — even though only minutes had elapsed today.

`calculate_worked_attendance_seconds_today` and the `duration_today` key on
`get_class_attendance_status` must count only the current evaluation day, clipped
at the canonical now, while `duration` is the unpaid figure, which ends a session
at the end of the day it began.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from types import SimpleNamespace

from app.feats.prod import record_attendance_session
from app.services.attendance_service import (
    _current_evaluation_day_bounds,
    calculate_worked_attendance_seconds_today,
    get_class_attendance_status,
)
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
)
from tests.helpers.classroom_initializer import initialize


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def test_time_today_excludes_time_before_today(client):
    """An active session started 3h before today's start counts only today.

    duration_today counts only from the class-local day start to now; the unpaid
    duration counts the session up to the end of the day it began.
    """
    app = client.application
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        eval_ctx = SimpleNamespace(class_id=classroom.class_id)
        day_start_utc, _day_end_utc = _current_evaluation_day_bounds(eval_ctx)
        now = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=eval_ctx,
            primitive="current_time",
        ).canonical_now_utc

        # Clock in 3 hours BEFORE today's evaluation day began, and stay active.
        active_start = day_start_utc - timedelta(hours=3)
        record_attendance_session(
            ctx=ctx,
            status="active",
            idempotency_key=f"test:time-today:active:{classroom.class_id}:{student.seat.id}",
            reference_time_utc=active_start,
        )

        status = get_class_attendance_status(
            student, class_id=classroom.class_id, ctx=ctx
        )

        seconds_since_day_start = int((now - day_start_utc).total_seconds())

        # duration_today counts only today's slice (day_start -> now), not the
        # 3h that elapsed yesterday.
        assert status["duration_today"] <= seconds_since_day_start + 2
        # The unpaid figure follows DOM-PROD-001 §VI.1: the session ended at the
        # end of the day it began, so exactly the 3h before today's start is owed.
        assert status["duration"] == 3 * 3600

        # The standalone helper agrees with the status dict.
        assert (
            calculate_worked_attendance_seconds_today(
                student.seat.id, classroom.class_id, ctx=ctx
            )
            == status["duration_today"]
        )

        # Day-bounded value can never exceed 24h.
        assert status["duration_today"] <= 24 * 3600
