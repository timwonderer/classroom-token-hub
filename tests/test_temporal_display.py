"""Regression tests for portable temporal display formatting."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

from app.utils.temporal_display import (
    fmt_timestamp,
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


def test_template_timestamps_follow_class_context(app):
    """The Jinja filter localizes under the template's class context rather than a fixed default."""
    env = Environment(autoescape=True)
    env.filters["fmt_timestamp"] = fmt_timestamp
    template = env.from_string("{{ value | fmt_timestamp }}")
    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)

    with app.app_context():
        class_id = provision_classroom("chemistry_p1").class_id
        assert template.render(value=value, temporal_context=SimpleNamespace(class_id=class_id)) == "Jan 3, 2026, 10:05 AM PST"
    assert template.render(value=value) == "Jan 3, 2026, 6:05 PM UTC"


def test_hall_pass_template_uses_canonical_temporal_filters():
    """Hall pass times render in the class timezone; a Pacific-defaulting filter would misreport them."""
    source = (TEMPLATE_ROOT / "admin_hall_pass.html").read_text()

    assert "format_datetime" not in source
    assert source.count("| fmt_timestamp }}") == 3


def test_fmt_timestamp_accepts_iso_string_from_correlation_pack():
    """TLCP correlation packs (DOM-OPS-001) freeze request-trace timestamps as
    ISO strings inside a JSON column (tlcp.py: row.created_at.isoformat()).
    sysadmin_view_issue.html renders trace.timestamp|fmt_timestamp directly on
    that JSON value -- confirmed live as an AttributeError 500 on
    /sysadmin/issues/<ref> for any ticket with a non-empty request trace.
    """
    iso_value = "2026-09-22T05:56:18.924000+00:00"

    assert format_timestamp(None, iso_value) == "Sep 22, 2026, 5:56 AM UTC"