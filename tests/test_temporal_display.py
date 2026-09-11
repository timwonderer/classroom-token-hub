"""Regression tests for portable temporal display formatting."""

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment

from app.utils.temporal_display import (
    fmt_timestamp,
    format_compact_date,
    format_date,
    format_time,
    format_timestamp,
)

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"


def test_temporal_formatters_are_portable_and_timezone_aware():
    """Display formatting avoids platform-specific strftime directives."""
    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)

    assert format_timestamp(value, "America/New_York") == "Jan 3, 2026, 1:05 PM EST"
    assert format_date(value, "America/New_York") == "Jan 3, 2026"
    assert format_compact_date(value, "America/New_York") == "Jan 3"
    assert format_time(value, "America/New_York") == "1:05 PM EST"


def test_template_timestamps_follow_display_timezone():
    """The Jinja filter reads the class timezone from context rather than a fixed default."""
    env = Environment(autoescape=True)
    env.filters["fmt_timestamp"] = fmt_timestamp
    template = env.from_string("{{ value | fmt_timestamp }}")
    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)

    assert template.render(value=value, display_timezone="America/New_York") == "Jan 3, 2026, 1:05 PM EST"
    assert template.render(value=value, display_timezone="Pacific/Honolulu") == "Jan 3, 2026, 8:05 AM HST"


def test_hall_pass_template_uses_canonical_temporal_filters():
    """Hall pass times render in the class timezone; a Pacific-defaulting filter would misreport them."""
    source = (TEMPLATE_ROOT / "admin_hall_pass.html").read_text()

    assert "format_datetime" not in source
    assert source.count("| fmt_timestamp }}") == 3