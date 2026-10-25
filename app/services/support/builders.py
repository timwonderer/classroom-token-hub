"""Support domain (DOM-SUP-001) presentation builders.

Per SPEC-UI-001 §VII/§IX: issue and announcement times reach templates as
class-time display text, localized through the temporal resolver.
"""

from __future__ import annotations

from app.services import obligations_service
from app.utils.temporal_display import format_timestamp


def build_issue_submitted_displays(ctx, issues) -> dict[int, str]:
    """Each issue's submission time as display text, keyed by issue id."""
    return {issue.id: format_timestamp(ctx, issue.submitted_at) for issue in issues}


def build_announcement_expiry_displays(class_id: str, announcements) -> dict[int, str]:
    """'Jan 05, 2030': the last class day each expiring announcement shows, keyed by id.

    ``expires_at`` is stored as that day's exclusive end.
    """
    return {
        a.id: obligations_service.last_class_day_before(class_id, a.expires_at).strftime("%b %d, %Y")
        for a in announcements
        if a.expires_at
    }
