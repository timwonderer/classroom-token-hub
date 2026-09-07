"""Rendered axe-core audit of the published marketing site.

The site in ``github-pages/`` is deployed to GitHub Pages and is not served by
the application, so this audit serves the directory directly over a throwaway
``http.server`` rather than driving the Flask app. It previously went through
the app's ``/gh/<path>`` route, which existed only so a local certification run
could stay on one origin; that route is gone, and with it the last reason for
this audit to need a running dev server.

Playwright and a Chromium build are still environment-dependent, so their
absence skips rather than fails. A skip says "not audited here"; a failure is
reserved for "audited, and the page has a violation".
"""

import http.server
import socketserver
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None


REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_ROOT = REPO_ROOT / "github-pages"
AXE_SOURCE = (REPO_ROOT / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")

# Every page published to GitHub Pages. On `main`, `index.html` is the holding
# page and there is no learn-more page; this branch replaces the former with the
# landing page and adds the latter, and the equality assertion below is what
# requires `learnmore.html` to be listed here when it returns.
PUBLIC_PAGES = [
    "index.html",
    "learnmore.html",
    "district.html",
    "privacy.html",
    "terms.html",
]


@contextmanager
def _serve_site():
    """Serve ``github-pages/`` on an ephemeral port for the duration of a test."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

        def log_message(self, *args):  # noqa: A003 - silence per-request stderr noise
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def test_every_published_page_is_audited():
    """The audit list must cover the directory it claims to audit.

    A page added to `github-pages/` without being listed here would ship
    unaudited while this suite still reported green — the audit would be passing
    over a set that no longer matches what is deployed.
    """
    on_disk = {path.name for path in SITE_ROOT.glob("*.html")}
    assert on_disk == set(PUBLIC_PAGES), (
        f"github-pages/ has {sorted(on_disk - set(PUBLIC_PAGES))} unaudited and "
        f"PUBLIC_PAGES lists {sorted(set(PUBLIC_PAGES) - on_disk)} which no longer exist"
    )


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_published_pages_have_no_axe_violations():
    """Audit every published marketing page against WCAG 2 A and AA."""
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser, _serve_site() as base_url:
            page = browser.new_page()
            for filename in PUBLIC_PAGES:
                response = page.goto(f"{base_url}/{filename}", wait_until="networkidle")
                assert response is not None and response.ok, f"Could not load {filename}"
                page.add_script_tag(content=AXE_SOURCE)
                result = page.evaluate("""async () => {
                    return await axe.run(document, {
                        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
                    });
                }""")
                assert not result["violations"], (
                    f"axe violations on {filename}: {result['violations']}"
                )
