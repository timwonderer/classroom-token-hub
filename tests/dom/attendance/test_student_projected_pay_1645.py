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

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import app.utils.canonical_temporal_resolver as resolver_module
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceSession
from app.services.attendance_service import get_class_attendance_status
from app.services.context_resolver import CanonicalContext
from contextlib import contextmanager
from tests.helpers.class_domain import put_payroll_setting_in_force
from tests.helpers.classroom_initializer import initialize

MON = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)  # 09:00 PDT


@contextmanager
def _clock(monkeypatch, instant):
    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _closed_work(classroom, seat_id: int, start, minutes: int) -> None:
    """A closed (clocked in then out) interval, written as a timeline fixture."""
    with FEATContext(
        "FEAT-PROD-001", correlation_id=f"att:{uuid4()}", idempotency_key=f"att:{uuid4()}"
    ):
        for status, instant in (("active", start), ("inactive", start + timedelta(minutes=minutes))):
            db.session.add(AttendanceSession(
                target_seat_id=seat_id, class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat_id, status=status,
                reason_code="start_work" if status == "active" else "done_for_day",
                timestamp=instant,
            ))
        db.session.flush()
    db.session.commit()


def test_projected_pay_is_zero_with_no_unpaid_work(client, app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _student_ctx(classroom, student)

    with app.app_context(), _clock(monkeypatch, MON):
        status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["projected_pay"] == Decimal("0.00")


def test_projected_pay_prices_closed_work_at_the_fixture_rate(client, app, monkeypatch):
    """chemistry_p1 provisions PayrollSettings.pay_rate = $0.50/min (canonical_classroom.py).

    15 minutes of closed, unpaid work -> 15 * 0.50 = $7.50.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with _clock(monkeypatch, MON):
            _closed_work(classroom, seat_id, MON, 15)

        with _clock(monkeypatch, MON + timedelta(minutes=30)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["projected_pay"] == Decimal("7.50")


def test_projected_pay_prices_closed_work_at_the_rate_in_force_when_it_closed(client, app, monkeypatch):
    """A rate change saved after the work closed must not reprice it (DOM-CLASS-003
    §VII, DOM-PROD-001 §XV.3) — the same rule a real payroll run follows, which
    this estimate must agree with so the preview and the payout never disagree."""
    with app.app_context():
        with _clock(monkeypatch, MON):
            classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with _clock(monkeypatch, MON):
            _closed_work(classroom, seat_id, MON, 15)  # active MON -> inactive MON+15, at $0.50/min = $7.50

        # Rate change saved strictly AFTER the work closed (MON+15).
        with _clock(monkeypatch, MON + timedelta(minutes=20)):
            put_payroll_setting_in_force(classroom.class_id, pay_rate=Decimal("10.00"))

        with _clock(monkeypatch, MON + timedelta(minutes=30)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    # Not $150.00 (15 min * $10.00/min) — the closed session is still priced at
    # the $0.50/min rate in force when it closed.
    assert status["projected_pay"] == Decimal("7.50")


def test_projected_pay_prices_the_open_session_at_the_rate_in_force_now(client, app, monkeypatch):
    """The still-open session is estimated as if it closed now, so a rate change
    while it is in progress changes the estimate (docs/user-guides: "If the rate
    changes... the number changes with it") — unlike already-closed work above."""
    with app.app_context():
        with _clock(monkeypatch, MON):
            classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    ctx = _student_ctx(classroom, student)

    with app.app_context():
        with _clock(monkeypatch, MON):
            record_attendance_session(
                ctx=ctx,
                status="active",
                idempotency_key=f"test:projected-pay:open:{classroom.class_id}:{seat_id}",
                reference_time_utc=MON,
            )

        with _clock(monkeypatch, MON + timedelta(minutes=5)):
            put_payroll_setting_in_force(classroom.class_id, pay_rate=Decimal("2.00"))

        # 10 minutes elapsed on the still-open session, priced at the $2.00/min
        # rate in force right now (not the fixture's original $0.50/min).
        with _clock(monkeypatch, MON + timedelta(minutes=10)):
            status = get_class_attendance_status(student, class_id=classroom.class_id, ctx=ctx)

    assert status["active"] is True
    assert status["projected_pay"] == Decimal("20.00")
