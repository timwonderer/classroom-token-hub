"""The break modal takes the PIN from its own field, not window.prompt().

Live 2026-10-20: a student on the Google app's in-app browser (iOS) opened the
break modal seven times and chose a destination each time; no hall-pass request
ever reached the server. The destination button called ``prompt()`` from inside
the open modal, the prompt came back empty, and the script returned silently
while the modal closed. Here every native dialog is dismissed, as that browser
behaved, and the request must still go out with the PIN typed into the modal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

ORIGIN = "http://cth.test"
REPO = Path(__file__).resolve().parent.parent
SCRIPTS = {
    "/static/vendor/bootstrap/bootstrap.bundle.min.js": "static/vendor/bootstrap/bootstrap.bundle.min.js",
    "/static/js/app-core.js": "static/js/app-core.js",
    "/static/js/attendance.js": "static/js/attendance.js",
}

# The break modal from student_dashboard.html, on the real Bootstrap and app-core.
DASHBOARD = """<!doctype html><html lang="en"><body>
<button type="button" class="attendance-action-btn" id="breakBtn" data-action="break">Break</button>
<div class="modal fade" id="breakChoiceModal" tabindex="-1" aria-labelledby="breakChoiceModalLabel"><div class="modal-dialog"><div class="modal-content">
  <h2 id="breakChoiceModalLabel">Choose Break Type</h2>
  <label for="breakPinInput">Your PIN</label>
  <input type="password" id="breakPinInput">
  <div class="invalid-feedback" id="breakPinError">Enter your PIN first.</div>
  <div id="hallPassDestinationSection" hidden><div id="hallPassDestinationList"></div></div>
  <button type="button" id="doneForDayBreakBtn">Done for the day</button>
</div></div></div>
<script src="/static/vendor/bootstrap/bootstrap.bundle.min.js"></script>
<script src="/static/js/app-core.js"></script>
<script>
  window.__posts = [];
  window.AppCore.csrfFetch = (url, options) => {
    window.__posts.push({ url, body: JSON.parse(options.body) });
    return Promise.resolve({ json: () => ({ status: 'success' }) });
  };
</script>
<script src="/static/js/attendance.js"></script>
</body></html>"""

TYPES = {"status": "success", "pass_type_payload": [{"name": "Bathroom"}]}
OK_STATE = {"status": "ok", "attendance_state": {"active": True, "hall_pass": None}}


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")
        with chromium:
            page = chromium.new_page()
            page.dialogs = []
            page.on("dialog", lambda dialog: (page.dialogs.append(dialog.message), dialog.dismiss()))
            page.route(f"{ORIGIN}/student/dashboard", lambda route: route.fulfill(
                status=200, content_type="text/html", body=DASHBOARD))
            def serve(source):
                body = (REPO / source).read_bytes()
                return lambda route: route.fulfill(status=200, content_type="application/javascript", body=body)

            for path, source in SCRIPTS.items():
                page.route(f"{ORIGIN}{path}", serve(source))
            page.route(f"{ORIGIN}/api/hall-pass/available-types", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(TYPES)))
            page.route(f"{ORIGIN}/api/student-status", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(OK_STATE)))
            page.goto(f"{ORIGIN}/student/dashboard")
            page.click("#breakBtn")
            page.get_by_role("button", name="Bathroom").wait_for()
            page.wait_for_function("() => document.activeElement.closest('.modal.show')")
            yield page


def test_hall_pass_request_sends_the_modal_pin_without_a_native_dialog(page):
    page.fill("#breakPinInput", "1234")
    page.get_by_role("button", name="Bathroom").click()

    page.wait_for_function("() => window.__posts.length === 1")
    assert page.evaluate("() => window.__posts") == [
        {"url": "/api/hall-pass/request", "body": {"destination": "Bathroom", "pin": "1234"}}
    ]
    assert page.dialogs == []


def test_hall_pass_without_a_pin_shows_an_error_instead_of_doing_nothing(page):
    page.get_by_role("button", name="Bathroom").click()

    assert page.evaluate("() => window.__posts") == []
    assert "is-invalid" in page.get_attribute("#breakPinInput", "class")
    assert page.dialogs == []


def test_an_empty_pin_is_announced_only_once_it_applies(page):
    field = page.get_by_label("Your PIN")
    assert field.get_attribute("aria-describedby") is None

    page.get_by_role("button", name="Bathroom").click()

    assert field.get_attribute("aria-invalid") == "true"
    assert field.get_attribute("aria-describedby") == "breakPinError"
    assert page.evaluate("() => document.activeElement.id") == "breakPinInput"


def test_choosing_a_destination_returns_focus_to_the_break_button(page):
    page.fill("#breakPinInput", "1234")
    page.get_by_role("button", name="Bathroom").click()

    page.wait_for_function("() => document.activeElement.id === 'breakBtn'")
    assert page.evaluate("() => document.querySelectorAll('[inert]').length") == 0
