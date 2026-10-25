"""
SPEC-TIME-001 / MAP-UI-002 compliant display formatting for timestamps.

Every timestamp is localized through ``canonical_temporal_resolver``'s
``localize_timestamp`` primitive: CLE in the class timezone when a class
context is at hand, SLE (UTC) when there is none.

The ``ctx`` argument is a context object carrying ``class_id``
(``CanonicalContext``, ``SimpleNamespace(class_id=...)``) for class time, or
``None`` for UTC. Builders call these (SPEC-UI-001 §VII); templates never format
a time and nothing here is a Jinja filter (INV-ARC-022 §V.8: a template must not
query the database, and resolving a class timezone is a database read).

Core functions (plain Python, usable anywhere):
    format_timestamp  — "Dec 3, 2025, 2:30 PM PST"
    format_date       — "Dec 3, 2025"
    format_compact_date — "Dec 3"
    format_time       — "2:30 PM PST"

    format_local_date — text for a class-local ``date`` (no conversion)
    format_file_stamp — "20261025_143000" (UTC) for export file names
"""

from __future__ import annotations

from datetime import datetime


from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _execution_context(ctx):
    """The class context to localize under, or None for SLE."""
    # BoundaryContext raises AttributeError on class_id; getattr's default covers it.
    return ctx if getattr(ctx, "class_id", None) else None


def _localize(ctx, dt) -> datetime:
    if isinstance(dt, str):
        # TLCP correlation packs (DOM-OPS-001) freeze request-trace timestamps
        # as ISO strings inside a JSON column (app/services/tlcp.py:
        # row.created_at.isoformat()) -- callers pass those straight through
        # this filter, never a datetime. The ISO string carries its offset.
        dt = datetime.fromisoformat(dt)
    execution_context = _execution_context(ctx)
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION if execution_context else SYSTEM_LEVEL_EVALUATION,
        canonical_execution_context=execution_context,
        primitive="localize_timestamp",
        timestamp=dt,
    ).local_timestamp


def _tz_abbrev(dt_local: datetime) -> str:
    abbrev = dt_local.strftime("%Z")
    return abbrev if abbrev else ""


def _format_month_day(dt_local: datetime) -> str:
    return f"{dt_local.strftime('%b')} {dt_local.day}"


def _format_clock_time(dt_local: datetime) -> str:
    return dt_local.strftime("%I:%M %p").lstrip("0")


# ---------------------------------------------------------------------------
# Core formatting functions
# ---------------------------------------------------------------------------

def format_timestamp(ctx, dt) -> str:
    if not dt:
        return "—"
    local = _localize(ctx, dt)
    formatted = f"{_format_month_day(local)}, {local.year}, {_format_clock_time(local)}"
    abbrev = _tz_abbrev(local)
    return f"{formatted} {abbrev}".strip()


def format_date(ctx, dt) -> str:
    if not dt:
        return "—"
    local = _localize(ctx, dt)
    return f"{_format_month_day(local)}, {local.year}"


def format_compact_date(ctx, dt) -> str:
    if not dt:
        return "—"
    local = _localize(ctx, dt)
    return _format_month_day(local)


def format_local_date(day, style: str = "medium") -> str | None:
    """Text for a class-local calendar date the resolver already produced.

    No conversion happens here: ``day`` is a ``date`` already in the class's
    calendar. For builders only; templates print the result (SPEC-UI-001 §VII).
    """
    if not day:
        return None
    if style == "short":
        return f"{day:%b %d}"
    if style == "medium":
        return f"{day:%b %d, %Y}"
    if style == "full":
        return f"{day:%B %d, %Y}"
    if style == "long":
        return f"{day:%B} {day.day}, {day.year}"
    if style == "numeric":
        return f"{day:%m/%d/%Y}"
    if style == "input":
        return day.isoformat()
    raise ValueError(f"unknown date style: {style}")


def format_time(ctx, dt) -> str:
    if not dt:
        return "—"
    local = _localize(ctx, dt)
    formatted = _format_clock_time(local)
    abbrev = _tz_abbrev(local)
    return f"{formatted} {abbrev}".strip()


def format_file_stamp(instant) -> str:
    """'20261025_143000': a UTC instant for an export file name."""
    utc = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="localize_timestamp", timestamp=instant,
    ).local_timestamp
    return f"{utc:%Y%m%d_%H%M%S}"
