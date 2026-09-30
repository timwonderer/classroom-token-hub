"""The next payroll date, derived and never stored (DOM-PROD-001 §XV.5).

Operator ruling 2026-09-30: the next payroll date comes from ``payroll_settings``
and ``payroll_event`` alone. It is one of

    first_pay_date                              no SYSTEM payroll run yet
    first_pay_date + frequency                  the last SYSTEM run was on first_pay_date
    last SYSTEM payroll occurrence + frequency  otherwise

and all three fall out of :func:`derive_next_payroll_date`: the second is the
third with the first scheduled run as its anchor. Only ``payroll`` events with
``mechanism = SYSTEM`` anchor the schedule. A teacher's run (``TEACHER``), a
``manual_credit`` — including a platform-computed correction recorded as
``SYSTEM`` — and a ``reversal`` never move it.

The anchor is the *scheduled occurrence* a SYSTEM run settled, which the run
records in its events' ``summary_json`` (``SCHEDULED_OCCURRENCE_KEY``); a run's
wall-clock ``recorded_at`` is used only for an event that predates that record.
Anchoring on the occurrence is what keeps paydays from drifting when the hourly
job runs late.

Pay frequency is ``payroll_frequency_days``, advanced in class-local calendar
days so a payday keeps its local time of day across DST. ``pay_schedule_type`` is
its label; ``monthly`` is 30 days, not a calendar month.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytz

from app.models import PayrollEvent
from app.services.payroll.settings import (
    classes_with_payroll_settings,
    current_payroll_setting,
    payroll_setting_effective_at,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
    utc_now,
)

SCHEDULED_OCCURRENCE_KEY = "scheduled_occurrence"

# Bounds the walk past an overdue boundary; a class would need to have missed
# thousands of paydays to reach it.
_MAX_BOUNDARY_STEPS = 10_000


def advance_local_calendar_days(occurrence_utc, days: int, timezone_name: str) -> datetime:
    """Move ``occurrence_utc`` forward ``days`` calendar days in ``timezone_name``.

    The local wall-clock time is preserved, so an occurrence at 07:00 local stays
    at 07:00 local across a DST change. Adding the elapsed UTC duration instead
    lands on the wrong local date on a 23- or 25-hour day.

    Ambiguous and nonexistent local times are decided explicitly:

    * **Ambiguous** (fall back — the clock reads 01:30 twice): take the
      chronologically earlier instant, so the interval never silently lengthens.
    * **Nonexistent** (spring forward — 02:30 never happens): take the smallest
      forward shift onto a time that does exist, so 02:30 becomes 03:30.

    Both are chosen by comparing candidate instants rather than by an ``is_dst``
    flag: in Europe/Dublin the tz database models winter as *negative* DST, so
    ``is_dst=True`` on an ambiguous Dublin time returns the **later** instant.
    """
    tz = pytz.timezone(timezone_name)
    local_occurrence = ensure_utc(occurrence_utc).astimezone(tz)
    target_naive = datetime.combine(
        local_occurrence.date() + timedelta(days=days),
        local_occurrence.time(),
    )

    try:
        target_local = tz.localize(target_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        target_local = min(
            (tz.localize(target_naive, is_dst=flag) for flag in (True, False)),
            key=lambda candidate: candidate.astimezone(timezone.utc),
        )
    except pytz.exceptions.NonExistentTimeError:
        candidates = [
            tz.normalize(tz.localize(target_naive, is_dst=flag))
            for flag in (False, True)
        ]
        target_local = min(
            candidates,
            key=lambda candidate: (
                candidate.replace(tzinfo=None) <= target_naive,
                abs(candidate.replace(tzinfo=None) - target_naive),
            ),
        )

    return target_local.astimezone(timezone.utc)


def derive_next_payroll_date(
    *,
    first_pay_date,
    frequency_days: int | None,
    last_system_occurrence,
    timezone_name: str,
) -> datetime | None:
    """The next payroll date. Pure: no reads, no clock (DOM-PROD-001 §XV.5).

    With a SYSTEM run on record the next date is that run's occurrence plus the
    frequency; otherwise it is ``first_pay_date`` — whether still ahead or
    already arrived, in which case it is due. A manual run is not an input, so it
    cannot move the date. Returns None when neither exists: no schedule.
    """
    if last_system_occurrence is not None and frequency_days:
        return advance_local_calendar_days(last_system_occurrence, int(frequency_days), timezone_name)
    if first_pay_date is not None:
        return ensure_utc(first_pay_date)
    return None


def class_timezone_name(class_id: str) -> str:
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
    ).temporal_authority


def last_system_payroll_occurrence(class_id: str, *, as_of=None) -> datetime | None:
    """The scheduled occurrence the class's last SYSTEM payroll run settled."""
    query = PayrollEvent.query.filter(
        PayrollEvent.class_id == class_id,
        PayrollEvent.payroll_event_type == "payroll",
        PayrollEvent.mechanism == "SYSTEM",
    )
    if as_of is not None:
        query = query.filter(PayrollEvent.recorded_at <= ensure_utc(as_of))
    event = query.order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc()).first()
    if event is None:
        return None
    recorded = (event.summary_json or {}).get(SCHEDULED_OCCURRENCE_KEY)
    if recorded:
        return ensure_utc(datetime.fromisoformat(recorded))
    return ensure_utc(event.recorded_at)


