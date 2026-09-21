"""The `hidden` attribute must actually hide (live-test finding 39).

The UA stylesheet declares `[hidden] { display: none }` without `!important`, so
any Bootstrap display utility on the same element wins: `.d-flex`, `.d-block`,
`.d-grid` and the `.d-inline-*` family are all `display: ... !important`. An
element written as `<div class="alert d-flex" hidden>` is visible permanently,
and setting `el.hidden = true` in JavaScript changes nothing.

That shipped: the stale-class-context banner announced itself on every admin
page regardless of whether the class context had diverged. The markup was
correct, the script was correct, and the cascade discarded both.

The existing test for that banner passed because it asserted the element and its
meta tag were present in the HTML. Presence is not visibility, and a test that
cannot see CSS cannot catch a CSS bug — the same blind spot as the CSRF header,
which the suite also could not observe.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Bootstrap display utilities, every one of which is declared `!important`.
DISPLAY_UTILITIES = (
    "d-flex", "d-inline-flex", "d-block", "d-inline-block",
    "d-grid", "d-inline-grid", "d-inline", "d-table", "d-table-cell",
)

_TAG = re.compile(r"<[a-zA-Z][^>]*>", re.S)


def find_hidden_display_collisions(html: str, path: str = "<source>") -> list[str]:
    """Tags carrying both `hidden` and a Bootstrap display utility.

    Pure function over source text so it can be fed a synthetic violation and
    proved to report it (SOP-TEST-003 §IX.A).
    """
    hits = []
    for tag in _TAG.findall(html):
        if not re.search(r"(?<![\w-])hidden(?=[\s>=])", tag):
            continue
        class_attr = re.search(r'class\s*=\s*"([^"]*)"', tag)
        if not class_attr:
            continue
        classes = set(class_attr.group(1).split())
        clash = classes.intersection(DISPLAY_UTILITIES)
        if clash:
            hits.append(f"{path}: {sorted(clash)} on an element with `hidden` — {tag[:110]}")
    return hits


def test_the_stylesheet_forces_hidden_to_win():
    """Without this rule every collision below is silently visible."""
    css = (REPO_ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important", css), (
        "static/css/style.css must declare [hidden] { display: none !important }, "
        "or any Bootstrap display utility overrides the hidden attribute"
    )


def test_no_template_pairs_hidden_with_a_display_utility():
    """Belt and braces: the rule above fixes these, but they read as bugs."""
    collisions = []
    for path in (REPO_ROOT / "templates").rglob("*.html"):
        collisions += find_hidden_display_collisions(
            path.read_text(encoding="utf-8", errors="replace"),
            str(path.relative_to(REPO_ROOT)),
        )
    assert not collisions, "\n  ".join(["hidden/display-utility collisions:"] + collisions)


# --- mutation proofs -------------------------------------------------------

def test_detector_reports_the_shipped_banner_markup():
    """Finding 39, exactly as it was written."""
    shipped = (
        '<div id="stale-class-context" class="alert alert-warning d-flex '
        'align-items-start gap-2 mb-3" role="alert" hidden>'
    )
    hits = find_hidden_display_collisions(shipped, "layout_admin.html")
    assert len(hits) == 1, hits
    assert "d-flex" in hits[0]


@pytest.mark.parametrize("utility", DISPLAY_UTILITIES)
def test_detector_covers_every_display_utility(utility):
    assert len(find_hidden_display_collisions(f'<div class="{utility}" hidden>')) == 1


def test_detector_accepts_hidden_without_a_display_utility():
    assert find_hidden_display_collisions('<div class="alert alert-warning" hidden>') == []


def test_detector_accepts_a_display_utility_without_hidden():
    assert find_hidden_display_collisions('<div class="alert d-flex">') == []


def test_detector_is_not_fooled_by_a_word_containing_hidden():
    """`overflow-hidden` and `data-hidden-until` are not the hidden attribute."""
    assert find_hidden_display_collisions('<div class="d-flex overflow-hidden">') == []
    assert find_hidden_display_collisions('<div class="d-flex" data-hidden-until="x">') == []
