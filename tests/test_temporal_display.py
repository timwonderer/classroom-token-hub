"""Regression tests for portable temporal display formatting."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.utils.temporal_display import (
    format_compact_date,
    format_date,
    format_time,
    format_timestamp,
)

from tests.helpers.canonical_classroom import provision_classroom

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"


def test_temporal_formatters_are_portable_and_timezone_aware(app):
    """Display formatting avoids platform-specific strftime directives and
    localizes through the resolver: CLE in the class timezone, SLE in UTC."""
    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)

    with app.app_context():
        ctx = SimpleNamespace(class_id=provision_classroom("chemistry_p1").class_id)  # America/Los_Angeles
        assert format_timestamp(ctx, value) == "Jan 3, 2026, 10:05 AM PST"
        assert format_date(ctx, value) == "Jan 3, 2026"
        assert format_compact_date(ctx, value) == "Jan 3"
        assert format_time(ctx, value) == "10:05 AM PST"

    assert format_timestamp(None, value) == "Jan 3, 2026, 6:05 PM UTC"


def test_class_local_date_differs_from_utc_date(app):
    """A late-evening class-local instant is already the next day in UTC; the
    date shown is the class's, not UTC's."""
    value = datetime(2026, 1, 4, 3, 0, tzinfo=timezone.utc)  # Jan 3, 7 PM in Los Angeles

    with app.app_context():
        ctx = SimpleNamespace(class_id=provision_classroom("chemistry_p1").class_id)
        assert format_date(ctx, value) == "Jan 3, 2026"
    assert format_date(None, value) == "Jan 4, 2026"


def test_INV_ARC_022__no_jinja_filter_formats_a_time(app):
    """Templates print builder-formatted text (SPEC-UI-001 §X); the app registers no
    time filter, because resolving a class timezone while rendering is a database
    read (INV-ARC-022 §V.8)."""
    time_filters = {name for name in app.jinja_env.filters if name.startswith("fmt_")}
    assert not time_filters
    assert "format_utc_iso" not in app.jinja_env.globals


def test_hall_pass_times_arrive_formatted_in_class_time(app):
    """Hall pass times are built in the class timezone and the template only prints them
    (INV-ARC-022 §V.8); a Pacific-defaulting or template-side formatter would misreport them."""
    from app.services.payroll.builders import add_hall_pass_time_displays

    source = (TEMPLATE_ROOT / "admin_hall_pass.html").read_text()
    assert "format_datetime" not in source and "fmt_" not in source
    for field in ("request_time", "decision_time", "left_time"):
        assert f"{{{{ req.{field}_display }}}}" in source

    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)
    with app.app_context():
        ctx = SimpleNamespace(class_id=provision_classroom("chemistry_p1").class_id)
        pending, issued = SimpleNamespace(request_time=value), SimpleNamespace(decision_time=value, left_time=None)
        add_hall_pass_time_displays(ctx, [pending, issued])
    assert pending.request_time_display == "Jan 3, 2026, 10:05 AM PST"
    assert issued.decision_time_display == "Jan 3, 2026, 10:05 AM PST"
    assert issued.left_time_display == "—"
    assert not hasattr(pending, "left_time_display")


def test_fmt_timestamp_accepts_iso_string_from_correlation_pack():
    """TLCP correlation packs (DOM-OPS-001) freeze request-trace timestamps as
    ISO strings inside a JSON column (tlcp.py: row.created_at.isoformat()).
    sysadmin_view_issue.html renders trace.timestamp|fmt_timestamp directly on
    that JSON value -- confirmed live as an AttributeError 500 on
    /sysadmin/issues/<ref> for any ticket with a non-empty request trace.
    """
    iso_value = "2026-09-22T05:56:18.924000+00:00"

    assert format_timestamp(None, iso_value) == "Sep 22, 2026, 5:56 AM UTC"