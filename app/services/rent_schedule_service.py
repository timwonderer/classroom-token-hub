"""Rent schedule producer — Rent lifecycle schedule intent → resolved instants.

This module is the boundary between two DIFFERENT LAYERS:

  1. Schedule INTENT lives on ``RentSettings`` (frequency, due day, grace period).
     It is mutable policy configuration; it says *when rent is meant to recur*.

  2. Resolved concrete INSTANTS live on ``BillCycle`` (``cycle_boundary_at``,
     ``next_assessment_at``, ``grace_boundary_at``). They are materialized ONCE at
     cycle creation and never re-derived, so a later settings change cannot
     retroactively move an already-materialized cycle's boundaries
     (INV-CORE-000 non-retroactivity).

The producer performs ALL calendar arithmetic in class-local *dates* (calendar
months, weeks, days), through the canonical temporal resolver, which also does
the DST-correct class-local-date → UTC materialization. It never invents a "current time" for business decisions and
never converts timezones by hand.

Three boundaries are resolved per cycle, all as start-of-class-local-date UTC:

  - ``cycle_boundary_at``  = the cycle's own due date D
  - ``next_assessment_at`` = the SUCCESSOR cycle's due date D' (guaranteed > D)
  - ``grace_boundary_at``  = D + ``grace_period_days`` (late-penalty boundary)
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
)


@dataclass(frozen=True)
class ResolvedCycleSchedule:
    """The three resolved UTC boundaries for a single rent cycle."""
    due_local_date: date
    next_due_local_date: date
    cycle_boundary_at: datetime
    next_assessment_at: datetime
    grace_boundary_at: datetime | None


# --------------------------------------------------------------------------- #
# Class-local date <-> UTC materialization (resolver-backed; the ONLY temporal
# authority this module leans on).
# --------------------------------------------------------------------------- #

def local_date_of_instant(context, instant_utc: datetime) -> date:
    """Class-local (CLE) calendar date of a UTC instant."""
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="current_evaluation_day",
        reference_time_utc=instant_utc,
    )
    return evaluation.evaluation_date


def current_local_date(context, reference_time_utc: datetime) -> date:
    """Class-local calendar date for 'now' (``reference_time_utc``)."""
    return local_date_of_instant(context, reference_time_utc)


def start_of_local_date_utc(context, local_date: date) -> datetime:
    """UTC instant at the START (00:00 class-local) of ``local_date``.

    DST-correct: the resolver localizes ``datetime.combine(D, time.min)`` in the
    class timezone before converting to UTC.
    """
    boundaries = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="evaluation_day_boundaries",
        evaluation_date=local_date,
    )
    return boundaries.boundary_start_utc


# --------------------------------------------------------------------------- #
# Calendar arithmetic on class-local dates (resolver-backed).
# --------------------------------------------------------------------------- #

def _clamp_day_of_month(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def advance_due_date(settings, due_local_date: date, *, context) -> date:
    """Return the SUCCESSOR cycle's due local date, one period after ``due_local_date``.

    Frequency intent is read from RentSettings:
      - ``monthly``: +1 calendar month, re-anchored to ``due_day_of_month``.
      - ``weekly``:  +7 days.
      - ``daily``:   +1 day.
      - ``custom``:  ``custom_frequency_value`` × ``custom_frequency_unit``.
    """
    frequency = (settings.frequency_type or "monthly").strip().lower()

    if frequency == "daily":
        return canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=context,
            primitive="shift_calendar_days",
            date=due_local_date,
            days=1,
        ).shifted_date
    if frequency == "weekly":
        return canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=context,
            primitive="shift_calendar_days",
            date=due_local_date,
            days=7,
        ).shifted_date
    if frequency == "monthly":
        nxt = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=context,
            primitive="anchored_recurrence_boundary",
            anchor_date=due_local_date,
            cadence="month",
            index=1,
            overflow="clamp",
        ).boundary_date
        # Re-anchor to the configured due day (clamped to the month end) so a
        # month-end clamp in one cycle does not permanently drift the day.
        anchor_day = settings.due_day_of_month or due_local_date.day
        return _clamp_day_of_month(nxt.year, nxt.month, anchor_day)
    if frequency == "custom":
        value = settings.custom_frequency_value
        unit = (settings.custom_frequency_unit or "days").strip().lower()
        if not value or value <= 0:
            raise ValueError("custom frequency requires a positive custom_frequency_value")
        if unit == "days":
            return canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=context,
                primitive="shift_calendar_days",
                date=due_local_date,
                days=value,
            ).shifted_date
        if unit == "weeks":
            return canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=context,
                primitive="shift_calendar_days",
                date=due_local_date,
                days=7 * value,
            ).shifted_date
        if unit == "months":
            return canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=context,
                primitive="anchored_recurrence_boundary",
                anchor_date=due_local_date,
                cadence="month",
                index=value,
                overflow="clamp",
            ).boundary_date
        raise ValueError(f"unsupported custom_frequency_unit: {settings.custom_frequency_unit!r}")

    raise ValueError(f"unsupported frequency_type: {settings.frequency_type!r}")


def first_due_local_date(settings, *, context, reference_time_utc: datetime) -> date:
    """Class-local due date of the FIRST rent cycle (cycle_number == 1).

    If ``first_rent_due_date`` is configured, its class-local date is authoritative.
    Otherwise the first due date defaults to the current class-local date (the
    day reconciliation first materializes rent), anchored to ``due_day_of_month``
    for monthly frequency.
    """
    if settings.first_rent_due_date is not None:
        return local_date_of_instant(context, settings.first_rent_due_date)

    today = current_local_date(context, reference_time_utc)
    frequency = (settings.frequency_type or "monthly").strip().lower()
    if frequency == "monthly" and settings.due_day_of_month:
        return _clamp_day_of_month(today.year, today.month, settings.due_day_of_month)
    return today


# --------------------------------------------------------------------------- #
# The producer: resolve one cycle's three boundaries.
# --------------------------------------------------------------------------- #

def resolve_cycle_schedule(settings, *, due_local_date: date, context) -> ResolvedCycleSchedule:
    """Resolve the three concrete UTC boundaries for a cycle due on ``due_local_date``.

    All three are start-of-class-local-date UTC instants:
      - ``cycle_boundary_at``  = start of D
      - ``next_assessment_at`` = start of the successor due date D'  (D' > D ⇒ ordered)
      - ``grace_boundary_at``  = start of (D + grace_period_days), or None if no grace
    """
    next_due_local_date = advance_due_date(settings, due_local_date, context=context)

    cycle_boundary_at = start_of_local_date_utc(context, due_local_date)
    next_assessment_at = start_of_local_date_utc(context, next_due_local_date)

    grace_days = settings.grace_period_days
    if grace_days is None or grace_days < 0:
        grace_boundary_at = None
    else:
        grace_local_date = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=context,
            primitive="shift_calendar_days",
            date=due_local_date,
            days=grace_days,
        ).shifted_date
        grace_boundary_at = start_of_local_date_utc(context, grace_local_date)

    return ResolvedCycleSchedule(
        due_local_date=due_local_date,
        next_due_local_date=next_due_local_date,
        cycle_boundary_at=cycle_boundary_at,
        next_assessment_at=next_assessment_at,
        grace_boundary_at=grace_boundary_at,
    )
