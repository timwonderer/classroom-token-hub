"""Guard the reachability assumption behind the accepted `image-size` advisories.

GHSA (ICNS parser, JXL/HEIF parsers) report denial of service via infinite loops
in `image-size` at every published version (`<= 2.0.2`). No patched release
exists, and the package arrives transitively under the current `@docusaurus/core`
release, so it cannot be remediated by a lockfile change today.

Those two alerts are therefore dismissed on a *reachability* argument, not a
severity argument: `image-size` runs only during the documentation build, when
`@docusaurus/mdx-loader` resolves dimensions for images referenced from markdown,
and `docs-site/` contains no image assets and no markdown image references. The
vulnerable parsers are never invoked.

That argument has an invalidation condition. This test enforces it, so adding a
docs image cannot silently void the dismissal. It retires itself: once the
lockfile carries a non-vulnerable `image-size` (or none at all), it stops
constraining docs content.
"""

import json
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = PROJECT_ROOT / "docs-site"
LOCKFILE = DOCS_SITE / "package-lock.json"

# Advisory ceiling: every release up to and including 2.0.2 is affected.
LAST_VULNERABLE_IMAGE_SIZE = (2, 0, 2)

# Directories that are build output or installed dependencies, not authored content.
EXCLUDED_DIRS = {"node_modules", "build", ".docusaurus", ".cache"}

# image-size sniffs format from magic bytes, not the file extension, so the guard
# covers any raster/vector asset rather than only .icns/.jxl/.heif.
IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".icns", ".jxl", ".heif", ".heic", ".avif",
}

MARKDOWN_SUFFIXES = {".md", ".mdx"}

# Markdown image syntax, deliberately not matching plain links.
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(")
HTML_IMAGE = re.compile(r"<img\b", re.IGNORECASE)

REASSESS = (
    "Adding documentation images re-enters the vulnerable `image-size` parsing "
    "paths, which voids the reachability justification recorded against the "
    "ICNS and JXL/HEIF advisories. Reassess those Dependabot findings before "
    "landing this: either confirm a patched `image-size` is available (then "
    "delete this guard), or re-evaluate the accepted risk."
)


def _parse_version(raw):
    parts = []
    for chunk in str(raw).split("-")[0].split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            break
    return tuple(parts)


def _vulnerable_image_size_versions():
    """Return locked `image-size` versions still inside the advisory range."""
    if not LOCKFILE.exists():
        return []
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    found = []
    for path, meta in (lock.get("packages") or {}).items():
        if not isinstance(meta, dict):
            continue
        if path.split("node_modules/")[-1] != "image-size":
            continue
        version = meta.get("version")
        if version and _parse_version(version) <= LAST_VULNERABLE_IMAGE_SIZE:
            found.append(version)
    return found


def _authored_files():
    for path in DOCS_SITE.rglob("*"):
        if not path.is_file():
            continue
        if EXCLUDED_DIRS & set(path.relative_to(DOCS_SITE).parts):
            continue
        yield path


def _docs_image_assets():
    return sorted(
        str(p.relative_to(PROJECT_ROOT))
        for p in _authored_files()
        if p.suffix.lower() in IMAGE_SUFFIXES
    )


def _markdown_image_references():
    hits = []
    for path in _authored_files():
        if path.suffix.lower() not in MARKDOWN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if MARKDOWN_IMAGE.search(line) or HTML_IMAGE.search(line):
                hits.append(f"{path.relative_to(PROJECT_ROOT)}:{number}")
    return sorted(hits)


requires_vulnerable_dep = pytest.mark.skipif(
    not _vulnerable_image_size_versions(),
    reason="image-size is no longer within the advisory range; guard retired.",
)


def test_guard_targets_the_expected_dependency_state():
    """Document which lockfile state the guard is currently reacting to."""
    versions = _vulnerable_image_size_versions()
    if not versions:
        pytest.skip("image-size is patched or absent; the reachability guard is moot.")
    assert all(_parse_version(v) <= LAST_VULNERABLE_IMAGE_SIZE for v in versions)


@requires_vulnerable_dep
def test_docs_site_has_no_image_assets():
    """No docs image assets while `image-size` remains unpatched."""
    assets = _docs_image_assets()
    assert not assets, (
        f"docs-site gained {len(assets)} image asset(s): {assets}\n\n{REASSESS}"
    )


@requires_vulnerable_dep
def test_docs_site_has_no_markdown_image_references():
    """No markdown/HTML image references while `image-size` remains unpatched."""
    references = _markdown_image_references()
    assert not references, (
        f"docs-site gained {len(references)} image reference(s): {references}\n\n{REASSESS}"
    )
