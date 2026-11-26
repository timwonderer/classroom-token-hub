"""A PIN field must not advertise itself as the account password.

`autocomplete="current-password"` on a PIN input lets Chrome save the PIN as the
password for the site, then autofill it into every passphrase prompt — the
Store purchase then fails with "Incorrect passphrase" (support ticket #13).
"""
import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_INPUT = re.compile(r"<input\b[^>]*>", re.S | re.I)
# HTML allows double-quoted, single-quoted and unquoted attribute values.
_ATTRIBUTE = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def _attributes(tag):
    return {
        match.group(1).lower(): next(v for v in match.groups()[1:] if v is not None)
        for match in _ATTRIBUTE.finditer(tag)
    }


def pin_inputs_marked_as_password(html):
    found = []
    for tag in _INPUT.findall(html):
        attributes = _attributes(tag)
        # autocomplete is a space-separated token list (e.g. "section-a current-password").
        tokens = attributes.get("autocomplete", "").lower().split()
        if attributes.get("name", "").lower() == "pin" and "current-password" in tokens:
            found.append(tag)
    return found


def test_no_template_pin_input_uses_current_password_autocomplete():
    offenders = {
        str(p.relative_to(TEMPLATES)): found
        for p in TEMPLATES.rglob("*.html")
        if (found := pin_inputs_marked_as_password(p.read_text(encoding="utf-8")))
    }
    assert not offenders, offenders


def test_detector_reports_the_transfer_pin_shape_that_caused_ticket_13():
    regressed = (
        '<input type="password" class="form-control" name="pin" id="passphrase"\n'
        '    autocomplete="current-password" required autofocus>'
    )
    assert pin_inputs_marked_as_password(regressed)
    assert not pin_inputs_marked_as_password(
        '<input type="password" name="passphrase" autocomplete="current-password">'
    )



@pytest.mark.parametrize("tag", [
    "<input type='password' name='pin' autocomplete='current-password'>",
    "<input type=password name=pin autocomplete=current-password>",
    '<INPUT TYPE="password" NAME="PIN" AUTOCOMPLETE="Current-Password">',
    '<input name="pin" autocomplete="section-transfer current-password">',
])
def test_detector_reports_every_valid_spelling(tag):
    assert pin_inputs_marked_as_password(tag), tag


def test_detector_ignores_lookalike_names_and_tokens():
    assert not pin_inputs_marked_as_password('<input name="pin_hint" autocomplete="current-password">')
    assert not pin_inputs_marked_as_password('<input name="pin" autocomplete="one-time-code">')
