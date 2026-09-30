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

Every payday is a boundary of one recurrence anchored on ``first_pay_date``
(SPEC-TIME-001 §IX.12, ``anchored_recurrence_boundary``). Boundary ``n`` is
computed from the anchor and ``n`` alone, never from the previous boundary, so
nothing drifts: a monthly schedule anchored on Jan 31 runs 1/31 → 3/1 → 3/31 →
5/1 → 5/31 … (``overflow = roll_forward``), and weekly paydays stay on
class-local midnight across DST. The next payroll date is the first boundary
strictly after the last SYSTEM occurrence — or boundary 0 when the schedule has
never run — which is where the three forms above come from.

``pay_schedule_type`` sets the cadence: ``weekly`` (every week), ``biweekly``
(every second week), ``monthly`` (calendar month, rolled forward), ``daily`` and
``custom`` (every ``payroll_frequency_days`` class-local days).
``payroll_frequency_days`` is read only for ``custom``; for the other types it is
informational and does not change the cadence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

from app.models import PayrollEvent
from app.services.payroll.settings import (
    classes_with_payroll_settings,
    current_payroll_setting,
    payroll_setting_effective_at,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    advance_local_calendar_days,
    canonical_temporal_resolver,
    ensure_utc,
    utc_now,
)

SCHEDULED_OCCURRENCE_KEY = "scheduled_occurrence"

# Roll a month-end anchor forward, never clamp it back (owner ruling; the same
# overflow insurance coverage uses, SPEC-TIME-001 §IX.12).
PAYROLL_MONTHLY_OVERFLOW = "roll_forward"

# Bounds the search for the first boundary after an instant; a class would need
# to have missed thousands of paydays to reach it.
_MAX_BOUNDARY_STEPS = 10_000


@dataclass(frozen=True)
class PayCadence:
    """How boundary ``n`` of a payroll schedule is computed from its anchor.

    ``unit`` is ``month`` or ``week`` (resolver ``anchored_recurrence_boundary``
    cadences, stepped ``step`` indexes per payday) or ``day`` (``step`` class-local
    calendar days per payday, for daily and custom N-day schedules).
    """

    unit: str
    step: int


# What the settings form stores in ``payroll_frequency_days`` for a named
# schedule: its usual length, for display (the economy page shows it). It is
# never used to compute a payday — the cadence comes from ``pay_schedule_type``
# (``pay_cadence``), and ``monthly`` is a calendar month, not a number of days.
NOMINAL_FREQUENCY_DAYS = {'daily': 1, 'weekly': 7, 'biweekly': 14, 'monthly': 30}


def pay_cadence(pay_schedule_type: str | None, frequency_days: int | None) -> PayCadence | None:
    """The cadence a setting's ``pay_schedule_type`` names; None if it names none."""
    schedule = (pay_schedule_type or "").strip().lower()
    if schedule == "monthly":
        return PayCadence("month", 1)
    if schedule == "weekly":
        return PayCadence("week", 1)
    if schedule == "biweekly":
        return PayCadence("week", 2)
    if schedule == "daily":
        return PayCadence("day", 1)
    if schedule == "custom" and frequency_days and int(frequency_days) > 0:
        days = int(frequency_days)
        return PayCadence("week", days // 7) if days % 7 == 0 else PayCadence("day", days)
    return None


def _class_ctx(class_id: str):
    return SimpleNamespace(class_id=class_id)


def _anchor_date(class_id: str, first_pay_date) -> date:
    """The class-local calendar date of ``first_pay_date``."""
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_class_ctx(class_id),
        primitive="current_evaluation_day",
        reference_time_utc=ensure_utc(first_pay_date),
    ).evaluation_date


