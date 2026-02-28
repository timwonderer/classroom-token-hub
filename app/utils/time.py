"""
Centralized time utility for Classroom Economy.

This module provides the authoritative source for "current time" and timezone handling.
As per docs/development/TIMEZONE_HANDLING_SPECIFICATION.md:
- All datetimes MUST be UTC-aware.
- No direct calls to datetime.now() or datetime.utcnow() allowed elsewhere.
"""

from datetime import date, datetime, time, timezone
import pytz
from flask import current_app, has_app_context, has_request_context, session
from app.extensions import db

# Re-export timezone for convenience
UTC = timezone.utc
UTC_MIN = datetime.min.replace(tzinfo=timezone.utc)
PACIFIC_FALLBACK_TIMEZONE = "America/Los_Angeles"

def utc_now() -> datetime:
    """
    Get the current time in UTC with timezone information.
    
    Returns:
        datetime: A timezone-aware datetime object representing now in UTC.
    """
    return datetime.now(timezone.utc)

def get_timezone(timezone_name: str | None = None):
    """
    Resolve an effective timezone with Pacific fallback.

    Priority:
    1. Explicit timezone_name argument
    2. Session timezone (if request context exists)
    3. App DEFAULT_TIMEZONE config (if app context exists)
    4. Pacific fallback
    """
    tz_candidate = timezone_name
    if not tz_candidate and has_request_context():
        tz_candidate = session.get("timezone")
    if not tz_candidate and has_app_context():
        tz_candidate = current_app.config.get("DEFAULT_TIMEZONE")
    if not tz_candidate:
        tz_candidate = PACIFIC_FALLBACK_TIMEZONE

    try:
        return pytz.timezone(tz_candidate)
    except pytz.UnknownTimeZoneError:
        if has_app_context():
            current_app.logger.warning(
                "Invalid timezone '%s'; falling back to %s.",
                tz_candidate,
                PACIFIC_FALLBACK_TIMEZONE,
            )
        return pytz.timezone(PACIFIC_FALLBACK_TIMEZONE)

def ensure_utc(dt: datetime, naive_tz_name: str | None = None) -> datetime | None:
    """
    Ensure a datetime object is UTC-aware.
    
    - If naive, assumes it is UTC and attaches timezone.
    - If aware, converts to UTC.
    - If None, returns None.
    
    Args:
        dt: The datetime to normalize.
        
    Returns:
        datetime | None: The normalized UTC-aware datetime.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        if naive_tz_name:
            tz = get_timezone(naive_tz_name)
            return tz.localize(dt).astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def local_date_bounds_utc(local_day: date, timezone_name: str | None = None) -> tuple[datetime, datetime]:
    """
    Convert a local calendar day into UTC start/end datetimes for that timezone.
    """
    tz = get_timezone(timezone_name)
    start_local = tz.localize(datetime.combine(local_day, time.min))
    end_local = tz.localize(datetime.combine(local_day, time.max.replace(microsecond=0)))
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def local_date_end_utc(local_day: date, timezone_name: str | None = None) -> datetime:
    """
    Convert a local date to the end of that local day, represented in UTC.
    """
    _, end_utc = local_date_bounds_utc(local_day, timezone_name=timezone_name)
    return end_utc

def normalize_for_db(dt: datetime) -> datetime | None:
    """
    Normalize datetimes for database comparisons (SQLite stores naive UTC).

    - Ensures UTC awareness.
    - Strips timezone for SQLite comparisons to match stored values.
    """
    dt = ensure_utc(dt)
    if dt is None:
        return None
    if db.engine.dialect.name == "sqlite":
        return dt.replace(tzinfo=None)
    return dt
