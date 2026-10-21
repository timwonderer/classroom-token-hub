"""The in-app dialogs that replace the browser's alert/confirm/prompt (INV-ARC-020).

``AppCore.confirm``, ``AppCore.prompt`` and ``data-confirm`` (static/js/app-core.js)
replaced every native dialog after one failed silently in an in-app browser
(2026-10-20; SPEC-DES-001 §X). A native dialog is at least announced by the
platform; its replacement has to earn that. These tests load the real
app-core.js, the vendored Bootstrap and the app's stylesheets into Chromium and
check what a screen reader is given, read from Chromium's own accessibility
tree over CDP (the tree NVDA, JAWS and VoiceOver read in Chrome), plus the
keyboard contract and an axe-core WCAG 2.1 A/AA audit of the open dialog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

REPO = Path(__file__).resolve().parent.parent
ORIGIN = "http://cth.test"
ASSETS = {
    "/static/vendor/bootstrap/bootstrap.min.css": ("text/css", "static/vendor/bootstrap/bootstrap.min.css"),
    "/static/css/tokens.css": ("text/css", "static/css/tokens.css"),
    "/static/css/style.css": ("text/css", "static/css/style.css"),
    "/static/vendor/bootstrap/bootstrap.bundle.min.js": ("application/javascript", "static/vendor/bootstrap/bootstrap.bundle.min.js"),
    "/static/js/app-core.js": ("application/javascript", "static/js/app-core.js"),
}
AXE_SOURCE = (REPO / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")

PAGE = """<!doctype html><html lang="en"><head><title>Dialogs</title>
<link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">
<link href="/static/css/tokens.css" rel="stylesheet">
<link href="/static/css/style.css" rel="stylesheet">
</head><body class="student-shell"><main>
<h1>Page</h1>
<button type="button" id="opener">Open</button>
<button type="button" id="background">Background action</button>
<form id="payForm" method="post" action="/pay">
  <input id="amount" name="amount" value="12.50" aria-label="Amount">
  <button type="submit" id="payBtn" name="choice" value="part"
          data-confirm="Pay ${value} toward this bill?" data-confirm-value-from="amount"
          data-confirm-title="Pay toward bill" data-confirm-label="Pay"
          data-confirm-cancel-label="Not now">Pay</button>
</form>
</main>
<div id="flashToastContainer" class="position-fixed bottom-0 end-0 p-3">
  <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
    <div class="toast-body">Settings saved</div>
    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Dismiss earlier toast"></button>
  </div>
</div>
<script src="/static/vendor/bootstrap/bootstrap.bundle.min.js"></script>
<script src="/static/js/app-core.js"></script>
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
            page.native_dialogs = []
            page.on("dialog", lambda dialog: (page.native_dialogs.append(dialog.type), dialog.dismiss()))
            page.posts = []

            def asset(route):
                path = route.request.url[len(ORIGIN):]
                content_type, source = ASSETS[path]
                route.fulfill(status=200, content_type=content_type, body=(REPO / source).read_bytes())

            for path in ASSETS:
                page.route(f"{ORIGIN}{path}", asset)
            page.route(f"{ORIGIN}/page", lambda route: route.fulfill(status=200, content_type="text/html", body=PAGE))

            def pay(route):
                page.posts.append(route.request.post_data)
                route.fulfill(status=200, content_type="text/html", body="<p>paid</p>")

            page.route(f"{ORIGIN}/pay", pay)
            page.goto(f"{ORIGIN}/page")
            yield page
            assert page.native_dialogs == []


def open_from_opener(page, call: str):
    """Focus the opener and start a dialog from it, as a click handler would."""
    page.evaluate(
        """(call) => {
            document.getElementById('opener').focus();
            window.__result = undefined;
            Promise.resolve(eval(call)).then((value) => { window.__result = value; });
        }""",
        call,
    )
    page.locator(".modal.show").wait_for()
    page.wait_for_function("() => document.activeElement && document.activeElement.closest('.modal.show')")


def result(page):
    page.wait_for_function("() => window.__result !== undefined")
    return page.evaluate("() => window.__result")


def ax_tree(page):
    """Chromium's accessibility tree: what a screen reader is actually given."""
    cdp = page.context.new_cdp_session(page)
    try:
        return cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()


def ax_value(node, key):
    return (node.get(key) or {}).get("value")


def exposed(nodes, role, name):
    return [
        n for n in nodes
        if not n.get("ignored") and ax_value(n, "role") == role and ax_value(n, "name") == name
    ]


def test_confirm_dialog_is_announced_as_a_named_described_modal_dialog(page):
    open_from_opener(page, "AppCore.confirm('Reverse this transaction?', {title: 'Reverse transaction', confirmLabel: 'Reverse'})")
    nodes = ax_tree(page)

    dialogs = exposed(nodes, "dialog", "Reverse transaction")
    assert len(dialogs) == 1
    assert ax_value(dialogs[0], "description") == "Reverse this transaction?"
    modal = [p for p in dialogs[0].get("properties", []) if p["name"] == "modal"]
    assert modal and modal[0]["value"]["value"] is True
    assert exposed(nodes, "button", "Reverse") and exposed(nodes, "button", "Cancel")
    assert exposed(nodes, "button", "Close")


