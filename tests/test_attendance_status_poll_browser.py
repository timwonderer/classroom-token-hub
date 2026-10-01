"""The dashboard's status poller (static/js/attendance.js), in a real browser.

``tests/test_student_status_rate_limit.py`` proves the server keys its limit
on the seat and answers /api/* 429s in JSON. Neither proves what the page does
with a refusal. The poller used to be a bare ``setInterval``: it kept asking
every 10 seconds however often the server said no, fed the HTML 429 page to
``r.json()``, and the action-triggered ``refreshUi()`` had no ``catch`` at all.

This loads the real script into Chromium, answers its requests from the test,
and drives time with Playwright's fake clock. Request times are read from the
page's own (fake) clock, so the assertions are about the schedule the script
chose, not about how fast the machine running the test is. Playwright and
Chromium are environment-dependent, so their absence skips rather than fails.
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
CLOCK_START = 1_000_000  # seconds since the epoch, as the Python clock API takes them
ATTENDANCE_SCRIPT = (
    Path(__file__).resolve().parent.parent / "static" / "js" / "attendance.js"
).read_text(encoding="utf-8")

# Just enough of student_dashboard.html for updateAttendanceUI to render into.
DASHBOARD = """<!doctype html><html><body>
<table><tr class="attendance-state-row">
  <td class="attendance-status"></td><td class="attendance-duration"></td>
  <td class="attendance-pay"></td>
  <td><button id="startWork"></button><button id="breakWork"></button></td>
</tr></table>
<script>
  window.AppCore = { toast() {}, buildAlertCard() { return document.createElement('div'); } };
</script>
<script src="/static/js/attendance.js"></script>
</body></html>"""

# Records the page's (fake) clock at every status request, and lets the test
# hide and show the tab. Math.random is pinned so the jittered back-off is
# deterministic: RANDOM near 1 takes the ceiling of each back-off window.
INIT_SCRIPT = """
window.__statusRequests = [];
window.__statusPending = 0;
const realFetch = window.fetch.bind(window);
window.fetch = (url, options) => {
  const response = realFetch(url, options);
  if (String(url).includes('/api/student-status')) {
    window.__statusRequests.push(Date.now());
    window.__statusPending += 1;
    const done = () => { window.__statusPending -= 1; };
    response.then(done, done);
  }
  return response;
};
window.__hidden = false;
Object.defineProperty(Document.prototype, 'hidden', { get() { return window.__hidden; } });
Object.defineProperty(Document.prototype, 'visibilityState', {
  get() { return window.__hidden ? 'hidden' : 'visible'; },
});
Math.random = () => window.__random;
window.__random = 0.999999;
"""

OK_STATE = {
    "status": "ok",
    "attendance_state": {
        "active": True, "duration": 5, "duration_today": 65,
        "projected_pay": 1.5, "hall_pass": None, "done": False,
    },
}
HTML_429 = "<!DOCTYPE html><html><body><h1>429</h1><p>Too Many Requests</p></body></html>"


class StatusServer:
    """Answers /api/student-status from a script of responses; the last one repeats."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.held = []
        self.hold = False

    def handle(self, route):
        if self.hold:
            self.held.append(route)
            return
        self._answer(route)

    def _answer(self, route):
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        route.fulfill(**response)

    def release(self):
        self.hold = False
        while self.held:
            self._answer(self.held.pop(0))


def ok():
    return {"status": 200, "content_type": "application/json", "body": json.dumps(OK_STATE)}


def too_many(retry_after=None, html=True):
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    if html:
        return {"status": 429, "content_type": "text/html", "body": HTML_429, "headers": headers}
    body = json.dumps({"status": "error", "error": "Too many requests."})
    return {"status": 429, "content_type": "application/json", "body": body, "headers": headers}


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")
        with chromium:
            yield chromium


def open_dashboard(browser, server):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script(INIT_SCRIPT)
    page.clock.install(time=CLOCK_START)
    page.route(f"{ORIGIN}/student/dashboard", lambda route: route.fulfill(
        status=200, content_type="text/html", body=DASHBOARD))
    page.route(f"{ORIGIN}/static/js/attendance.js", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=ATTENDANCE_SCRIPT))
    page.route(f"{ORIGIN}/student/login*", lambda route: route.fulfill(
        status=200, content_type="text/html", body="<p>login</p>"))
    page.route(f"{ORIGIN}/api/student-status", server.handle)
    page.goto(f"{ORIGIN}/student/dashboard")
    page.clock.pause_at(CLOCK_START + 0.5)
    return page, errors


