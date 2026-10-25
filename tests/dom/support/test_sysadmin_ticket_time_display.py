"""Sysadmin support builders hand templates presentation-ready times (SPEC-UI-001 §VII)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.support.builders import build_correlation_pack_view, build_issue_view

_ESCALATED = datetime(2026, 9, 22, 5, 56, tzinfo=timezone.utc)


def test_in_review_since_falls_back_to_escalation_time_under_sle(app):
    with app.app_context():
        view = build_issue_view({"submitted_at": None, "escalated_at": _ESCALATED,
                                 "sysadmin_reviewed_at": None, "sysadmin_resolved_at": None})
    assert view["in_review_since_display"] == "Sep 22, 2026, 5:56 AM UTC"
    assert view["escalated_at_display"] == "Sep 22, 2026, 5:56 AM UTC"
    assert view["submitted_at_display"] == "—"


def test_correlation_pack_display_leaves_stored_artifacts_untouched(app):
    trace = [{"timestamp": "2026-09-22T05:56:18+00:00", "method": "GET"}]
    with app.app_context():
        view = build_correlation_pack_view({"request_trace_json": trace, "error_refs_json": None})
    assert view["request_trace_json"][0]["timestamp_display"] == "Sep 22, 2026, 5:56 AM UTC"
    assert view["error_refs_json"] == []
    assert "timestamp_display" not in trace[0]
