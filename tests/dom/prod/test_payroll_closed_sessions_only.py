"""Regression: payroll settles closed, unpaid sessions only (DOM-PROD-001 §VI.3).

Production incident, 2026-09-28: a teacher ran payroll while students were still
clocked in, then ran it again later. The second run paid almost nobody. The
reader filtered attendance to rows at or after the seat's last payroll event,
which dropped the ``active`` row that opened a still-running session, so the part
of that session after the first run had no start and was never paid, even after
the student clocked out.

The rule now: a session is payable once it has closed after the seat's last
payroll event, and the run in whose window it closes pays all of it. An open
session is never payable, so no session is split across runs and none is paid
twice. A run with nothing closed and unpaid is refused.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    PayrollCycleCompletion,
    PayrollEvent,
    Transaction,
)
from app.scheduled_tasks import run_automatic_payroll_job
from app.services.attendance_service import (
    CLOSED_SESSION_SETTLEMENT_RULE,
    calculate_payable_attendance_seconds,
    calculate_seat_payroll_attendance,
)
from app.services.context_resolver import CanonicalContext
from app.services.ledger_posting_service import create_pending_transaction
from app.services.payroll.schedule import next_payroll_date
from app.services.payroll.settings import (
    first_payroll_setting,
    pay_rate_per_second,
    save_payroll_setting,
)
from app.services.payroll.settlement import (
    NoPayableAttendanceError,
    settle_class_payroll_cycle,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

# 10:00 PDT on one class-local day; every instant below stays inside that day.
T0 = datetime(2026, 8, 26, 17, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _attendance(classroom, seat_id: int, *rows) -> None:
    """Append raw timeline rows: ``("active"|"inactive", instant)``.

    Written directly (as the other payroll fixtures do) so a test can produce
    timelines the FEAT would normalise, such as two ``active`` rows in a row.
    """
    cid = classroom.class_id
    with FEATContext(
        "FEAT-PROD-001", correlation_id=f"att:{uuid4()}", idempotency_key=f"att:{uuid4()}"
    ):
        for status, instant in rows:
            db.session.add(AttendanceSession(
                target_seat_id=seat_id, class_id=cid,
                actor_seat_id=classroom.teacher_seat_id, status=status,
                reason_code="start_work" if status == "active" else "done_for_day",
                timestamp=instant,
            ))
        db.session.flush()


def _run(cid: str, boundary: datetime):
    cycle_id = str(uuid4())
    with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
        return settle_class_payroll_cycle(
            class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=boundary,
            run_mechanism="TEACHER",
        )


def _paid(cid: str, seat_id: int) -> Decimal:
    rows = Transaction.query.filter_by(class_id=cid, seat_id=seat_id, type="payroll").all()
    return sum((Decimal(row.amount) for row in rows), Decimal("0.00"))


def _pay_for(cid: str, minutes: int) -> Decimal:
    # The sessions here close before the provisioned setting was recorded, so
    # they are priced by the class's first setting (DOM-PROD-001 §XV.3).
    rate = pay_rate_per_second(first_payroll_setting(cid))
    return (Decimal(minutes * 60) * rate).quantize(Decimal("0.01"))


def _payroll_events(cid: str, seat_id: int):
    return PayrollEvent.query.filter_by(
        class_id=cid, target_seat_id=seat_id, payroll_event_type="payroll"
    ).all()


def test_DOM_PROD_001__session_open_at_a_run_is_paid_in_full_by_the_run_after_it_closes(app):
    """The 2026-09-28 incident: pay mid-session, clock out, pay again."""
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    working, returned = classroom.students[0].seat.id, classroom.students[1].seat.id

    _attendance(classroom, working, ("active", _at(0)))
    # `returned` finishes one session, then starts another before the first run
    # (production seat 161's shape: paid at the run, but already working again).
    _attendance(
        classroom, returned,
        ("active", _at(0)), ("inactive", _at(20)), ("active", _at(25)),
    )

    first = _run(cid, _at(30))
    # Only closed work is settled: the still-working seat gets no event at all.
    assert first.settled_seat_ids == [returned]
    assert _payroll_events(cid, working) == []
    assert _paid(cid, returned) == _pay_for(cid, 20)

    _attendance(classroom, working, ("inactive", _at(50)))
    _attendance(classroom, returned, ("inactive", _at(55)))
    preview = calculate_payable_attendance_seconds(
        working, cid, ctx=classroom_ctx(classroom), as_of_utc=_at(60)
    )
    second = _run(cid, _at(60))

    # Each session is paid whole, exactly once, by the run after it closes,
    # including the part that ran before the first run. The preview named the
    # amount beforehand.
    assert sorted(second.settled_seat_ids) == sorted([working, returned])
    assert preview == 50 * 60
    assert _paid(cid, working) == _pay_for(cid, 50)
    assert _paid(cid, returned) == _pay_for(cid, 20) + _pay_for(cid, 30)


def test_DOM_PROD_001__run_with_nothing_closed_and_unpaid_is_refused(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    seat_id = classroom.students[0].seat.id
    _attendance(classroom, seat_id, ("active", _at(0)))

    with pytest.raises(NoPayableAttendanceError):
        _run(cid, _at(30))
    db.session.rollback()
    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0

    # Once that session is paid, an immediate second run has nothing to settle.
    _attendance(classroom, seat_id, ("inactive", _at(40)))
    _run(cid, _at(45))
    with pytest.raises(NoPayableAttendanceError):
        _run(cid, _at(46))
    db.session.rollback()
    assert len(_payroll_events(cid, seat_id)) == 1


def test_DOM_PROD_001__repeated_active_row_continues_the_open_session(app):
    """A second ``active`` while open must not restart the session and drop time."""
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    seat_id = classroom.students[0].seat.id
    _attendance(
        classroom, seat_id,
        ("active", _at(0)), ("active", _at(10)), ("inactive", _at(30)),
    )

    attendance = calculate_seat_payroll_attendance(
        seat_id, cid, ctx=classroom_ctx(classroom), as_of_utc=_at(40)
    )
    assert attendance.payable_seconds == 30 * 60
    assert attendance.in_progress_seconds == 0


def test_DOM_PROD_001__run_stamps_the_closed_session_rule(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    seat_id = classroom.students[0].seat.id
    _attendance(classroom, seat_id, ("active", _at(0)), ("inactive", _at(10)))

    _run(cid, _at(20))

    (event,) = _payroll_events(cid, seat_id)
    assert event.summary_json["settlement_rule"] == CLOSED_SESSION_SETTLEMENT_RULE


def test_DOM_PROD_001__legacy_run_during_a_session_is_not_paid_twice(app):
    """Transition: a pre-rule run paid an open session up to its own instant.

    When that session closes, only the part after the legacy run is still owed.
    """
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    seat_id = classroom.students[0].seat.id
    _attendance(classroom, seat_id, ("active", _at(0)))

    # A payroll event written by the earlier rule carries no settlement_rule.
    # FEAT-PROD-003 no longer writes one (it derives every payroll amount), so
    # the historical row and its ledger credit are written as a fixture.
    key = f"legacy:{uuid4()}"
    with FEATContext("FEAT-PROD-003", idempotency_key=key):
        legacy = PayrollEvent(
            class_id=cid, target_seat_id=seat_id, actor_seat_id=classroom.teacher_seat_id,
            correlation_id=key, idempotency_key=key,
            policy_uuid=first_payroll_setting(cid).policy_uuid, mechanism="TEACHER",
            payroll_event_type="payroll", recorded_at=_at(30),
            summary_json={"source": "class_payroll_settlement"},
        )
        db.session.add(legacy)
        create_pending_transaction(
            seat_id=seat_id, class_id=cid, target_seat_id=seat_id,
            actor_seat_id=classroom.teacher_seat_id, mechanism="teacher",
            amount=_pay_for(cid, 30), account_type="checking", type="payroll",
            description="Legacy payroll", idempotency_key=key,
        )
        db.session.flush()
    assert "settlement_rule" not in legacy.summary_json

    _attendance(classroom, seat_id, ("inactive", _at(60)))
    _run(cid, _at(70))

    # 30 minutes paid by the legacy run + the 30 minutes after it, not 60 more.
    assert _paid(cid, seat_id) == _pay_for(cid, 30) + _pay_for(cid, 30)


def test_DOM_PROD_001__run_payroll_route_explains_a_refused_run(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = classroom.class_id
    now = utc_now()
    _attendance(classroom, classroom.students[0].seat.id, ("active", now - timedelta(minutes=5)))

    response = client.post(
        "/admin/run_payroll",
        data={"idempotency_token": "tok-open-only"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 409
    assert b"Nothing to pay yet" in response.data
    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0
    assert PayrollCycleCompletion.query.filter_by(class_id=cid).count() == 0


def test_DOM_PROD_001__automatic_payroll_waits_for_a_closed_session(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    seat_id = classroom.students[0].seat.id
    now = utc_now()
    occurrence = now - timedelta(minutes=1)
    # The first pay date has arrived; the provisioned default defines no
    # boundary, so this schedule is in force at once.
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"sched:{cid}"):
        save_payroll_setting(
            class_id=cid,
            settings_data={"first_pay_date": occurrence, "payroll_frequency_days": 14},
        )
    db.session.commit()
    _attendance(classroom, seat_id, ("active", now - timedelta(minutes=20)))

    run_automatic_payroll_job()

    # Deferred, not failed: nothing written, and the occurrence is still due.
    assert PayrollCycleCompletion.query.filter_by(class_id=cid).count() == 0
    assert next_payroll_date(cid) == occurrence

    _attendance(classroom, seat_id, ("inactive", now - timedelta(minutes=2)))
    run_automatic_payroll_job()

    assert PayrollCycleCompletion.query.filter_by(class_id=cid).count() == 1
    assert len(_payroll_events(cid, seat_id)) == 1
    assert next_payroll_date(cid) > occurrence


def classroom_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user_id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id,
        actor_role="teacher",
    )
