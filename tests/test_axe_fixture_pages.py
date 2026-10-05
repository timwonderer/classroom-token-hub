"""axe-core over every registered accessibility render fixture (SOP-TEST-002 §X).

Covers templates the real-route sweep (``test_axe_app_pages.py``) cannot reach
cheaply: error pages, multi-step flows, pages needing seeded domain rows. Each
state in ``tests/a11y_fixtures`` is rendered through the real Jinja
environment, served to Chromium with the project's real CSS and JS, and
audited. A fixture proves a supported presentation state is accessible; it does
not prove a production route reaches that state.
"""

from __future__ import annotations

import pytest

from tests.a11y_fixtures import load_registry
from tests.helpers.axe_wcag import (
    audit_fixture_states,
    record_fixture_templates,
    skip_or_fail_without_browser,
    sync_playwright,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_in_registered_fixture_states(app, wcag_live_server):
    states = load_registry()
    assert states, "the accessibility fixture registry is empty"

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            skip_or_fail_without_browser(exc)
        with browser:
            failures, rendered = audit_fixture_states(browser, wcag_live_server, states)

    record_fixture_templates(rendered)
    assert not failures, "\n\n".join(failures.values())
