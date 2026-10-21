"""The timed destruction gate, as a screen-reader and keyboard user meets it (INV-ARC-020).

VoiceOver on the Delete Class gate, 2026-10-20: Tab read the title, Cancel and
"Enter the confirmation phrase shown below", and nothing else. The warnings
were tied to nothing, the phrase itself was never read, and the hold button
(HTML `disabled`) was out of the Tab order, so its existence and its unlock
were silent. The student-deletion page carried its own stale copy of the gate
without even the keyboard hold.

This renders the shared component through Jinja, loads the real
timed-delete-gate.js and Bootstrap into Chromium, and reads Chromium's
accessibility tree over CDP. Playwright's clock skips the 30-second countdown
and the 10-second hold.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

REPO = Path(__file__).resolve().parent.parent
ORIGIN = "http://cth.test"
SCRIPTS = {
    "/static/vendor/bootstrap/bootstrap.bundle.min.js": "static/vendor/bootstrap/bootstrap.bundle.min.js",
    "/static/js/app-core.js": "static/js/app-core.js",
    "/static/js/timed-delete-gate.js": "static/js/timed-delete-gate.js",
}
GATE = (
    Environment(loader=FileSystemLoader(REPO / "templates"))
    .get_template("components/timed_delete_gate.html")
    .module.timed_delete_gate()
)
PAGE = f"""<!doctype html><html lang="en"><head><title>Delete</title></head><body>
<main><h1>Delete Class</h1><button type="button" id="start">Delete this class</button></main>
{GATE}
<script src="/static/vendor/bootstrap/bootstrap.bundle.min.js"></script>
<script src="/static/js/app-core.js"></script>
<script src="/static/js/timed-delete-gate.js"></script>
<script>
  document.getElementById('start').addEventListener('click', () => {{
    window.__gate = undefined;
    showTimedDeleteGate({{
      title: 'Safety Check: Please Read Carefully',
      warning: 'You are about to permanently delete Gooner Club.',
      expectedPhrase: 'DELETE GOONER CLUB',
      bullets: ['You are performing an irreversible action.', 'Recovery of this class is not possible.'],
    }}).then((payload) => {{ window.__gate = payload; }});
  }});
</script>
</body></html>"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")
        with chromium:
            page = chromium.new_page()

            def serve(source):
                body = (REPO / source).read_bytes()
                return lambda route: route.fulfill(status=200, content_type="application/javascript", body=body)

            for path, source in SCRIPTS.items():
                page.route(f"{ORIGIN}{path}", serve(source))
            page.route(f"{ORIGIN}/delete", lambda route: route.fulfill(status=200, content_type="text/html", body=PAGE))
            page.clock.install()
            page.goto(f"{ORIGIN}/delete")
            page.click("#start")
            page.clock.run_for(1000)  # fade-in
            page.locator("#timedDeleteGateModal.show").wait_for()
            yield page


def ax_nodes(page):
    cdp = page.context.new_cdp_session(page)
    try:
        return cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()


def ax(page, role, name_prefix):
    for node in ax_nodes(page):
        name = (node.get("name") or {}).get("value") or ""
        if not node.get("ignored") and (node.get("role") or {}).get("value") == role and name.startswith(name_prefix):
            return node
    raise AssertionError(f"no exposed {role} named {name_prefix!r}")


def description(node):
    return (node.get("description") or {}).get("value") or ""


def finish_countdown(page):
    page.clock.run_for(31_000)
    page.wait_for_function("() => document.activeElement.id === 'timed-delete-phrase'")


def test_opening_the_gate_announces_the_warning_and_every_bullet(page):
    text = description(ax(page, "dialog", "Safety Check: Please Read Carefully"))
    assert "You are about to permanently delete Gooner Club." in text
    assert "You are performing an irreversible action." in text
    assert "Recovery of this class is not possible." in text


def test_the_phrase_field_reads_the_phrase_to_type(page):
    finish_countdown(page)
    text = description(ax(page, "textbox", "Enter the confirmation phrase"))
    assert "Required phrase: DELETE GOONER CLUB" in text
    assert "Countdown complete" in text


def test_the_locked_hold_button_is_reachable_and_says_why(page):
    finish_countdown(page)
    page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement.id") == "timed-delete-hold-btn"

    button = ax(page, "button", "Hold to Confirm")
    assert any(p["name"] == "disabled" and p["value"]["value"] for p in button.get("properties", []))
    assert "unlocks after countdown" in description(button)

    page.keyboard.down(" ")
    page.clock.run_for(11_000)
    page.keyboard.up(" ")
    assert page.evaluate("() => window.__gate") is None  # locked: holding does nothing


