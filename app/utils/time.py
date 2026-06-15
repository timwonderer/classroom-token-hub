"""
Centralized time utility for Classroom Economy.

This module provides the authoritative source for "current time" and timezone handling.
As per docs/ARCHITECTURE/OPERATIONS/ARC-OPS-012_Datetime_Handling_Specification.md:
- All datetimes MUST be UTC-aware.
- No direct calls to datetime.now() or datetime.utcnow() allowed elsewhere.
"""

from datetime import date, datetime, time, timedelta, timezone
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

def ensure_utc(dt: datetime | None, naive_tz_name: str | None = None) -> datetime | None:
    """
    Ensure a datetime object is UTC-aware.
    
    - If naive and naive_tz_name is provided, localize in that timezone then convert to UTC.
    - If naive and naive_tz_name is not provided, assume UTC and attach timezone.
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
    end_local = tz.localize(datetime.combine(local_day, time.max))
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def local_date_range_utc(local_day: date, timezone_name: str | None = None) -> tuple[datetime, datetime]:
    """
    Convert a local calendar day into a UTC [start, end) range for that timezone.
    """
    tz = get_timezone(timezone_name)
    start_local = tz.localize(datetime.combine(local_day, time.min))
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def local_date_end_utc(local_day: date, timezone_name: str | None = None) -> datetime:
    """
    Convert a local date to the end of that local day, represented in UTC.
    """
    _, end_utc = local_date_bounds_utc(local_day, timezone_name=timezone_name)
    return end_utc

def class_now(timezone_name: str | None = None, timestamp_utc: datetime | None = None) -> datetime:
    """
    Return the current effective class-local time.
    """
    reference_utc = ensure_utc(timestamp_utc) if timestamp_utc is not None else utc_now()
    return reference_utc.astimezone(get_timezone(timezone_name))

def class_date(timezone_name: str | None = None, timestamp_utc: datetime | None = None) -> date:
    """
    Return the current effective class-local calendar date.
    """
    return class_now(timezone_name=timezone_name, timestamp_utc=timestamp_utc).date()

def day_bounds_utc(timezone_name: str | None = None, timestamp_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for the effective class-local day.
    """
    return local_date_range_utc(
        class_date(timezone_name=timezone_name, timestamp_utc=timestamp_utc),
        timezone_name=timezone_name,
    )

