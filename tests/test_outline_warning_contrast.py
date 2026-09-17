"""Outline warning buttons clear WCAG AA text contrast (SC 1.4.3).

Regression: the roster's Unclaim button used Bootstrap's raw ``--warning`` gold
(#D4A857) as text, 2.2:1 on white and about 1.9:1 on striped rows. Logged-in
teacher pages are not in the axe corpus, so this pins the resolved token pairs.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = (ROOT / "static/css/tokens.css").read_text()
STYLE = (ROOT / "static/css/style.css").read_text()
STRIPED_ROW = "#e8e8e8"  # darker than Bootstrap's striped/hover row tint


def _token(name, seen=()):
    value = re.search(rf"--{re.escape(name)}:\s*([^;]+);", TOKENS).group(1).strip()
    ref = re.fullmatch(r"var\(--([\w-]+)\)", value)
    return _token(ref.group(1), seen + (name,)) if ref else value


def _rule(selector):
    block = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", STYLE).group(1)
    return dict(re.findall(r"([\w-]+):\s*([^;!]+?)\s*(?:!important)?;", block))


def _resolve(value):
    ref = re.fullmatch(r"var\(--([\w-]+)\)", value.strip())
    return _token(ref.group(1)) if ref else value.strip()


def _luminance(hex_color):
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_outline_warning_text_clears_aa_on_light_surfaces():
    text = _resolve(_rule(".btn-outline-warning")["color"])
    for surface in ("#ffffff", STRIPED_ROW):
        assert _contrast(text, surface) >= 4.5, (text, surface)


def test_outline_warning_pressed_state_clears_aa():
    pressed = _rule(".btn-outline-warning:hover,\n.btn-outline-warning:focus-visible,\n.btn-outline-warning:active,\n.btn-outline-warning.active")
    assert _contrast(_resolve(pressed["color"]), _resolve(pressed["background-color"])) >= 4.5


def test_raw_warning_gold_would_fail_as_text():
    # Guards the premise: if --warning itself ever passes, this test can be retired.
    assert _contrast(_token("warning"), "#ffffff") < 4.5


# ── Switch and checkbox boundaries (SC 1.4.11, non-text contrast) ──
#
# A control's boundary and the indicator that carries its state each need 3:1
# against what sits beside them. Bootstrap ships rgba(0, 0, 0, 0.25) for both
# the resting border and the switch thumb — 1.84:1 on a white track — and this
# project then set the *checked* fill to --primary, which on a --primary section
# header is 1.00:1. The Payroll Settings "Advanced Mode" switch showed the
# result: no track, and a white thumb floating in the header.
NON_TEXT_MIN = 3.0
_THUMB = re.compile(r"circle r='3' fill='%23([0-9a-fA-F]{6})'")


def _switch_thumb(selector):
    block = re.search(rf"(?ms)^{re.escape(selector)}\s*\{{(.*?)\}}", STYLE).group(1)
    return "#" + _THUMB.search(block).group(1)


def test_resting_control_border_clears_non_text_contrast():
    border = _resolve(_rule(".form-check-input")["border-color"])
    for surface in ("#ffffff", STRIPED_ROW):
        assert _contrast(border, surface) >= NON_TEXT_MIN, (border, surface)


def test_resting_switch_thumb_clears_non_text_contrast_on_its_track():
    # The unchecked track is the body background, i.e. white.
    assert _contrast(_switch_thumb(".form-switch .form-check-input"), "#ffffff") >= NON_TEXT_MIN


def test_bootstrap_default_control_border_would_fail():
    """Holds the reason this override exists: 25% black on white is 1.84:1."""
    assert _contrast("#bfbfbf", "#ffffff") < NON_TEXT_MIN


def test_checked_switch_is_visible_inside_a_dark_section_header():
    dark = _resolve(_token("primary"))
    fill = _resolve(_rule(".bg-primary .form-check-input:checked,\n.bg-dark .form-check-input:checked")["background-color"])
    assert _contrast(fill, dark) >= NON_TEXT_MIN, (fill, dark)


def test_checked_switch_thumb_is_visible_on_its_own_fill():
    fill = _resolve(_rule(".bg-primary .form-check-input:checked,\n.bg-dark .form-check-input:checked")["background-color"])
    thumb = _switch_thumb(".bg-primary .form-switch .form-check-input:checked,\n.bg-dark .form-switch .form-check-input:checked")
    assert _contrast(thumb, fill) >= NON_TEXT_MIN, (thumb, fill)


def test_primary_fill_on_a_primary_header_would_be_invisible():
    """The defect this replaced: same colour on same colour is 1.00:1."""
    dark = _resolve(_token("primary"))
    assert _contrast(dark, dark) < NON_TEXT_MIN