def test_typing_the_phrase_announces_the_unlock_once(page):
    finish_countdown(page)
    status = page.locator("#timed-delete-hold-status")
    assert status.get_attribute("aria-live") == "polite"

    page.keyboard.type("DELETE GOONER CLU")
    assert "unlocks after countdown" in status.inner_text()
    page.keyboard.type("B")

    assert status.inner_text() == (
        'Hold the Space or Enter key for 10 seconds. You will hear "complete" when the timer is done.'
    )
    assert page.get_attribute("#timed-delete-hold-btn", "aria-disabled") == "false"


def test_a_keyboard_hold_of_ten_seconds_confirms(page):
    finish_countdown(page)
    page.keyboard.type("DELETE GOONER CLUB")
    page.keyboard.press("Tab")

    page.keyboard.down(" ")
    page.clock.run_for(10_100)

    # "Complete" is spoken while the dialog is still open, before anything moves on.
    assert page.locator("#timed-delete-hold-status").inner_text() == "Complete"
    assert page.locator("#timedDeleteGateModal.show").count() == 1
    assert page.evaluate("() => window.__gate") is None
    page.keyboard.up(" ")  # a late release cannot undo it
    page.clock.run_for(500)
    assert page.evaluate("() => window.__gate") is None

    page.clock.run_for(600)
    page.wait_for_function("() => window.__gate !== undefined")
    assert page.evaluate("() => window.__gate") == {
        "gate_phrase": "DELETE GOONER CLUB", "gate_countdown_seconds": 30, "gate_hold_seconds": 10,
    }


def test_holding_does_not_rename_the_focused_button_or_flood_the_live_region(page):
    # VoiceOver, 2026-10-20: the button's own text was rewritten every 100ms
    # during the hold, so the screen reader restarted it each time ("hhhhho").
    finish_countdown(page)
    page.keyboard.type("DELETE GOONER CLUB")
    page.keyboard.press("Tab")
    page.evaluate("""() => {
        window.__mutations = {button: 0, status: 0};
        const watch = (id, key) => new MutationObserver((records) => { window.__mutations[key] += records.length; })
            .observe(document.getElementById(id), {childList: true, characterData: true, subtree: true});
        watch('timed-delete-hold-btn', 'button');
        watch('timed-delete-hold-status', 'status');
    }""")
    timer_texts = set()

    page.keyboard.down(" ")
    for _ in range(9):
        page.clock.run_for(1_000)
        timer_texts.add(page.locator("#timed-delete-hold-timer").inner_text())
    page.keyboard.up(" ")
    page.clock.run_for(100)

    mutations = page.evaluate("() => window.__mutations")
    assert mutations["button"] == 0
    assert mutations["status"] == 1  # silent while holding; only the early-release message
    assert len(timer_texts) >= 8  # sighted users still see it count down
    assert page.get_attribute("#timed-delete-hold-timer", "aria-hidden") == "true"


def test_releasing_early_resets_and_announces_it(page):
    finish_countdown(page)
    page.keyboard.type("DELETE GOONER CLUB")
    page.keyboard.press("Tab")

    page.keyboard.down(" ")
    page.clock.run_for(4_000)
    page.keyboard.up(" ")
    page.clock.run_for(10_000)

    assert page.evaluate("() => window.__gate") is None
    assert page.locator("#timed-delete-hold-status").inner_text() == "Hold must be continuous for 10 seconds."


def gate_copies(files):
    """Where a gate implementation or its modal markup is defined, by path."""
    found = []
    for path, text in files:
        if "function showTimedDeleteGate" in text or 'id="timedDeleteGateModal"' in text:
            found.append(path)
    return sorted(found)


def test_the_gate_has_exactly_one_implementation():
    # admin_students.html carried its own copy, which never received the
    # keyboard hold: keyboard-only teachers could not delete students.
    files = [
        (p.relative_to(REPO).as_posix(), p.read_text(encoding="utf-8"))
        for root in ("templates", "static/js")
        for p in (REPO / root).rglob("*")
        if p.suffix in {".html", ".js"} and p.is_file()
    ]
    assert gate_copies(files) == ["static/js/timed-delete-gate.js", "templates/components/timed_delete_gate.html"]


def test_mutation_proof_a_page_copy_of_the_gate_is_reported():
    forked = [
        ("templates/admin_students.html", "<script>\n  function showTimedDeleteGate(options) {}\n</script>"),
        ("templates/admin_other.html", '<div class="modal" id="timedDeleteGateModal"></div>'),
    ]
    assert gate_copies(forked) == ["templates/admin_other.html", "templates/admin_students.html"]
