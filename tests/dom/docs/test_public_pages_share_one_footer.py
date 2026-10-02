"""Every published public page carries the same footer.

The footer holds the site's standing promises — the support address, the
no-advertising, no-tracking statement, the license — and its links. Each page
kept its own copy, and they drifted: three policy pages carried an older
disclaimer, one dropped the support address, and pages left themselves out of
the link list. Nothing was visibly broken, so nothing reported it.

`learnmore.html` is the reference. The rule runs over every HTML file in
`github-pages/`, so a new page inherits it by existing.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_SITE = REPO_ROOT / "github-pages"
REFERENCE_PAGE = "learnmore.html"

_FOOTER = re.compile(r"<footer\b.*?</footer>", re.S)


def footer_of(html):
    """The page's single <footer> element, or None when it has none or several."""
    footers = _FOOTER.findall(html)
    return footers[0] if len(footers) == 1 else None


def footer_mismatches(pages, reference=REFERENCE_PAGE):
    """Names of pages whose footer is missing or differs from the reference's.

    Pure over {page name: markup} so the detector can be run against a drifted
    page, not only against pages that already agree.
    """
    expected = footer_of(pages[reference])
    assert expected is not None, f"{reference} must have exactly one <footer>"
    return sorted(name for name, html in pages.items() if footer_of(html) != expected)


def _published_pages():
    return {path.name: path.read_text(encoding="utf-8") for path in PUBLIC_SITE.glob("*.html")}


def test_every_public_page_uses_the_reference_footer():
    pages = _published_pages()
    assert REFERENCE_PAGE in pages
    assert footer_mismatches(pages) == []


@pytest.mark.parametrize(
    "drift",
    [
        # The drift that shipped: an older disclaimer on the policy pages.
        lambda f: f.replace("self-funded by a full-time high school teacher", "maintained by a classroom teacher"),
        # A page dropping the support address.
        lambda f: re.sub(r"\s*<p><a [^>]*mailto:support@[^<]*</a></p>", "", f),
        # A page leaving itself out of the link list.
        lambda f: f.replace('<a href="./terms.html" target="_self">Terms of Service</a>', ""),
        # A page losing the way back to the landing page (the gap found 2026-10-02).
        lambda f: f.replace('<a href="./index.html" target="_self">Home</a>', ""),
        # A one-character difference.
        lambda f: f.replace("</a></p>", "</a> </p>", 1),
    ],
    ids=["older-disclaimer", "no-support-address", "self-link-dropped", "stray-space"],
)
def test_the_detector_reports_a_drifted_footer(drift):
    """Mutation proof (SOP-TEST-003 §IX.A): each near miss must be reported."""
    reference_html = (PUBLIC_SITE / REFERENCE_PAGE).read_text(encoding="utf-8")
    footer = footer_of(reference_html)
    drifted = drift(footer)
    assert drifted != footer, "the mutation must actually change the footer"
    pages = {REFERENCE_PAGE: reference_html, "terms.html": reference_html.replace(footer, drifted)}
    assert footer_mismatches(pages) == ["terms.html"]


def test_the_detector_reports_a_page_without_a_footer():
    reference_html = (PUBLIC_SITE / REFERENCE_PAGE).read_text(encoding="utf-8")
    pages = {REFERENCE_PAGE: reference_html, "new.html": "<html><body>no footer</body></html>"}
    assert footer_mismatches(pages) == ["new.html"]
