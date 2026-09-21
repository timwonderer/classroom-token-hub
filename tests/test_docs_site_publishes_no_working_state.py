"""The public documentation site publishes contracts, not working state.

The site builds from `../docs` with an *exclude* list, which fails open: a new
file dropped into a directory is published unless someone remembers to exclude
it. That is how a filled deployment worksheet — one production host's state,
ticked boxes and all — reached a public site nobody had decided to put it on.

This test inverts the default. Anything under a governed prefix must either be
matched by the site's exclude list or appear in `PUBLISHABLE` below, which is a
deliberate, reviewed decision rather than an oversight. A new document defaults
to *not published* and the build fails until someone chooses.

Per `SOP-TEST-003` §IX.A the matching is a pure function over the config text,
with a companion mutation proof.
"""

import fnmatch
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "docs-site" / "docusaurus.config.js"
DOCS = REPO_ROOT / "docs"

# Directories whose contents are working state by default.
GOVERNED_PREFIXES = ("ops", "TRACKING")

# The deliberate exceptions: durable enough for an outside developer to read.
# Adding to this list is a decision about the public site, not a formality.
PUBLISHABLE = {
    "TRACKING/DOCS_PLATFORM_ROADMAP.md",
    "TRACKING/DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md",
}

_EXCLUDE_BLOCK = re.compile(r"exclude:\s*\[(.*?)\]", re.S)
_QUOTED = re.compile(r"""["']([^"']+)["']""")
_COMMENT = re.compile(r"//[^\n]*")


def exclude_patterns(config_text: str) -> list[str]:
    """The docs plugin's exclude globs, comments stripped."""
    block = _EXCLUDE_BLOCK.search(config_text)
    if not block:
        return []
    return _QUOTED.findall(_COMMENT.sub("", block.group(1)))


def is_excluded(rel_path: str, patterns: list[str]) -> bool:
    """Whether a docs-relative path is matched by any exclude glob.

    `ops/**` must match `ops/a.md` as well as `ops/x/y.md`; fnmatch alone does
    not, because `*` spans separators for it but `**` is not special.
    """
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if pattern.endswith("/**") and rel_path.startswith(pattern[:-2]):
            return True
    return False


def _governed_documents() -> list[str]:
    found: list[str] = []
    for prefix in GOVERNED_PREFIXES:
        base = DOCS / prefix
        if base.exists():
            found += [
                str(p.relative_to(DOCS)) for p in base.rglob("*.md")
            ] + [str(p.relative_to(DOCS)) for p in base.rglob("*.mdx")]
    return sorted(found)


@pytest.mark.parametrize("rel_path", _governed_documents(), ids=lambda p: p)
def test_working_state_is_not_published(rel_path):
    """A governed document is excluded from the site unless deliberately listed."""
    if rel_path in PUBLISHABLE:
        return
    patterns = exclude_patterns(CONFIG.read_text(encoding="utf-8"))
    assert is_excluded(rel_path, patterns), (
        f"docs/{rel_path} would be published to the public documentation site.\n"
        f"Add it to the exclude list in docs-site/docusaurus.config.js, or, if it "
        f"is genuinely meant to be public, add it to PUBLISHABLE in this test — "
        f"which is a decision about the public site, not a formality."
    )


@pytest.mark.parametrize("rel_path", sorted(PUBLISHABLE), ids=lambda p: p)
def test_publishable_documents_exist_and_are_reachable(rel_path):
    """An allowlisted document that no longer exists, or that is also excluded,
    is a stale decision rather than a published page."""
    assert (DOCS / rel_path).exists(), f"docs/{rel_path} is allowlisted but missing"
    patterns = exclude_patterns(CONFIG.read_text(encoding="utf-8"))
    assert not is_excluded(rel_path, patterns), (
        f"docs/{rel_path} is in PUBLISHABLE and also matched by an exclude glob; "
        f"the two disagree about whether it is public."
    )


# ─── Mutation proofs ───


def test_parser_reads_the_real_exclude_list():
    patterns = exclude_patterns(CONFIG.read_text(encoding="utf-8"))
    assert "ops/**" in patterns
    assert "archive/**" in patterns
    assert "user-guides/**" in patterns


@pytest.mark.parametrize(
    ("rel_path", "patterns"),
    [
        # the shapes a real regression would take
        ("TRACKING/PRODUCTION_READINESS_2026-10.md", ["TRACKING/PRODUCTION_READINESS_2026-09.md"]),
        ("ops/audits/NEW_DEPLOYMENT_2026-10-01.md", ["TRACKING/**"]),
        ("TRACKING/A_NEW_DECISION_PACKAGE.md", []),
        ("ops/evidence/run/pytest_full_summary.md", ["ops/audits/**"]),
    ],
)
def test_detector_reports_an_unexcluded_document(rel_path, patterns):
    """Guard against the gate going green because the matcher went blind."""
    assert not is_excluded(rel_path, patterns)


@pytest.mark.parametrize(
    ("rel_path", "patterns"),
    [
        ("ops/audits/LIVE_TEST_DEPLOYMENT_2026-09-19.md", ["ops/**"]),
        ("ops/STATUS_APP_HEALTH_COLLECTOR_SETUP.md", ["ops/**"]),
        ("ops/audits/evidence/run/README.md", ["ops/**"]),
        ("TRACKING/PRODUCTION_FIRST_TEST_DEPLOYMENT_CHECKLIST_2026-09.md",
         ["TRACKING/PRODUCTION_FIRST_TEST_DEPLOYMENT_CHECKLIST_*.md"]),
        ("TRACKING/CI_CLASSIFIER_DESIGN_2026-08-26.md",
         ["TRACKING/CI_CLASSIFIER_DESIGN_2026-08-26.md"]),
    ],
)
def test_detector_admits_a_correctly_excluded_document(rel_path, patterns):
    assert is_excluded(rel_path, patterns)


def test_comments_in_the_exclude_block_are_not_read_as_patterns():
    """The block is heavily commented, and a quoted path inside a comment must
    not be mistaken for a live exclude."""
    config = 'exclude: [\n  // superseded: "TRACKING/OLD.md"\n  "ops/**",\n],'
    assert exclude_patterns(config) == ["ops/**"]
