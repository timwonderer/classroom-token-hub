"""
SPEC-TIME-001 / MAP-UI-002 compliant display formatting for timestamps.

Every timestamp is localized through ``canonical_temporal_resolver``'s
``localize_timestamp`` primitive: CLE in the class timezone when a class
context is at hand, SLE (UTC) when there is none.

The ``ctx`` argument is either a context object carrying ``class_id``
(``CanonicalContext``, ``SimpleNamespace(class_id=...)``), ``None`` (SLE), or the
Jinja template context the filters receive. For a template context the class
comes from an explicit ``temporal_context`` template variable (a display lens,
e.g. the sysadmin ticket view's "class time" toggle), else from the request's
``g.canonical_context``.

Core functions (plain Python, usable anywhere):
    format_timestamp  — "Dec 3, 2025, 2:30 PM PST"
    format_date       — "Dec 3, 2025"
    format_compact_date — "Dec 3"
    format_time       — "2:30 PM PST"

Jinja filters (registered via register_temporal_filters):
    fmt_timestamp, fmt_date, fmt_compact_date, fmt_time
"""

from __future__ import annotations

from datetime import datetime

from flask import g, has_app_context
from jinja2 import pass_context
from jinja2.runtime import Context
from markupsafe import Markup

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
    if isinstance(ctx, Context):
        ctx = ctx.get("temporal_context") or (
            getattr(g, "canonical_context", None) if has_app_context() else None
        )
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


def format_time(ctx, dt) -> str:
    if not dt:
        return "—"
    local = _localize(ctx, dt)
    formatted = _format_clock_time(local)
    abbrev = _tz_abbrev(local)
    return f"{formatted} {abbrev}".strip()


# ---------------------------------------------------------------------------
# Jinja2 filters (delegate to core functions with the template context)
# ---------------------------------------------------------------------------

@pass_context
def fmt_timestamp(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_timestamp(ctx, dt)


@pass_context
def fmt_date(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_date(ctx, dt)


@pass_context
def fmt_compact_date(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_compact_date(ctx, dt)


@pass_context
def fmt_time(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_time(ctx, dt)


def register_temporal_filters(app):
    app.jinja_env.filters["fmt_timestamp"] = fmt_timestamp
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_compact_date"] = fmt_compact_date
    app.jinja_env.filters["fmt_time"] = fmt_time
