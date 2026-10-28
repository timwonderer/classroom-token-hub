"""A PIN field must not advertise itself as the account password.

`autocomplete="current-password"` on a PIN input lets Chrome save the PIN as the
password for the site, then autofill it into every passphrase prompt — the
Store purchase then fails with "Incorrect passphrase" (support ticket #13).
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_INPUT = re.compile(r"<input\b[^>]*>", re.S)


def pin_inputs_marked_as_password(html):
    return [
        tag for tag in _INPUT.findall(html)
        if re.search(r'name="pin"', tag) and 'autocomplete="current-password"' in tag
    ]


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
