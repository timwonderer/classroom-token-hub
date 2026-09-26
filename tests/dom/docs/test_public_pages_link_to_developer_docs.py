"""Every published public page offers a way into the developer documentation.

The two sites ship in one GitHub Pages artifact — `github-pages/` at the root,
`docs-site/build/` at `/docs/` — and the footer link is the only route a reader
has from one to the other. A page that ships without it is not visibly broken;
it simply becomes a dead end, which is the kind of regression nobody reports.

This is written as a rule over *every* HTML file in `github-pages/`, not a list
of the four that exist today, because the landing branch
(`launch/v2-landing-pages`) replaces `index.html` and adds `learnmore.html`.
Those pages inherit the requirement by existing, and this test is what tells
whoever merges that branch that the link has to come with it.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_SITE = REPO_ROOT / "github-pages"

# The path the docs site is mounted at inside the Pages artifact
# (.github/workflows/github-pages.yml).
DOCS_HREF = "/docs/"


def public_pages():
    return sorted(PUBLIC_SITE.glob("*.html"))


def links_to_docs(html):
    """True when the page carries an anchor whose href is the docs site.

    Pure over the markup so the detector can be run against a page that is
    missing the link, rather than only against pages that have it.
    """
    return bool(re.search(r'<a\s[^>]*href="/docs/"', html))


def test_the_detector_reports_a_page_with_no_way_into_the_docs():
    """Mutation proof: the near miss is a footer that kept every other link.

    A page reachable only by URL, or one whose footer links to the repository
    but not to the docs, is exactly what a merge of the landing branch would
    produce today.
    """
    without = """
      <footer class="landing-footer"><div class="landing-footer-links">
        <a href="https://github.com/timwonderer/classroom-token-hub">Project Repository</a>
        <a href="./privacy.html">Privacy Policy</a>
      </div></footer>
    """
    assert not links_to_docs(without)
    assert links_to_docs(without.replace('href="./privacy.html"', 'href="/docs/"'))


def test_there_are_public_pages_to_check():
    """Guards against the glob silently matching nothing."""
    assert public_pages(), f"no HTML pages found under {PUBLIC_SITE}"


@pytest.mark.parametrize("page", public_pages(), ids=lambda p: p.name)
def test_public_page_links_to_the_developer_docs(page):
    assert links_to_docs(page.read_text(encoding="utf-8")), (
        f"{page.name} ships in the Pages artifact with no link to {DOCS_HREF}"
    )
