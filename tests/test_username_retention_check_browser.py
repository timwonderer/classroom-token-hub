"""The username retention check's page script, exercised in a real browser.

``tests/dom/identity/test_username_retention_check.py`` proves the server
decides the check and fails closed. This drives
``static/js/username_retention_check.js`` against the setup page the app
renders, with the check endpoint stubbed, to prove what the student sees: the
modal hides the username, only "Show my username again" brings it
back, a match unlocks the PIN and passphrase, and paste is refused on the check
input only.

The page is served from an intercepted origin so it needs no network. Playwright
and Chromium are environment-dependent, so their absence skips rather than fails.
"""

import json
import re
import mimetypes
import os
from urllib.parse import urlparse
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

from bs4 import BeautifulSoup
from flask import render_template

from app import app as flask_app
from app.forms import StudentPinPassphraseForm, StudentVerifySavedUsernameForm

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

ORIGIN = "http://cth.test"
USERNAME = "river-otter-soilAD"
SCRIPT = (
    Path(__file__).resolve().parent.parent / "static" / "js" / "username_retention_check.js"
).read_text(encoding="utf-8")


def _setup_page_html():
    # Render as production does. The suite's app fixture turns CSRF off on this
    # shared app, which would drop the token field the script sends.
    previous = flask_app.config.get("WTF_CSRF_ENABLED", True)
    flask_app.config["WTF_CSRF_ENABLED"] = True
    try:
        with flask_app.test_request_context("/"):
            html = render_template(
                "student_pin_setup.html", username=USERNAME, username_verified=False,
                retention_page_token="browser-test-page-token",
                form=StudentPinPassphraseForm(), verify_form=StudentVerifySavedUsernameForm(),
            )
    finally:
        flask_app.config["WTF_CSRF_ENABLED"] = previous
    assert 'name="csrf_token"' in html
    # Drop external scripts; inline the one under test and stub the strength meter.
    document = BeautifulSoup(html, 'html.parser')
    for script in document.select('script[src]'):
        script.decompose()
    html = str(document)
    return html.replace(
        "<script>",
        "<script>window.zxcvbn = () => ({score: 4});</script>"
        f"<script>{SCRIPT}</script><script>",
        1,
    )


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")
        with browser:
            page = browser.new_page()
            root = Path(__file__).resolve().parent.parent
            def asset(route):
                path = root / urlparse(route.request.url).path.lstrip('/')
                if path.is_file() and path.is_relative_to(root / 'static'):
                    route.fulfill(path=str(path), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                else:
                    route.abort()
            page.route(f"{ORIGIN}/static/**", asset)
            yield page


def _open(page, verified: bool):
    html = _setup_page_html()
    submitted = []

    def check(route):
        assert route.request.headers.get("x-csrftoken"), "check request carries no CSRF token"
        # FormData posts multipart; keep just the field values.
        submitted.append(dict(re.findall(
            r'name="([^"]+)"\r\n\r\n(.*?)\r\n', route.request.post_data or "")))
        body = {"verified": True} if verified else {
            "verified": False,
            "message": "That doesn't match your username. Check the copy you saved and try again.",
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route(f"{ORIGIN}/student/setup-pin-passphrase",
               lambda route: route.fulfill(status=200, content_type="text/html", body=html))
    page.route(f"{ORIGIN}/student/verify-username", check)
    page.goto(f"{ORIGIN}/student/setup-pin-passphrase")
    return submitted


def _username_visible(page):
    return USERNAME in page.inner_text("body")


def test_opening_the_check_hides_the_username(page):
    _open(page, verified=True)
    assert _username_visible(page)
    page.click("[data-open-retention-check]")
    assert page.evaluate("document.getElementById('retention-check-dialog').open")
    assert USERNAME not in page.evaluate("document.body.innerText")
    assert USERNAME not in page.content()
    assert page.evaluate("document.activeElement.id") == "saved-username"


def test_show_my_username_again_brings_back_the_same_username(page):
    _open(page, verified=True)
    page.click("[data-open-retention-check]")
    page.click("[data-show-username-again]")
    assert not page.evaluate("document.getElementById('retention-check-dialog').open")
    assert _username_visible(page)
    # Escape closes it the same way.
    page.click("[data-open-retention-check]")
    page.keyboard.press("Escape")
    page.wait_for_function("!document.getElementById('retention-check-dialog').open")
    page.wait_for_function(f"document.body.innerText.includes({USERNAME!r})")


def test_a_mismatch_keeps_the_username_hidden_and_announces_the_error(page):
    submitted = _open(page, verified=False)
    page.click("[data-open-retention-check]")
    page.fill("#saved-username", "river-otter-soil")
    page.click("#retention-check-dialog button[type=submit]")
    page.wait_for_function("document.getElementById('retention-check-result-message').textContent.length > 0")
    assert page.evaluate("document.getElementById('retention-check-dialog').open")
    assert submitted[0]["saved_username"] == "river-otter-soil"
    assert not _username_visible(page)
    assert "That doesn't match your username" in page.inner_text("#retention-check-result")
    assert page.evaluate("document.activeElement.id") == "retention-check-result"
    assert page.is_disabled("#pin")


def test_a_match_unlocks_setup_and_removes_the_username(page):
    _open(page, verified=True)
    assert page.is_disabled("#pin")
    page.click("[data-open-retention-check]")
    page.type("#saved-username", USERNAME)
    page.click("#retention-check-dialog button[type=submit]")
    page.wait_for_function("!document.getElementById('retention-check-dialog').open")
    assert not page.is_disabled("#pin")
    assert page.evaluate("document.activeElement.id") == "pin"
    assert not _username_visible(page)
    assert page.is_visible("[data-username-verified-note]")


def _paste(page, selector, text="pasted"):
    return page.evaluate(
        """([selector, text]) => {
            const el = document.querySelector(selector);
            const data = new DataTransfer();
            data.setData('text/plain', text);
            const event = new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true});
            el.dispatchEvent(event);
            return event.defaultPrevented;
        }""",
        [selector, text],
    )


def test_paste_is_refused_on_the_check_input_only(page):
    _open(page, verified=True)
    page.click("[data-open-retention-check]")
    assert _paste(page, "#saved-username") is True
    assert "Pasting is turned off" in page.inner_text("#retention-paste-notice")
    # Typing is unaffected.
    page.type("#saved-username", "abc")
    assert page.input_value("#saved-username") == "abc"
    page.click("[data-show-username-again]")
    # No other input on the page is guarded.
    assert _paste(page, "#passphrase") is False


def test_the_accommodation_turns_paste_back_on_and_is_reported(page):
    submitted = _open(page, verified=True)
    page.click("[data-open-retention-check]")
    page.click(".retention-paste-accommodation summary")
    page.click("[data-allow-paste]")
    assert _paste(page, "#saved-username") is False
    page.fill("#saved-username", USERNAME)
    page.click("#retention-check-dialog button[type=submit]")
    page.wait_for_function("!document.getElementById('retention-check-dialog').open")
    assert submitted[0]["paste_accommodation"] == "1"


def test_copy_remains_available_and_reopening_clears_the_answer(page):
    _open(page, verified=False)
    page.evaluate("""() => {
        window.copiedUsername = null;
        Object.defineProperty(navigator, 'clipboard', {value: {
            writeText: async value => {window.copiedUsername = value;}
        }});
    }""")
    page.click('[data-copy-username]')
    assert page.evaluate('window.copiedUsername') == USERNAME
    page.click('[data-open-retention-check]')
    page.fill('#saved-username', 'incorrect')
    page.click('[data-show-username-again]')
    assert page.evaluate('document.activeElement.hasAttribute("data-open-retention-check")')
    page.click('[data-open-retention-check]')
    assert page.input_value('#saved-username') == ''
    assert not _username_visible(page)


def test_normal_login_allows_paste_and_password_managers(page):
    from app.forms import StudentLoginForm
    with flask_app.test_request_context('/'):
        html = render_template('student_login.html', form=StudentLoginForm())
    page.route(f'{ORIGIN}/student/login', lambda route: route.fulfill(content_type='text/html', body=html))
    page.goto(f'{ORIGIN}/student/login')
    assert not _paste(page, '#studentUsername')
    assert not _paste(page, '#studentPassphrase')
    assert page.get_attribute('#studentUsername', 'autocomplete') == 'username'


@pytest.mark.parametrize('width', [390, 1280])
def test_retention_states_have_no_axe_violations(page, width):
    page.set_viewport_size({'width': width, 'height': 900})
    _open(page, verified=False)
    axe = (Path(__file__).resolve().parent / 'assets' / 'axe-core.min.js').read_text()
    page.add_script_tag(content=axe)
    evidence_dir = os.environ.get('CTH_UI_EVIDENCE_DIR')
    stage = iter(['presentation', 'verification', 'mismatch'])
    def audit():
        if evidence_dir:
            target = Path(evidence_dir)
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f'{width}-{next(stage)}.png'), full_page=True)
        violations = page.evaluate("""async () => (await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}
        })).violations""")
        assert not violations, [(v['id'], [(n['target'], n.get('failureSummary')) for n in v['nodes']]) for v in violations]
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    audit()
    page.click('[data-open-retention-check]')
    audit()
    page.fill('#saved-username', 'incorrect')
    page.click('#retention-check-dialog button[type=submit]')
    page.wait_for_function("document.getElementById('retention-check-result-message').textContent.length > 0")
    audit()


def test_missing_script_keeps_standalone_verification_disabled(page):
    with flask_app.test_request_context('/'):
        html = render_template('student_verify_username.html',
            verify_form=StudentVerifySavedUsernameForm(),
            retention_page_token='browser-test-page-token', error_message=None)
    document = BeautifulSoup(html, 'html.parser')
    for script in document.find_all('script'):
        script.decompose()
    html = str(document)
    page.route(f'{ORIGIN}/student/verify-username',
        lambda route: route.fulfill(content_type='text/html', body=html))
    page.goto(f'{ORIGIN}/student/verify-username')
    assert page.is_disabled('#saved-username')
    assert page.is_disabled('button[type=submit]')
    assert USERNAME not in page.content()
