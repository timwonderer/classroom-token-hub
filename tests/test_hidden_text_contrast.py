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
LOW_CONTRAST_TEXT = """() => {
  const rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((v) => {
    v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
  const backdrop = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const c = rgb(getComputedStyle(n).backgroundColor);
      if (c.length === 3 || c[3] === 1) return c.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const failures = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (el.closest('option, script, style, template, noscript, [aria-hidden="true"]')) return;
    const text = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim()).join(' ');
    if (!text) return;
    const fg = rgb(getComputedStyle(el).color);
    if (fg.length === 4 && fg[3] < 1) return;  // translucent text: axe's domain, not this check's
    const [a, b] = [lum(fg.slice(0, 3)), lum(backdrop(el))];
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