def settle(page):
    """Let answered requests finish their promise chains.

    The page's clock is paused, so only real I/O and promise jobs are pending:
    wait for every status response to arrive, then give the script's own chain
    (body parsing, rescheduling) a moment of real time. Nothing here reads the
    script's internals, so the same harness runs against any version of it.
    """
    for _ in range(200):
        if page.evaluate("() => window.__statusPending === 0"):
            page.wait_for_timeout(25)  # Playwright's timer, not the page's
            return
        page.wait_for_timeout(5)
    raise AssertionError("status request never answered")


def advance(page, seconds):
    """Run the page's clock forward one second at a time, settling after each."""
    for _ in range(seconds):
        page.clock.run_for(1000)
        settle(page)


def request_times(page):
    times = page.evaluate("() => window.__statusRequests")
    return [t / 1000 - CLOCK_START for t in times]


def gaps(times):
    return [round(b - a, 1) for a, b in zip(times, times[1:])]


def test_continuous_429_backs_off_to_a_minute_instead_of_every_10_seconds(browser):
    page, errors = open_dashboard(browser, StatusServer(too_many()))

    advance(page, 300)

    times = request_times(page)
    assert 9.5 <= times[0] <= 11  # the first poll is one interval after load
    # Back-off ceilings with the jitter pinned high: 20s, 40s, then capped at 60s.
    assert gaps(times) == pytest.approx([20, 40, 60, 60, 60], abs=1.5)
    assert errors == []


def test_retry_after_is_honoured(browser):
    server = StatusServer(too_many(retry_after=45, html=False), ok())
    page, _ = open_dashboard(browser, server)
    page.evaluate("() => { window.__random = 0; }")  # jitter would allow 10s

    advance(page, 70)

    assert gaps(request_times(page))[0] == pytest.approx(45, abs=1.5)


def test_one_success_returns_the_poll_to_every_10_seconds(browser):
    server = StatusServer(too_many(), too_many(), ok())
    page, errors = open_dashboard(browser, server)

    advance(page, 150)

    times = request_times(page)
    assert gaps(times)[:2] == pytest.approx([20, 40], abs=1.5)
    assert set(gaps(times)[2:]) and all(abs(g - 10) <= 1.5 for g in gaps(times)[2:])
    assert page.inner_text(".attendance-status") == "Active"
    assert page.inner_text(".attendance-duration") == "0h 1m 5s"
    assert errors == []


def test_a_hidden_tab_does_not_poll_and_polls_at_once_when_shown(browser):
    page, _ = open_dashboard(browser, StatusServer(ok()))
    advance(page, 25)
    assert len(request_times(page)) == 2

    page.evaluate("() => { window.__hidden = true; document.dispatchEvent(new Event('visibilitychange')); }")
    advance(page, 120)
    assert len(request_times(page)) == 2

    page.evaluate("() => { window.__hidden = false; document.dispatchEvent(new Event('visibilitychange')); }")
    advance(page, 1)
    times = request_times(page)
    assert len(times) == 3
    assert times[2] == pytest.approx(146, abs=1.5)  # on showing, not on a leftover timer

    advance(page, 10)
    assert len(request_times(page)) == 4


def test_only_one_status_request_is_ever_on_the_wire(browser):
    server = StatusServer(ok())
    page, _ = open_dashboard(browser, server)
    server.hold = True

    page.clock.run_for(10_000)            # the scheduled poll goes out and hangs
    page.evaluate("() => { refreshUi(); refreshUi(); refreshUi(); }")  # three actions finish
    page.clock.run_for(30_000)            # three more intervals pass
    page.wait_for_timeout(100)
    assert len(request_times(page)) == 1

    server.release()                      # the hung poll answers; one queued refresh follows
    settle(page)
    advance(page, 1)
    assert len(request_times(page)) == 2


def test_refresh_after_an_action_does_not_throw_on_an_html_429(browser):
    page, errors = open_dashboard(browser, StatusServer(too_many()))

    page.evaluate("() => refreshUi()")
    page.clock.run_for(0)
    settle(page)
    page.wait_for_timeout(100)

    assert len(request_times(page)) == 1
    assert errors == []


def test_a_401_still_sends_the_student_to_login(browser):
    unauthorized = {"status": 401, "content_type": "application/json",
                    "body": json.dumps({"status": "error", "error": "Session expired"})}
    page, _ = open_dashboard(browser, StatusServer(unauthorized))

    with page.expect_navigation(url=f"{ORIGIN}/student/login?session_expired=1"):
        page.clock.run_for(10_000)
