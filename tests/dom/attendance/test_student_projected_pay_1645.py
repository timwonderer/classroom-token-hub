"""#1645: the student dashboard and ``/api/student-status`` always showed
``projected_pay: None``.

``get_class_attendance_status`` must price unpaid attendance the same way
``app/services/payroll/pricing.py`` prices a real payroll run (DOM-PROD-001
§XV.3): closed-but-unpaid work at the payroll setting in force when it
closed, and the still-open session as if it closed now, at whatever setting
is in force now. A naive "current rate times all unpaid time" implementation
would misprice already-closed work after a mid-cycle rate change — these
tests pin that distinction down.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.feats.prod import record_attendance_session
from app.services.attendance_service import get_class_attendance_status
from app.services.context_resolver import CanonicalContext
from tests.helpers import temporal
from tests.helpers.class_domain import put_payroll_setting_in_force
from tests.helpers.classroom_initializer import initialize

MON = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)  # 09:00 PDT


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _closed_work(ctx: CanonicalContext, classroom, start, minutes: int) -> None:
    """A closed (clocked in then out) interval, recorded through the attendance command."""
    record_attendance_session(
        ctx=ctx, status="active", actor_seat_id=classroom.teacher_seat_id,
        idempotency_key=f"att:{uuid4()}", reference_time_utc=start,
    )
    record_attendance_session(
        ctx=ctx, status="inactive", reason="done_for_day",
        actor_seat_id=classroom.teacher_seat_id,
        idempotency_key=f"att:{uuid4()}",
        reference_time_utc=temporal.shifted(start, minutes=minutes),
    )


def test_projected_pay_is_zero_with_no_unpaid_work(client, app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _student_ctx(classroom, student)

    with app.app_context(), temporal.pinned_clock(MON):
        status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["projected_pay"] == Decimal("0.00")


def test_projected_pay_prices_closed_work_at_the_fixture_rate(client, app):
    """chemistry_p1 provisions PayrollSettings.pay_rate = $0.50/min (canonical_classroom.py).

    15 minutes of closed, unpaid work -> 15 * 0.50 = $7.50.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with temporal.pinned_clock(MON):
            _closed_work(ctx, classroom, MON, 15)

        with temporal.pinned_clock(temporal.shifted(MON, minutes=30)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["projected_pay"] == Decimal("7.50")


def test_projected_pay_prices_closed_work_at_the_rate_in_force_when_it_closed(client, app):
    """A rate change saved after the work closed must not reprice it (DOM-CLASS-003
    §VII, DOM-PROD-001 §XV.3) — the same rule a real payroll run follows, which
    this estimate must agree with so the preview and the payout never disagree."""
    with app.app_context():
        with temporal.pinned_clock(MON):
            classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with temporal.pinned_clock(MON):
            _closed_work(ctx, classroom, MON, 15)  # active MON -> inactive MON+15, at $0.50/min = $7.50

        # Rate change saved strictly AFTER the work closed (MON+15).
        with temporal.pinned_clock(temporal.shifted(MON, minutes=20)):
            put_payroll_setting_in_force(classroom.class_id, pay_rate=Decimal("10.00"))

        with temporal.pinned_clock(temporal.shifted(MON, minutes=30)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    # Not $150.00 (15 min * $10.00/min) — the closed session is still priced at
    # the $0.50/min rate in force when it closed.
    assert status["projected_pay"] == Decimal("7.50")


def test_projected_pay_prices_the_open_session_at_the_rate_in_force_now(client, app):
    """The still-open session is estimated as if it closed now, so a rate change
    while it is in progress changes the estimate (docs/user-guides: "If the rate
    changes... the number changes with it") — unlike already-closed work above."""
    with app.app_context():
        with temporal.pinned_clock(MON):
            classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with temporal.pinned_clock(MON):
            record_attendance_session(
                ctx=ctx,
                status="active",
                idempotency_key=f"test:projected-pay:open:{classroom.class_id}:{seat_id}",
                reference_time_utc=MON,
            )

        with temporal.pinned_clock(temporal.shifted(MON, minutes=5)):
            put_payroll_setting_in_force(classroom.class_id, pay_rate=Decimal("2.00"))

        # 10 minutes elapsed on the still-open session, priced at the $2.00/min
        # rate in force right now (not the fixture's original $0.50/min).
        with temporal.pinned_clock(temporal.shifted(MON, minutes=10)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["active"] is True
    assert status["projected_pay"] == Decimal("20.00")
