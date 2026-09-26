"""Alerts are the shared alert card, never a raw Bootstrap `.alert` box.

The app migrated alerts to `macros/cards.html` → `alert_card` (a card with a
headed title, styled in style.css). A raw `class="alert ..."` in a template
bypasses that look and its heading structure; two had crept back by
2026-09-26. This guard scans every template except the macros that define
the card.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
_RAW_ALERT = re.compile(r"""class\s*=\s*["'](?:[^"']*\s)?alert(?:\s[^"']*)?["']""")


def find_raw_alerts(source: str) -> list[str]:
    """Class attributes that make an element a Bootstrap `.alert` box."""
    return [m.group(0) for m in _RAW_ALERT.finditer(source)]


def test_no_template_uses_a_raw_bootstrap_alert():
    offenders = {
        str(path.relative_to(TEMPLATES)): hits
        for path in TEMPLATES.rglob("*.html")
        if "macros" not in path.parts
        for hits in [find_raw_alerts(path.read_text(encoding="utf-8"))]
        if hits
    }
    assert not offenders, f"use cards.alert_card instead: {offenders}"


def test_detector_catches_raw_alerts_and_ignores_lookalikes():
    """Mutation proof (SOP-TEST-003 §IX.A): near misses a real edit would use."""
    assert find_raw_alerts('<div class="alert alert-warning py-2">')
    assert find_raw_alerts("<div class='mb-3 alert alert-info' role=\"alert\">")
    assert find_raw_alerts('<div class="alert">')
    assert find_raw_alerts('<div class = "d-flex alert">')
    assert not find_raw_alerts('<div class="card alert-card border-warning">')
    assert not find_raw_alerts('<div role="alert">')
    assert not find_raw_alerts('<span class="alert-heading">')