def week_bounds_utc(reference_time: datetime | None = None, timezone_name: str | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for the class-local week containing reference_time.
    Weeks start on Monday.
    """
    local_now = class_now(timezone_name=timezone_name, timestamp_utc=reference_time)
    week_start = local_now.date() - timedelta(days=local_now.weekday())
    start_utc, _ = local_date_range_utc(week_start, timezone_name=timezone_name)
    return start_utc, start_utc + timedelta(days=7)

def month_bounds_utc(reference_time: datetime | None = None, timezone_name: str | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for the class-local month containing reference_time.
    """
    local_now = class_now(timezone_name=timezone_name, timestamp_utc=reference_time)
    start_local_day = date(local_now.year, local_now.month, 1)
    start_utc, _ = local_date_range_utc(start_local_day, timezone_name=timezone_name)
    if local_now.month == 12:
        next_month_day = date(local_now.year + 1, 1, 1)
    else:
        next_month_day = date(local_now.year, local_now.month + 1, 1)
    end_utc, _ = local_date_range_utc(next_month_day, timezone_name=timezone_name)
    return start_utc, end_utc

def semester_bounds_utc(reference_time: datetime | None = None, timezone_name: str | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for the class-local semester containing reference_time.
    """
    local_now = class_now(timezone_name=timezone_name, timestamp_utc=reference_time)
    if local_now.month <= 6:
        start_day = date(local_now.year, 1, 1)
        end_day = date(local_now.year, 7, 1)
    else:
        start_day = date(local_now.year, 7, 1)
        end_day = date(local_now.year + 1, 1, 1)
    start_utc, _ = local_date_range_utc(start_day, timezone_name=timezone_name)
    end_utc, _ = local_date_range_utc(end_day, timezone_name=timezone_name)
    return start_utc, end_utc

def claim_period_bounds_utc(period_key: str, timezone_name: str | None = None, reference_time: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for a supported insurance claim period.
    """
    normalized_key = (period_key or "month").strip().lower()
    if normalized_key in {"week", "weekly"}:
        return week_bounds_utc(reference_time=reference_time, timezone_name=timezone_name)
    if normalized_key in {"semester", "semiannual"}:
        return semester_bounds_utc(reference_time=reference_time, timezone_name=timezone_name)
    if normalized_key in {"month", "monthly"}:
        return month_bounds_utc(reference_time=reference_time, timezone_name=timezone_name)
    raise ValueError(f"Unsupported claim period: {period_key}")

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


# ============================================================================
# V2 CLASS-SCOPED TEMPORAL AUTHORITY (INV-ARC-015)
# ============================================================================

def get_class_timezone(class_id: str) -> str:
    """
    Resolve the authoritative timezone for a class.
    """
    from app.models import ClassEconomy
    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    return economy.class_timezone if economy else PACIFIC_FALLBACK_TIMEZONE


def get_class_now(class_id: str, reference_time_utc: datetime | None = None) -> datetime:
    """
    Get the current time in the class's authoritative timezone.
    """
    tz_name = get_class_timezone(class_id)
    reference_utc = ensure_utc(reference_time_utc) if reference_time_utc is not None else utc_now()
    return reference_utc.astimezone(get_timezone(tz_name))


def to_class_time(dt_utc: datetime, class_id: str) -> datetime:
    """
    Convert a UTC datetime to class-local time.
    """
    tz_name = get_class_timezone(class_id)
    return ensure_utc(dt_utc).astimezone(get_timezone(tz_name))


def get_class_month_start_utc(class_id: str, reference_time: datetime | None = None) -> datetime:
    """
    Return the UTC timestamp representing the start of the current month in class time.
    """
    tz_name = get_class_timezone(class_id)
    start_utc, _ = month_bounds_utc(reference_time=reference_time, timezone_name=tz_name)
    return start_utc


def get_class_today_range(class_id: str, reference_time_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for 'today' in class time.
    """
    tz_name = get_class_timezone(class_id)
    return local_date_range_utc(
        class_date(timezone_name=tz_name, timestamp_utc=reference_time_utc),
        timezone_name=tz_name,
    )


def get_class_week_range_utc(class_id: str, reference_time_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Return the UTC [start, end) range for the class-local week containing reference time.
    """
    tz_name = get_class_timezone(class_id)
    local_now = get_class_now(class_id, reference_time_utc=reference_time_utc)
    week_start = local_now.date() - timedelta(days=local_now.weekday())
    start_utc, _ = local_date_range_utc(week_start, timezone_name=tz_name)
    return start_utc, start_utc + timedelta(days=7)


def get_class_cycle_start_utc(
    class_id: str,
    reference_time_utc: datetime,
    *,
    cycle_length_days: int,
    effective_start_utc: datetime | None = None,
) -> datetime:
    """
    Return deterministic class-aligned cycle start in UTC.

    For monthly-equivalent cycles (30 days), aligns to class month boundary.
    For other cycles, aligns relative to the class-local effective start.
    """
    reference_utc = ensure_utc(reference_time_utc) or utc_now()
    normalized_cycle_days = max(1, int(cycle_length_days))

    if normalized_cycle_days == 30:
        return get_class_month_start_utc(class_id, reference_time=reference_utc)

    tz_name = get_class_timezone(class_id)
    tz = get_timezone(tz_name)
    local_reference = reference_utc.astimezone(tz)

    effective_utc = ensure_utc(effective_start_utc) if effective_start_utc is not None else reference_utc
    local_effective = effective_utc.astimezone(tz)

    if local_reference <= local_effective:
        return local_effective.astimezone(timezone.utc)

    elapsed_days = (local_reference.date() - local_effective.date()).days
    cycle_index = elapsed_days // normalized_cycle_days
    cycle_start_local = local_effective + timedelta(days=cycle_index * normalized_cycle_days)
    return cycle_start_local.astimezone(timezone.utc)
