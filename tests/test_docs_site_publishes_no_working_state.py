"""The public documentation site publishes contracts, not working state.

The retired Docusaurus site built from `../docs` with an *exclude* list, which failed
open: a new file dropped into a directory was published unless someone
remembered to exclude it. That is how a filled deployment worksheet — one
production host's state, ticked boxes and all — reached a public site nobody had
decided to put it on.

The Hugo build (`docs-generator-proof/build.py`) publishes from an *allowlist*
instead, so a new document defaults to not published. This test pins that
default where working state lives: anything under a governed prefix is published
only if it appears in `PUBLISHABLE` below, a deliberate, reviewed decision that
must agree with the build's own allowlist.

Per `SOP-TEST-003` §IX.A the selection is a pure function over a directory tree,
with a companion mutation proof.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

# Directories whose contents are working state by default.
GOVERNED_PREFIXES = ("ops", "TRACKING")

# The deliberate exceptions: durable enough for an outside developer to read.
# Adding to this list is a decision about the public site, not a formality.
PUBLISHABLE = {
    "TRACKING/DOCS_PLATFORM_ROADMAP.md",
    "TRACKING/DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md",
}


def _site_build():
    spec = importlib.util.spec_from_file_location(
        "docs_site_build", REPO_ROOT / "docs-generator-proof" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _site_build()


def _governed_documents() -> list[str]:
    found: list[str] = []
    for prefix in GOVERNED_PREFIXES:
        base = DOCS / prefix
        if base.exists():
            found += [str(p.relative_to(DOCS)) for p in base.rglob("*.md")]
    return sorted(found)


def _published() -> set[str]:
    return {p.as_posix() for p in BUILD.published_documents(DOCS)}


@pytest.mark.parametrize("rel_path", _governed_documents(), ids=lambda p: p)
def test_working_state_is_not_published(rel_path):
    """A governed document is kept off the site unless deliberately listed."""
    if rel_path in PUBLISHABLE:
        return
    assert rel_path not in _published(), (
        f"docs/{rel_path} would be published to the public documentation site.\n"
        f"Remove it from the allowlist in docs-generator-proof/build.py, or, if it "
        f"is genuinely meant to be public, add it to PUBLISHABLE in this test — "
        f"which is a decision about the public site, not a formality."
    )


@pytest.mark.parametrize("rel_path", sorted(PUBLISHABLE), ids=lambda p: p)
def test_publishable_documents_exist_and_are_published(rel_path):
    """An allowlisted document that no longer exists, or that the build leaves
    out, is a stale decision rather than a published page."""
    assert (DOCS / rel_path).exists(), f"docs/{rel_path} is allowlisted but missing"
    assert rel_path in _published(), f"docs/{rel_path} is in PUBLISHABLE but not published"


def test_the_build_allowlist_and_this_decision_agree():
    assert BUILD.PUBLISHABLE_TRACKING == PUBLISHABLE
    assert not {prefix for prefix in GOVERNED_PREFIXES} & BUILD.PUBLIC_ROOTS


# ─── Mutation proof ───


def test_new_working_state_defaults_to_unpublished(tmp_path):
    """Guard against the gate going green because the selection went blind:
    the shapes a real regression would take are left out of the site."""
    for name in (
        "INVARIANT/CORE/example.md",
        "TRACKING/PRODUCTION_READINESS_2026-10.md",
        "TRACKING/A_NEW_DECISION_PACKAGE.md",
        "ops/audits/NEW_DEPLOYMENT_2026-10-01.md",
        "ops/evidence/run/pytest_full_summary.md",
        "TRACKING/DOCS_PLATFORM_ROADMAP.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Fixture")
    assert {p.as_posix() for p in BUILD.published_documents(tmp_path)} == {
        "INVARIANT/CORE/example.md",
        "TRACKING/DOCS_PLATFORM_ROADMAP.md",
    }
