"""Bootstrap is served from this application, at one version.

Every layout used to load Bootstrap's CSS and JS from `cdn.jsdelivr.net`. When
that request was slow, filtered, or failed, the local stylesheet still applied
while Bootstrap's component rules did not — so `.btn-outline-*` lost its border
(`.btn` supplies `border: 1px solid transparent` and the variant only colours
it), `.form-switch` lost its track, and `bootstrap.bundle.min.js` took collapses,
tabs and modals with it. The symptom was intermittent and looked like an
application defect. A classroom behind a filter that blocks the CDN lost the UI
outright.

Three versions were in play at once — 5.3.0 in thirteen templates, 5.3.3 in
sixteen, 5.3.8 in one — so pages disagreed about which Bootstrap they rendered
against.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "templates"
VENDOR = REPO_ROOT / "static" / "vendor" / "bootstrap"

_BOOTSTRAP_CDN = re.compile(r"cdn\.jsdelivr\.net/npm/bootstrap@")
_VERSION = re.compile(r"Bootstrap\s+v(\d+\.\d+\.\d+)")


def _templates():
    return sorted(TEMPLATES.rglob("*.html"))


def _loads_bootstrap_from_a_cdn(source: str) -> bool:
    """Pure over the text, so the guard can be run against a known violation."""
    return bool(_BOOTSTRAP_CDN.search(source))


def _missing_style_layers(source: str) -> list[str]:
    """Layers a standalone page fails to load. Empty for a fragment."""
    if "DOCTYPE" not in source:
        return []  # a fragment or extending template inherits the stack
    missing = []
    if "vendor/bootstrap/bootstrap.min.css" not in source:
        missing.append("bootstrap")
    if "tokens.css" not in source:
        missing.append("tokens.css")
    return missing


def test_no_template_loads_bootstrap_from_a_cdn():
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _templates()
        if _loads_bootstrap_from_a_cdn(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "Bootstrap must be served from static/vendor/bootstrap so a CDN outage "
        f"cannot strip borders, switches and collapse behaviour: {offenders}"
    )


def test_the_vendored_bootstrap_files_exist_and_are_real():
    css = VENDOR / "bootstrap.min.css"
    js = VENDOR / "bootstrap.bundle.min.js"
    assert css.is_file() and js.is_file()
    # A truncated or placeholder file would pass an existence check while
    # producing exactly the missing-styles failure this module exists to stop.
    assert css.stat().st_size > 150_000
    assert js.stat().st_size > 50_000
    assert "Bootstrap" in css.read_text(encoding="utf-8")[:200]


def test_one_bootstrap_version_is_served_and_the_bundle_matches_the_css():
    css_version = _VERSION.search((VENDOR / "bootstrap.min.css").read_text(encoding="utf-8")[:400])
    js_version = _VERSION.search((VENDOR / "bootstrap.bundle.min.js").read_text(encoding="utf-8")[:400])
    assert css_version and js_version, "vendored files must carry their version banner"
    assert css_version.group(1) == js_version.group(1), (
        "the stylesheet and the bundle must be the same Bootstrap release: "
        f"css={css_version.group(1)} js={js_version.group(1)}"
    )


def test_templates_reference_the_bundle_rather_than_the_bare_js():
    """The bundle carries Popper; the bare build silently drops dropdowns and tooltips."""
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _templates()
        if "vendor/bootstrap/bootstrap.min.js" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


def test_every_standalone_page_loads_bootstrap_and_the_design_tokens():
    """A page that declares its own document must load the whole style stack.

    ``style.css`` consumes design tokens but does not import them — it opens
    "Consumes tokens.css for role-aware theming" — so a page that loads only
    ``style.css`` resolves every ``var(--…)`` to nothing. Bootstrap is the same
    story for layout: ``card``, ``d-flex`` and the spacing utilities come from
    it, not from this project's stylesheet.

    ``student_select_class_context.html`` was rendering the ``alert_card`` macro
    with neither layer loaded, so its alerts lost both their colours and their
    layout while the page around them still looked broadly right — the failure
    mode that makes this worth pinning rather than eyeballing.
    """
    offenders = []
    for path in _templates():
        missing = _missing_style_layers(path.read_text(encoding="utf-8"))
        if missing:
            offenders.append(f"{path.relative_to(REPO_ROOT)} missing {'+'.join(missing)}")
    assert offenders == [], offenders


def test_the_guards_catch_the_regressions_they_exist_to_stop():
    """The mutation proof: commit the forbidden thing, confirm CI stops it.

    Both checks above are substring scans over templates, which fail silently in
    one particular way: if the thing they search for is renamed — a new vendor
    path, a different CDN host, a build step that inlines the stylesheet — the
    scan finds nothing and reports success. A green check would then mean
    "no template regressed" or "the scan no longer looks at anything", and
    nothing distinguishes them.
    """
    cdn_forms = [
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">',
        "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
    ]
    for source in cdn_forms:
        assert _loads_bootstrap_from_a_cdn(source), f"guard missed a CDN load: {source}"
    assert not _loads_bootstrap_from_a_cdn(
        '<link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">'
    )

    bare = "<!DOCTYPE html><html><head><title>x</title></head><body></body></html>"
    assert set(_missing_style_layers(bare)) == {"bootstrap", "tokens.css"}

    tokens_only = bare.replace("<title>x</title>", '<title>x</title><link href="css/tokens.css">')
    assert _missing_style_layers(tokens_only) == ["bootstrap"]

    bootstrap_only = bare.replace(
        "<title>x</title>", '<title>x</title><link href="vendor/bootstrap/bootstrap.min.css">'
    )
    assert _missing_style_layers(bootstrap_only) == ["tokens.css"]

    complete = bare.replace(
        "<title>x</title>",
        '<title>x</title><link href="vendor/bootstrap/bootstrap.min.css"><link href="css/tokens.css">',
    )
    assert _missing_style_layers(complete) == []

    # A fragment is exempt by design; the guard must keep treating it that way,
    # or every partial in the tree becomes a false failure.
    assert _missing_style_layers('{% extends "base.html" %}<div>partial</div>') == []
