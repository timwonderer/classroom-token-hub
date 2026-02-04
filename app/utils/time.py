"""
Centralized time utility for Classroom Economy.

This module provides the authoritative source for "current time" and timezone handling.
As per docs/development/TIMEZONE_HANDLING_SPECIFICATION.md:
- All datetimes MUST be UTC-aware.
- No direct calls to datetime.now() or datetime.utcnow() allowed elsewhere.
"""

from datetime import datetime, timezone

# Re-export timezone for convenience
UTC = timezone.utc

def utc_now() -> datetime:
    """
    Get the current time in UTC with timezone information.
    
    Returns:
        datetime: A timezone-aware datetime object representing now in UTC.
    """
    return datetime.now(timezone.utc)

def ensure_utc(dt: datetime) -> datetime | None:
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
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
