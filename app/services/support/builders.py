"""Support domain view-model builders (SPEC-UI-001 §VII, §IX).

Times arrive in templates as presentation-ready text, formatted here through
the canonical temporal resolver (SPEC-TIME-001).
"""

from __future__ import annotations

from app.utils.temporal_display import format_timestamp


def build_announcement_rows(ctx, announcements):
    """Attach display times and the expired flag to each announcement for the teacher's list.

    ``expires_on`` is the class-local last day the caller already resolved from
    the stored exclusive end (a date, so no timezone is left to apply).
    """
    for announcement in announcements:
        # Evaluated here, not in the template: it asks the resolver for the class's now.
        announcement.has_expired = announcement.is_expired()
        announcement.created_at_display = format_timestamp(ctx, announcement.created_at)
        expires_on = getattr(announcement, "expires_on", None)
        announcement.expires_on_display = (
            expires_on.strftime("%b %d, %Y") if announcement.expires_at and expires_on else None
        )
    return announcements
