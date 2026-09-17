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


def test_no_template_loads_bootstrap_from_a_cdn():
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _templates()
        if _BOOTSTRAP_CDN.search(path.read_text(encoding="utf-8"))
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
