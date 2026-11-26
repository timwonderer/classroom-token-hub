"""The only time tool tests use: thin wrappers over the production resolver.

INV-ARC-015 §VII and SPEC-TIME-001 §XII bind tests as well as runtime code: a
test must not read the wall clock, convert timezones or do date arithmetic
itself. Each function here is one ``canonical_temporal_resolver`` call, so a
test's notion of "now", "three days later" or "09:00 class time" is the
production one, not a second implementation that can disagree with it.

Pinning time: ``pinned_clock(instant)`` patches the resolver's own clock, the
single seam SPEC-TIME-001 §XIII names, so production code and the test see the
same instant.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import patch

from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


def _resolve(primitive: str, class_id: str | None = None, **inputs):
    if class_id is None:
        return canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive=primitive, **inputs)
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive=primitive,
        **inputs,
    )


@contextmanager
def pinned_clock(instant: datetime):
    """Production code and the test both read ``instant`` as now."""
    with patch("app.utils.canonical_temporal_resolver.utc_now", return_value=instant):
        yield instant


def now() -> datetime:
    """The resolver's current UTC instant (pinned inside ``pinned_clock``)."""
    return _resolve("current_time").canonical_now_utc


def shifted(instant: datetime, *, seconds: int = 0, minutes: int = 0, hours: int = 0) -> datetime:
    """``instant`` moved by an exact elapsed duration (negative for earlier)."""
    return _resolve(
        "shift_timestamp", timestamp=instant, elapsed_seconds=seconds + 60 * minutes + 3600 * hours,
    ).shifted_timestamp_utc


def calendar_days_later(instant: datetime, days: int, *, class_id: str | None = None) -> datetime:
    """``instant`` moved by whole calendar days, keeping its local clock time.

    Without ``class_id`` the calendar is UTC, so a day is exactly 24 hours.
    """
    return _resolve("shift_calendar_days", class_id, timestamp=instant, days=days).shifted_timestamp_utc


def class_wall_time(class_id: str, on: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """The UTC instant of a class-local wall-clock time, e.g. 09:00 on Nov 1."""
    return _resolve(
        "shift_calendar_days", class_id, date=on, days=0, time=time(hour, minute, second),
    ).shifted_timestamp_utc


def class_date_of(instant: datetime, class_id: str) -> date:
    """The class-local calendar date of ``instant``."""
    return _resolve("localize_timestamp", class_id, timestamp=instant).evaluation_date


def class_day_bounds(class_id: str, on: date) -> tuple[datetime, datetime]:
    """``[start, end)`` of a class-local day, in UTC."""
    bounds = _resolve("evaluation_day_boundaries", class_id, evaluation_date=on)
    return bounds.boundary_start_utc, bounds.boundary_end_utc


def seconds_between(start: datetime, end: datetime) -> int:
    """Exact elapsed seconds from ``start`` to ``end``."""
    return _resolve("elapsed_duration", intervals=[(start, end)]).elapsed_seconds
