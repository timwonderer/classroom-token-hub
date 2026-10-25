"""Support domain page builders (SPEC-UI-001 §VII, §IX).

Times arrive at the sysadmin support templates as presentation-ready text,
localized through ``canonical_temporal_resolver`` by ``app.utils.temporal_display``.
``temporal_context`` is the display lens the route chose: ``None`` for SLE (UTC,
the Operations default), or an object carrying the ticket's ``class_id`` when the
operator selects class time. It is a display choice, never class context on the
request (INV-ARC-019, INV-ARC-022 §V.3).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.utils.temporal_display import format_timestamp

_ISSUE_TIME_FIELDS = ("submitted_at", "escalated_at", "sysadmin_reviewed_at", "sysadmin_resolved_at")


def build_issue_view(issue_view: dict, temporal_context=None) -> dict:
    """Add ``<field>_display`` for each ticket time, plus ``in_review_since_display``."""
    view = dict(issue_view)
    for field in _ISSUE_TIME_FIELDS:
        view[f"{field}_display"] = format_timestamp(temporal_context, issue_view.get(field))
    view["in_review_since_display"] = format_timestamp(
        temporal_context,
        issue_view.get("sysadmin_reviewed_at") or issue_view.get("escalated_at"),
    )
    return view


def build_teacher_report_rows(reports, temporal_context=None) -> list[SimpleNamespace]:
    """Teacher-ticket rows with ``submitted_at_display``."""
    return [
        SimpleNamespace(**vars(report), submitted_at_display=format_timestamp(temporal_context, report.submitted_at))
        for report in reports
    ]


def _with_timestamp_display(entries, temporal_context):
    # Correlation-pack entries freeze their timestamps as ISO strings (app/services/tlcp.py).
    return [
        {**entry, "timestamp_display": format_timestamp(temporal_context, entry.get("timestamp"))}
        for entry in entries or []
    ]


def build_correlation_pack_view(pack_view: dict | None, temporal_context=None) -> dict | None:
    """Correlation pack with ``timestamp_display`` on each request trace and error ref.

    The stored artifacts are not modified (INV-ARC-015 §X.1): new lists are built.
    """
    if not pack_view:
        return None
    return {
        **pack_view,
        "request_trace_json": _with_timestamp_display(pack_view.get("request_trace_json"), temporal_context),
        "error_refs_json": _with_timestamp_display(pack_view.get("error_refs_json"), temporal_context),
    }


def build_history_rows(history, temporal_context=None) -> list[dict]:
    """Status-history rows with ``changed_at_display``."""
    return [
        {**entry, "changed_at_display": format_timestamp(temporal_context, entry.get("changed_at"))}
        for entry in history
    ]
