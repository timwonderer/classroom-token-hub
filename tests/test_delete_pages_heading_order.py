"""The class- and account-deletion pages keep a logical heading order (INV-ARC-020 §VI.2).

WAVE, 2026-10-20: each page's red card title was an h5 directly under the page
h1, with an h3 inside it. axe files `heading-order` under best-practice, so the
WCAG-tagged route sweep never ran it, and test_accessibility.py skips every
template that extends a layout. This runs that one rule on the rendered pages.
"""

import pytest

from tests.helpers.axe_wcag import (
    AXE_SOURCE,
    authenticated_page,
    skip_or_fail_without_browser,
    sync_playwright,
    teacher_session as _build_teacher_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.classroom_initializer import initialize_as_teacher

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")


def test_deletion_pages_do_not_skip_heading_levels(app, client, wcag_live_server):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    session = _build_teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )
    failures = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            skip_or_fail_without_browser(exc)
        with browser:
            for path in ("/admin/class-delete", "/admin/account-delete"):
                page = authenticated_page(browser, wcag_live_server, session)
                response = page.goto(f"{wcag_live_server}{path}", wait_until="networkidle")
                assert response is not None and response.ok, path
                page.add_script_tag(content=AXE_SOURCE)
                nodes = page.evaluate(
                    "async () => (await axe.run(document, {runOnly: {type: 'rule', values: ['heading-order']}}))"
                    ".violations.flatMap(v => v.nodes.map(n => n.target.join(' ')))"
                )
                if nodes:
                    failures[path] = nodes
                page.close()
    assert failures == {}, failures
