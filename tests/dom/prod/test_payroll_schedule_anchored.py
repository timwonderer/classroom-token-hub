"""The payroll schedule is an anchored recurrence (SPEC-TIME-001 §IX.12).

Owner correction 2026-09-30: a monthly payroll is not every 30 days. A month
runs from one date to the next occurrence of that date; when the date does not
exist in a month the boundary rolls forward to the next day that does, and every
boundary is counted from the ORIGINAL anchor (first_pay_date), never from the
previous result: 1/31 → 3/1 → 3/31 → 5/1 → 5/31 … Weekly and biweekly paydays
stay on class-local midnight across DST. The next payroll date is the first
anchored boundary strictly after the last SYSTEM payroll occurrence; a teacher's
run does not move it (DOM-PROD-001 §XV.5).

These drive the real derivation (``next_payroll_date``) over real
``payroll_settings`` rows and SYSTEM ``payroll_event`` rows written as they are
recorded by the automatic job. The class is in America/Los_Angeles.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytz
import pytest

from tests.helpers.payroll_fixture import record_payroll_source_fixture
from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollEvent
from app.services.payroll.schedule import SCHEDULED_OCCURRENCE_KEY, next_payroll_date
from app.services.payroll.settings import append_payroll_setting
from tests.helpers.canonical_classroom import provision_classroom

LA = pytz.timezone("America/Los_Angeles")

NON_LEAP_SEQUENCE = [
    (1, 31), (3, 1), (3, 31), (5, 1), (5, 31), (7, 1),
    (7, 31), (8, 31), (10, 1), (10, 31), (12, 1), (12, 31),
]


def _midnight(year, month, day):
    """Class-local midnight (what the settings form stores for a pay date)."""
    return LA.localize(datetime.combine(date(year, month, day), time.min)).astimezone(timezone.utc)


def _local_date(instant):
    return instant.astimezone(LA).date()


def _class(app, *, first_pay_date, schedule, recorded_at):
    classroom = provision_classroom("tz_pacific_p1", with_payroll_settings=False)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"schedule:{uuid4()}"):
        setting = append_payroll_setting(
            class_id=classroom.class_id,
            settings_data={
                "pay_rate": Decimal("1"),
                "pay_schedule_type": schedule,
                "first_pay_date": first_pay_date,
            },
            effective_date=recorded_at, created_at=recorded_at,
        )
    db.session.commit()
    return classroom, setting


def _run(classroom, setting, *, mechanism, at, occurrence=None):
    """A payroll event as the job (SYSTEM, with its occurrence) or a teacher records it."""
    summary = {"source": "class_payroll_settlement"}
    if occurrence is not None:
        summary[SCHEDULED_OCCURRENCE_KEY] = occurrence.isoformat()
    key = f"run:{uuid4()}"
    with FEATContext("FEAT-PROD-003", idempotency_key=key):
        record_payroll_source_fixture(
            class_id=classroom.class_id, target_seat_id=classroom.students[0].seat.id,
            actor_seat_id=classroom.teacher_seat_id, correlation_id=key, idempotency_key=key,
            policy_uuid=setting.policy_uuid, mechanism=mechanism,
            payroll_event_type="payroll", recorded_at=at, summary_json=summary,
        )
        db.session.flush()
    db.session.commit()


def _walk(classroom, setting, first, steps):
    """Run the scheduler's loop: each SYSTEM run settles the date then due."""
    dates = []
    occurrence = next_payroll_date(classroom.class_id, as_of=first)
    for _ in range(steps):
        dates.append(_local_date(occurrence))
        # The hourly job runs a little late; the occurrence, not the run
        # instant, is what anchors the next date.
        ran_at = occurrence + timedelta(minutes=50)
        _run(classroom, setting, mechanism="SYSTEM", at=ran_at, occurrence=occurrence)
        occurrence = next_payroll_date(classroom.class_id, as_of=ran_at)
    return dates


@pytest.mark.parametrize("year", [2027, 2028])  # non-leap, leap
def test_monthly_anchored_on_the_31st_rolls_forward_from_the_original_anchor(app, year):
    first = _midnight(year, 1, 31)
    classroom, setting = _class(
        app, first_pay_date=first, schedule="monthly",
        recorded_at=first - timedelta(days=10),
    )

    dates = _walk(classroom, setting, first, 12)

    # SPEC-TIME-001 §IX.12 required example; in a leap year index 1 is still
    # March 1 (February 29 is not the anchor day).
    assert dates == [date(year, m, d) for m, d in NON_LEAP_SEQUENCE]


def test_monthly_anchored_on_the_28th_stays_on_the_28th(app):
    first = _midnight(2027, 1, 28)
    classroom, setting = _class(
        app, first_pay_date=first, schedule="monthly",
        recorded_at=first - timedelta(days=10),
    )

    assert _walk(classroom, setting, first, 6) == [date(2027, m, 28) for m in range(1, 7)]


def test_after_a_system_run_on_march_1st_the_next_date_is_march_31st(app):
    """Anchor 1/31: the run on the rolled-forward 3/1 is followed by 3/31 (the
    anchor day), not 4/1 (3/1 + one month)."""
    first = _midnight(2027, 1, 31)
    classroom, setting = _class(
        app, first_pay_date=first, schedule="monthly",
        recorded_at=first - timedelta(days=10),
    )
    march_1 = _midnight(2027, 3, 1)
    _run(classroom, setting, mechanism="SYSTEM", at=march_1 + timedelta(minutes=5), occurrence=march_1)

    assert next_payroll_date(classroom.class_id, as_of=march_1 + timedelta(hours=1)) == _midnight(2027, 3, 31)


@pytest.mark.parametrize("schedule,expected", [
    ("weekly", [(3, 2), (3, 9), (3, 16), (3, 23)]),
    ("biweekly", [(3, 2), (3, 16), (3, 30), (4, 13)]),
])
def test_weekly_and_biweekly_paydays_stay_at_local_midnight_across_dst(app, schedule, expected):
    """US DST starts Sun Mar 8 2026: paydays after it are 00:00 PDT (07:00 UTC),
    before it 00:00 PST (08:00 UTC)."""
    first = _midnight(2026, 3, 2)
    classroom, setting = _class(
        app, first_pay_date=first, schedule=schedule,
        recorded_at=first - timedelta(days=1),
    )

    occurrence = next_payroll_date(classroom.class_id, as_of=first)
    seen = []
    for _ in range(len(expected)):
        seen.append(occurrence)
        _run(classroom, setting, mechanism="SYSTEM", at=occurrence + timedelta(minutes=50), occurrence=occurrence)
        occurrence = next_payroll_date(classroom.class_id, as_of=occurrence + timedelta(hours=1))

    assert seen == [_midnight(2026, m, d) for m, d in expected]
    assert all(instant.astimezone(LA).time() == time.min for instant in seen)


def test_a_teacher_run_does_not_move_the_anchored_schedule(app):
    first = _midnight(2027, 1, 31)
    classroom, setting = _class(
        app, first_pay_date=first, schedule="monthly",
        recorded_at=first - timedelta(days=10),
    )
    _run(classroom, setting, mechanism="SYSTEM", at=first + timedelta(minutes=5), occurrence=first)
    feb_10 = _midnight(2027, 2, 10)
    _run(classroom, setting, mechanism="TEACHER", at=feb_10)

    assert next_payroll_date(classroom.class_id, as_of=feb_10 + timedelta(hours=1)) == _midnight(2027, 3, 1)