def schedule_boundary(class_id: str, anchor: date, cadence: PayCadence, n: int) -> datetime:
    """Payday ``n`` (``n >= 0``) of the schedule: class-local midnight, in UTC.

    Computed from the anchor and ``n`` only (SPEC-TIME-001 §IX.12), never from
    payday ``n - 1``.
    """
    if cadence.unit == "day":
        # No day cadence in §IX.12; the same rule — anchor plus n × step
        # calendar days at local midnight — through the resolver's calendar
        # arithmetic.
        start = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=_class_ctx(class_id),
            primitive="anchored_recurrence_boundary",
            anchor_date=anchor, cadence="week", index=0,
        ).boundary_start_utc
        return advance_local_calendar_days(start, cadence.step * n, class_timezone_name(class_id))
    extra = {"overflow": PAYROLL_MONTHLY_OVERFLOW} if cadence.unit == "month" else {}
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_class_ctx(class_id),
        primitive="anchored_recurrence_boundary",
        anchor_date=anchor,
        cadence=cadence.unit,
        index=cadence.step * n,
        **extra,
    ).boundary_start_utc


def _index_estimate(anchor: date, cadence: PayCadence, local_day: date) -> int:
    """A payday index at or before the first boundary after ``local_day``."""
    if cadence.unit == "month":
        months = (local_day.year - anchor.year) * 12 + (local_day.month - anchor.month)
        return max(0, months // cadence.step - 1)
    days_per_step = cadence.step * (7 if cadence.unit == "week" else 1)
    return max(0, (local_day - anchor).days // days_per_step - 1)


def first_boundary_after(class_id: str, anchor: date, cadence: PayCadence, instant) -> datetime:
    """The first payday strictly after ``instant``."""
    instant = ensure_utc(instant)
    local_day = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_class_ctx(class_id),
        primitive="current_evaluation_day",
        reference_time_utc=instant,
    ).evaluation_date
    n = _index_estimate(anchor, cadence, local_day)
    for _ in range(_MAX_BOUNDARY_STEPS):
        boundary = schedule_boundary(class_id, anchor, cadence, n)
        if boundary > instant:
            return boundary
        n += 1
    raise ValueError(f"No payroll boundary found after {instant} for class {class_id}.")


def derive_next_payroll_date(
    *,
    class_id: str,
    first_pay_date,
    pay_schedule_type: str | None,
    frequency_days: int | None,
    last_system_occurrence,
) -> datetime | None:
    """The next payroll date (DOM-PROD-001 §XV.5). Reads nothing but the class's
    timezone (through the resolver).

    Boundary 0 (``first_pay_date``) until the schedule has run — whether still
    ahead or already arrived, in which case it is due — then the first anchored
    boundary strictly after the last SYSTEM occurrence. A manual run is not an
    input, so it cannot move the date. None when there is no anchor or no
    cadence: no schedule.
    """
    if first_pay_date is None:
        return None
    cadence = pay_cadence(pay_schedule_type, frequency_days)
    anchor = _anchor_date(class_id, first_pay_date)
    first = schedule_boundary(class_id, anchor, cadence or PayCadence("week", 1), 0)
    if last_system_occurrence is None:
        return first
    if cadence is None:
        return None
    return first_boundary_after(class_id, anchor, cadence, last_system_occurrence)


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
        class_id=class_id,
        first_pay_date=setting.first_pay_date,
        pay_schedule_type=setting.pay_schedule_type,
        frequency_days=setting.payroll_frequency_days,
        last_system_occurrence=last_system_payroll_occurrence(class_id, as_of=as_of),
    )


def next_payroll_boundary_after(class_id: str, instant) -> datetime | None:
    """The first payroll boundary strictly after ``instant``.

    Normally the next payroll date itself. If that date has already passed but
    its scheduled run has not happened yet, the overdue date already closed the
    cycle ``instant`` falls in, so the boundary is the one after it.
    """
    instant = ensure_utc(instant)
    boundary = next_payroll_date(class_id, as_of=instant)
    if boundary is None or boundary > instant:
        return boundary
    setting = current_payroll_setting(class_id, as_of=instant)
    cadence = pay_cadence(setting.pay_schedule_type, setting.payroll_frequency_days)
    if cadence is None:
        return None
    anchor = _anchor_date(class_id, setting.first_pay_date)
    return first_boundary_after(class_id, anchor, cadence, instant)


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
