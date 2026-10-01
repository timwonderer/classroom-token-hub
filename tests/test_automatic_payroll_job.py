"""Slice 8.3f — automatic (scheduled) payroll.

Automatic payroll is a second initiation mechanism for the same canonical
economic-cycle completion; the scheduler owns only "is this class due now?" and
then calls ``complete_payroll_cycle``. These tests prove:

* a due class runs the full lifecycle through FEAT-PROD-004 (events + ITR record +
  completion anchor keyed by the scheduled occurrence);
* the derived next payroll date advances so the class is no longer due, and a
  second job tick is inert (DOM-PROD-001 §XV.5: the date is derived from the
  run's SYSTEM payroll events, never stored);
* the scheduled occurrence is the deterministic command identity: replaying the
  same occurrence resolves the completed run and reproduces nothing.

Nothing is activated at the boundary: a change saved for the next cycle is an
effective-dated row that is in force from its date (DOM-CLASS-003 §VII).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    InterpretationCycleRecord,
    PayrollEvent,
)
from app.scheduled_tasks import run_automatic_payroll_job
from app.services.payroll import schedule as schedule_module
from app.services.payroll.cycle_completion import resolve_completed_run
from app.services.payroll.schedule import class_timezone_name, next_payroll_date
from tests.helpers.class_domain import put_payroll_setting_in_force
from app.utils import canonical_temporal_resolver as resolver_module
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _local_midnight(cid, instant):
    """Class-local midnight of ``instant``'s day: a pay date as the settings form
    stores it, and the grid the anchored schedule runs on (SPEC-TIME-001 §IX.12)."""
    from types import SimpleNamespace
    from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION, canonical_execution_context=SimpleNamespace(class_id=cid),
        primitive="evaluation_day_boundaries", reference_time_utc=instant,
    ).boundary_start_utc


def _local_midnight_days_after(cid, instant, days):
    """Class-local midnight ``days`` calendar days after ``instant``'s local day,
    in UTC. Not ``instant + timedelta(days=...)``: across a DST change local
    midnight is an hour more or less than a multiple of 24h away."""
    tz = ZoneInfo(class_timezone_name(cid))
    local_day = instant.astimezone(tz).date() + timedelta(days=days)
    return datetime.combine(local_day, time.min, tzinfo=tz).astimezone(timezone.utc)


def _seed_due_class(classroom, *, due=True):
    cid = classroom.class_id
    student = classroom.students[0]
    now = utc_now()
    occurrence = _local_midnight(cid, now if due else now + timedelta(days=7))

    # The schedule: the first pay date is the occurrence (due, or a week out).
    put_payroll_setting_in_force(cid, first_pay_date=occurrence, pay_schedule_type="biweekly")

    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid,
            actor_seat_id=classroom.teacher_seat_id, reason_code="start_work",
            timestamp=now - timedelta(minutes=30),
        ))
        # Closed: payroll settles finished sessions only (DOM-PROD-001 §VI.3).
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid,
            actor_seat_id=classroom.teacher_seat_id, status="inactive",
            reason_code="done_for_day", timestamp=now - timedelta(minutes=10),
        ))
        db.session.flush()

    return cid, occurrence


@contextmanager
def _pinned_clock(monkeypatch, instant):
    """Moves the resolver's clock (the one application code reads) to start at
    ``instant``. It keeps ticking, so rows stamped in sequence stay distinct."""
    offset = instant - datetime.now(timezone.utc)

    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            moved = datetime.now(timezone.utc) + offset
            return moved.astimezone(tz) if tz else moved.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


def test_due_class_runs_full_lifecycle_and_advances_next_date(app):
    _run_full_lifecycle_and_assert_next_date(app)


def test_next_date_is_class_local_midnight_across_a_dst_change(app, monkeypatch):
    """The run 7 days before America/Los_Angeles leaves daylight time
    (2026-11-01): the next payday is local midnight 14 calendar days on, which is
    14 days and one hour later in UTC."""
    with _pinned_clock(monkeypatch, datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc)):
        _run_full_lifecycle_and_assert_next_date(app)


def _run_full_lifecycle_and_assert_next_date(app):
    classroom = initialize("chemistry_p1", app)
    cid, occurrence = _seed_due_class(classroom, due=True)

    run_automatic_payroll_job()

    key = f"auto-payroll:{cid}:{occurrence.isoformat()}"
    cycle_id = resolve_completed_run(cid, key)
    assert cycle_id is not None

    assert PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id, payroll_event_type="payroll"
    ).count() >= 1
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle_id).one()
    assert record.observations_json["coverage"]["complete"] is True

    # The run is SYSTEM and names its occurrence, so the derived next date is one
    # frequency on from the occurrence → the class is no longer due.
    assert {event.mechanism for event in PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id)} == {"SYSTEM"}
    assert next_payroll_date(cid) == _local_midnight_days_after(cid, occurrence, 14)

    # A second tick is inert — the class is not due.
    events_before = PayrollEvent.query.filter_by(class_id=cid).count()
    run_automatic_payroll_job()
    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_before
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1


def test_not_due_class_is_skipped(app):
    classroom = initialize("chemistry_p1", app)
    cid, *_ = _seed_due_class(classroom, due=False)

    run_automatic_payroll_job()

    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 0


def test_replaying_same_occurrence_is_idempotent(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, occurrence = _seed_due_class(classroom, due=True)

    run_automatic_payroll_job()
    events_after_first = PayrollEvent.query.filter_by(class_id=cid).count()
    assert events_after_first >= 1

    # Simulate the scheduled occurrence being retried (as a job racing the first
    # would see it): the SAME occurrence is due again, so the derived key is
    # identical.
    monkeypatch.setattr(
        schedule_module, "due_payroll_occurrences", lambda now=None: [(cid, occurrence)]
    )

    run_automatic_payroll_job()

    # The completion anchor for this occurrence already exists, so the FEAT
    # short-circuits: no new payroll events, still one interpretation record.
    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_after_first
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1


def test_one_class_failing_to_derive_its_date_does_not_block_another(app, monkeypatch):
    """A class whose next payroll date cannot be derived is skipped, not fatal:
    every other due class is still enumerated and paid, keeping the job's
    "one class's failure cannot roll back or block another" contract."""
    broken_classroom = initialize("chemistry_p1", app)
    healthy_classroom = initialize("ap_csp_p3", app)
    broken_cid, *_ = _seed_due_class(broken_classroom, due=True)
    healthy_cid, _, _, healthy_occurrence = _seed_due_class(healthy_classroom, due=True)

    real_next_payroll_date = schedule_module.next_payroll_date

    def _next_payroll_date(class_id, *, as_of=None):
        if class_id == broken_cid:
            raise ValueError(f"No payroll boundary found for class {class_id}.")
        return real_next_payroll_date(class_id, as_of=as_of)

    monkeypatch.setattr(schedule_module, "next_payroll_date", _next_payroll_date)

    assert schedule_module.due_payroll_occurrences() == [(healthy_cid, healthy_occurrence)]

    run_automatic_payroll_job()

    assert resolve_completed_run(
        healthy_cid, f"auto-payroll:{healthy_cid}:{healthy_occurrence.isoformat()}"
    ) is not None
    assert PayrollEvent.query.filter_by(class_id=broken_cid).count() == 0