def next_payroll_date(class_id: str, *, as_of=None) -> datetime | None:
    """The class's next payroll date as known at ``as_of`` (default now).

    ``first_pay_date`` and the frequency come from the setting in force at
    ``as_of``; a pending setting shapes the schedule only once it is in force.
    """
    as_of = ensure_utc(as_of or utc_now())
    setting = current_payroll_setting(class_id, as_of=as_of)
    if setting is None:
        return None
    return derive_next_payroll_date(
        first_pay_date=setting.first_pay_date,
        frequency_days=setting.payroll_frequency_days,
        last_system_occurrence=last_system_payroll_occurrence(class_id, as_of=as_of),
        timezone_name=class_timezone_name(class_id),
    )


def next_payroll_boundary_after(class_id: str, instant) -> datetime | None:
    """The first payroll boundary strictly after ``instant``.

    Normally the next payroll date itself. If that date has already passed but
    its scheduled run has not happened yet, the overdue date already closed the
    cycle ``instant`` falls in, so the boundary is the one after it.
    """
    instant = ensure_utc(instant)
    boundary = next_payroll_date(class_id, as_of=instant)
    if boundary is None:
        return None
    setting = current_payroll_setting(class_id, as_of=instant)
    frequency = int(setting.payroll_frequency_days or 0)
    if frequency <= 0:
        return boundary if boundary > instant else None
    timezone_name = class_timezone_name(class_id)
    steps = 0
    while boundary <= instant:
        boundary = advance_local_calendar_days(boundary, frequency, timezone_name)
        steps += 1
        if steps > _MAX_BOUNDARY_STEPS:
            raise ValueError(f"No payroll boundary found after {instant} for class {class_id}.")
    return boundary


def effective_date_for_new_setting(class_id: str, recorded_at) -> datetime:
    """When a setting saved at ``recorded_at`` takes effect (DOM-CLASS-003 §VII).

    The class's first setting is in force at once. A later one waits for the next
    payroll boundary so it never reprices the open cycle. A class whose settings
    define no schedule (no first pay date and no SYSTEM run) has no boundary to
    wait for, so its change is in force at once as well.
    """
    recorded_at = ensure_utc(recorded_at)
    if payroll_setting_effective_at(class_id, recorded_at) is None:
        return recorded_at
    boundary = next_payroll_boundary_after(class_id, recorded_at)
    return boundary if boundary is not None else recorded_at


def due_payroll_occurrences(*, now=None) -> list[tuple[str, datetime]]:
    """``(class_id, scheduled_occurrence)`` for every class whose payroll is due.

    Pure read for the automatic-payroll job: due means the derived next payroll
    date is at or before ``now``.
    """
    now = ensure_utc(now or utc_now())
    due = []
    for class_id in classes_with_payroll_settings():
        occurrence = next_payroll_date(class_id, as_of=now)
        if occurrence is not None and occurrence <= now:
            due.append((class_id, occurrence))
    return due
