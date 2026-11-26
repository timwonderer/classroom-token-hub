"""Every text node meets AA contrast, including visually-hidden text (INV-ARC-020 §VI.6).

axe skips text it considers hidden, so it never measured the getting-started
button's screen-reader label: black on --primary, 2.19:1. WAVE does measure
it, and flagged it on the teacher dashboard (2026-10-20). This measures what
WAVE measures: the computed colour of every element that owns text, against
the first opaque background behind it, visible or not.
"""

from __future__ import annotations

import pytest

from tests.helpers.axe_wcag import (
    authenticated_page,
    skip_or_fail_without_browser,
    student_session as _build_student_session,
    sync_playwright,
    teacher_session as _build_teacher_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

# <option> text is drawn by the platform's own dropdown, not over the page.
#
# Backgrounds and text are composited per the "over" operator
# (https://www.w3.org/TR/compositing-1/#simplealphacompositing) instead of
# discarding translucent layers outright, so a nearly-opaque translucent
# background (or a nearly-opaque translucent text color used to visually
# hide text) is measured against its real effective color, not against
# whatever opaque color sits further behind it.
LOW_CONTRAST_TEXT = """() => {
  const rgba = (c) => {
    const m = (c.match(/[\\d.]+/g) || []).map(Number);
    if (m.length === 3) m.push(1);
    return m;
  };
  const lum = ([r, g, b]) => [r, g, b].map((v) => {
    v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
  const over = ([r, g, b, a], [br, bg, bb]) => [
    r * a + br * (1 - a),
    g * a + bg * (1 - a),
    b * a + bb * (1 - a),
  ];
  const backdrop = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) layers.push(rgba(getComputedStyle(n).backgroundColor));
    let acc = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i--) {
      const [r, g, b, a] = layers[i];
      if (a === 0) continue;  // fully transparent: pass through to the next layer
      acc = over([r, g, b, a], acc);
    }
    return acc;
  };
  const failures = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (el.closest('option, script, style, template, noscript, [aria-hidden="true"]')) return;
    const text = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim()).join(' ');
    if (!text) return;
    const fg = rgba(getComputedStyle(el).color);
    const bg = backdrop(el);
    const effectiveFg = fg[3] < 1 ? over(fg, bg) : fg.slice(0, 3);
    const [a, b] = [lum(effectiveFg), lum(bg)];
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const style = getComputedStyle(el);
    const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5)) failures.push(`${el.tagName.toLowerCase()}.${el.className} "${text.slice(0, 50)}" ${ratio.toFixed(2)}:1`);
  });
  return failures;
}"""


def test_all_dashboard_text_meets_aa_contrast_hidden_text_included(app, client, wcag_live_server):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher = _build_teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )
    student_classroom, student = initialize_as_student("ap_csp_p3", client, app)
    student_sess = _build_student_session(
        client, user_id=student.user.id, class_id=student_classroom.class_id, seat_id=student.seat.id,
    )
    failures = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            skip_or_fail_without_browser(exc)
        with browser:
            for path, session in (("/admin/", teacher), ("/student/dashboard", student_sess)):
                page = authenticated_page(browser, wcag_live_server, session)
                page.goto(f"{wcag_live_server}{path}", wait_until="networkidle")
                found = page.evaluate(LOW_CONTRAST_TEXT)
                if found:
                    failures[path] = found
                page.close()
    assert failures == {}, failures


def test_translucent_colors_are_composited_not_skipped():
    """Mutation proof: a translucent layer must be composited, not discarded.

    Case 1: opaque white text on a near-white translucent white background,
    inside a black ancestor. Discarding the translucent layer (the original
    bug) compares white text against the black ancestor and passes at
    21:1; compositing it over black leaves a near-white effective
    background, which opaque white text fails.

    Case 2: a visually-hidden label whose text color is itself translucent
    (``rgba(0, 0, 0, 0.1)`` on white) -- a pattern that hides text from
    sighted users without `aria-hidden` or `display: none`, so it still
    reaches assistive tech and axe's hidden-text skip does not excuse it.
    Returning early on alpha < 1 (the original bug) never measures it; its
    effective color is near-white-on-white and must fail.
    """
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            skip_or_fail_without_browser(exc)
        with browser:
            page = browser.new_page()
            page.set_content(
                """
                <body style="background: black;">
                  <div style="background: rgba(255,255,255,0.95);">
                    <p style="color: white;">near-white backdrop, opaque white text</p>
                  </div>
                  <span style="color: rgba(0,0,0,0.1);">translucent hidden label</span>
                </body>
                """
            )
            failures = page.evaluate(LOW_CONTRAST_TEXT)
            page.close()
    assert any("near-white backdrop" in f for f in failures), failures
    assert any("translucent hidden label" in f for f in failures), failures
