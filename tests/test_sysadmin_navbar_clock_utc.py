"""The sysadmin navbar clock must show UTC, never the operator's browser-local time.

INV-ARC-015 SS X.2: operations surfaces default to UTC with no exception and
no inference from browser locale. `toLocaleDateString(undefined, ...)` /
`toLocaleTimeString(undefined, ...)` resolve `undefined` to the browser's own
locale/timezone -- exactly the "Tim happens to be in Los Angeles" case the
rule forbids. Every sysadmin clock reader (this widget, Grafana correlation,
audit records) must be reading the same baseline.
"""
from pathlib import Path

SOURCE = Path("templates/layout_system_admin.html").read_text(encoding="utf-8")


def test_navbar_clock_does_not_use_browser_locale_inference():
    assert "toLocaleDateString(undefined" not in SOURCE
    assert "toLocaleTimeString(undefined" not in SOURCE


def test_navbar_clock_explicitly_requests_utc():
    assert "timeZone: 'UTC'" in SOURCE
    # Both the date and time formatters need it independently -- one fixed
    # instance would leave the other silently browser-local again.
    assert SOURCE.count("timeZone: 'UTC'") >= 2


def test_navbar_clock_labels_itself_utc():
    assert "' UTC'" in SOURCE or '" UTC"' in SOURCE
