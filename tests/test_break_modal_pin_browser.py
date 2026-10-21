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
ATTENDANCE_SCRIPT = (
    Path(__file__).resolve().parent.parent / "static" / "js" / "attendance.js"
).read_text(encoding="utf-8")

# The break modal from student_dashboard.html, without Bootstrap.
DASHBOARD = """<!doctype html><html><body>
<div id="breakChoiceModal">
  <input type="password" id="breakPinInput">
  <div id="hallPassDestinationSection" hidden><div id="hallPassDestinationList"></div></div>
  <button type="button" id="doneForDayBreakBtn">Done for the day</button>
</div>
<script>
  window.__posts = [];
  window.AppCore = {
    toast() {}, buildAlertCard() { return document.createElement('div'); },
    csrfFetch(url, options) {
      window.__posts.push({ url, body: JSON.parse(options.body) });
      return Promise.resolve({ json: () => ({ status: 'success' }) });
    },
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
            page.route(f"{ORIGIN}/static/js/attendance.js", lambda route: route.fulfill(
                status=200, content_type="application/javascript", body=ATTENDANCE_SCRIPT))
            page.route(f"{ORIGIN}/api/hall-pass/available-types", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(TYPES)))
            page.route(f"{ORIGIN}/api/student-status", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(OK_STATE)))
            page.goto(f"{ORIGIN}/student/dashboard")
            page.evaluate("openBreakChoiceModal()")
            page.get_by_role("button", name="Bathroom").wait_for()
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