def test_content_behind_the_dialog_is_hidden_from_assistive_technology(page):
    assert exposed(ax_tree(page), "button", "Background action")

    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm'})")

    assert not exposed(ax_tree(page), "button", "Background action")


def test_toasts_stay_announced_but_their_controls_stay_outside_reach(page):
    # Review on #1625: exempting the toast container from inert kept toasts
    # announced, but also left each toast's Close button browsable outside
    # the dialog. Toasts already shown and toasts raised mid-dialog both count.
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm'})")
    page.evaluate("() => AppCore.toast('Request sent')")
    page.get_by_text("Request sent").wait_for()
    page.wait_for_timeout(50)  # the observer runs after the toast is inserted
    nodes = ax_tree(page)

    assert not exposed(nodes, "button", "Dismiss earlier toast")
    toast_closes = page.evaluate(
        "() => [...document.querySelectorAll('#flashToastContainer .btn-close')].map(b => b.inert)"
    )
    assert toast_closes == [True, True]
    assert len(exposed(nodes, "button", "Close")) == 1  # the dialog's own
    texts = {ax_value(n, "name") for n in nodes if not n.get("ignored")}
    assert "Settings saved" in texts and "Request sent" in texts

    page.keyboard.press("Escape")
    result(page)
    assert page.evaluate("() => document.querySelectorAll('[inert]').length") == 0
    assert exposed(ax_tree(page), "button", "Dismiss earlier toast")


def test_focus_starts_on_confirm_and_on_cancel_for_a_destructive_action(page):
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm', confirmLabel: 'Go'})")
    assert page.evaluate("() => document.activeElement.textContent") == "Go"
    page.keyboard.press("Escape")
    result(page)

    open_from_opener(page, "AppCore.confirm('Delete?', {title: 'Delete', confirmLabel: 'Delete', danger: true})")
    assert page.evaluate("() => document.activeElement.textContent") == "Cancel"


def test_tab_and_shift_tab_never_reach_the_page_behind(page):
    # Past the last control focus may leave for the browser's own UI (as it
    # does from a native <dialog>); it must never land on page content.
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm'})")
    seen_inside = 0
    for key in ["Tab"] * 6 + ["Shift+Tab"] * 6:
        page.keyboard.press(key)
        where = page.evaluate(
            "() => document.activeElement.closest('.modal.show') ? 'dialog'"
            " : (document.activeElement === document.body ? 'browser' : document.activeElement.id)"
        )
        assert where in ("dialog", "browser"), (key, where)
        seen_inside += where == "dialog"
    assert seen_inside >= 8


def test_closing_the_dialog_restores_the_page(page):
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm'})")
    page.keyboard.press("Escape")
    result(page)
    assert page.evaluate("() => document.querySelectorAll('[inert]').length") == 0
    assert exposed(ax_tree(page), "button", "Background action")


def test_escape_cancels_and_returns_focus_to_the_opener(page):
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm'})")
    page.keyboard.press("Escape")

    assert result(page) is False
    page.wait_for_function("() => document.activeElement.id === 'opener'")
    assert page.locator(".modal").count() == 0


def test_confirming_with_the_keyboard_resolves_true_and_returns_focus(page):
    open_from_opener(page, "AppCore.confirm('Go?', {title: 'Confirm', confirmLabel: 'Go'})")
    page.keyboard.press("Enter")

    assert result(page) is True
    page.wait_for_function("() => document.activeElement.id === 'opener'")


def test_prompt_field_is_labelled_and_announces_its_error_only_once_it_applies(page):
    open_from_opener(page, "AppCore.prompt('Enter your PIN to start work.', {title: 'Start Work', label: 'Your PIN', type: 'password', requiredMessage: 'Enter your PIN first.'})")

    field = page.get_by_label("Your PIN")
    assert page.evaluate("() => document.activeElement.id") == field.get_attribute("id")
    assert field.get_attribute("aria-invalid") is None
    assert field.get_attribute("aria-describedby") is None  # no premature error

    page.keyboard.press("Enter")  # empty

    assert field.get_attribute("aria-invalid") == "true"
    error_id = field.get_attribute("aria-describedby")
    assert page.locator(f"#{error_id}").inner_text() == "Enter your PIN first."
    assert page.evaluate("() => document.activeElement.getAttribute('aria-invalid')") == "true"
    node = [n for n in exposed(ax_tree(page), "textbox", "Your PIN")]
    assert node and ax_value(node[0], "description") == "Enter your PIN first."

    field.type("1")  # the error no longer applies once there is input
    assert field.get_attribute("aria-invalid") is None
    assert field.get_attribute("aria-describedby") is None
    assert "is-invalid" not in field.get_attribute("class")

    field.fill("1234")
    page.keyboard.press("Enter")
    assert result(page) == "1234"
    page.wait_for_function("() => document.activeElement.id === 'opener'")


def test_prompt_escape_resolves_null(page):
    open_from_opener(page, "AppCore.prompt('Name it.', {title: 'Name', label: 'Name'})")
    page.keyboard.press("Escape")
    assert result(page) is None


@pytest.mark.parametrize("call", [
    "AppCore.confirm('Reverse this transaction?', {title: 'Reverse transaction', confirmLabel: 'Reverse', danger: true})",
    "AppCore.prompt('Enter your PIN.', {title: 'Start Work', label: 'Your PIN', type: 'password'})",
])
def test_open_dialog_has_no_wcag_a_or_aa_violations(page, call):
    open_from_opener(page, call)
    page.wait_for_function("() => !document.querySelector('.modal.fading, .modal.show:not(.show)')")
    page.wait_for_timeout(400)  # fade-in finished, so colour contrast is measured at rest
    page.add_script_tag(content=AXE_SOURCE)
    violations = page.evaluate(
        "async () => (await axe.run(document.querySelector('.modal.show'),"
        " {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})).violations"
        ".map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).join(', '))"
    )
    assert violations == []


def test_data_confirm_cancel_submits_nothing_and_confirm_submits_with_its_button(page):
    page.locator("#payBtn").focus()
    page.keyboard.press("Enter")
    dialog = page.get_by_role("dialog", name="Pay toward bill")
    dialog.wait_for()
    page.wait_for_function("() => document.activeElement.closest('.modal.show')")
    assert dialog.get_by_text("Pay $12.50 toward this bill?").is_visible()
    # A destructive "Cancel X" next to a plain "Cancel" is ambiguous when read alone.
    assert dialog.get_by_role("button", name="Not now").is_visible()
    page.keyboard.press("Escape")
    dialog.wait_for(state="detached")
    page.wait_for_function("() => document.activeElement.id === 'payBtn'")
    assert page.posts == []

    page.keyboard.press("Enter")
    dialog.wait_for()
    page.wait_for_function("() => document.activeElement.closest('.modal.show')")
    dialog.get_by_role("button", name="Pay").click()
    page.get_by_text("paid").wait_for()
    assert page.posts == ["amount=12.50&choice=part"]


BUTTON_VARIANTS = [
    "btn-primary", "btn-danger", "btn-outline-primary", "btn-outline-secondary",
    "btn-outline-danger", "btn-outline-success", "btn-outline-warning", "btn-outline-info",
]

# WCAG relative-luminance contrast of the text against the first opaque
# background behind it, read from the computed style the user actually sees.
CONTRAST_JS = """(el) => {
  const rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((v) => {
    v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
  let node = el, bg = null;
  while (node) {
    const c = rgb(getComputedStyle(node).backgroundColor);
    if (c.length === 3 || (c.length === 4 && c[3] === 1)) { bg = c.slice(0, 3); break; }
    node = node.parentElement;
  }
  bg = bg || [255, 255, 255];
  const [a, b] = [lum(rgb(getComputedStyle(el).color).slice(0, 3)), lum(bg)];
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""


@pytest.mark.parametrize("shell", ["", "student-shell", "sysadmin-shell"])
def test_buttons_keep_aa_contrast_under_keyboard_focus_hover_and_active(page, shell):
    # The dialog's Cancel (.btn-outline-secondary) measured 2.3:1 when focused
    # from the keyboard: style.css forced its text dark but not its focus fill.
    # axe audits the resting state, so it never saw it.
    page.evaluate(
        """([shell, variants]) => {
            document.body.className = shell;
            const box = document.createElement('div');
            box.className = 'modal-content p-3';
            variants.forEach((v) => {
                const b = document.createElement('button');
                b.type = 'button'; b.className = 'btn ' + v; b.id = v; b.textContent = 'Keep request';
                box.appendChild(b);
            });
            document.querySelector('main').prepend(box);
        }""",
        [shell, BUTTON_VARIANTS],
    )
    failures = []
    for variant in BUTTON_VARIANTS:
        button = page.locator(f"#{variant}")
        page.evaluate("(id) => document.getElementById(id).previousElementSibling?.focus() || document.body.focus()", variant)
        button.focus()  # Playwright focus after a keyboard event counts as :focus-visible
        page.keyboard.press("Shift")
        assert page.evaluate("(id) => document.getElementById(id).matches(':focus-visible')", variant)
        page.wait_for_timeout(250)  # Bootstrap animates button colours for 0.15s
        focused = button.evaluate(CONTRAST_JS)
        button.hover()
        page.wait_for_timeout(250)
        hovered = button.evaluate(CONTRAST_JS)
        page.mouse.move(0, 0)
        page.evaluate("(id) => document.getElementById(id).classList.add('active')", variant)
        page.wait_for_timeout(250)
        selected = button.evaluate(CONTRAST_JS)
        page.evaluate("(id) => document.getElementById(id).classList.remove('active')", variant)
        for state, ratio in (("focus-visible", focused), ("hover", hovered), ("active", selected)):
            if ratio < 4.5:
                failures.append(f"{variant} {state}: {ratio:.2f}:1")
    assert failures == [], failures
