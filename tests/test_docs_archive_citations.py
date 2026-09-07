"""Live documentation must not silently cite archived or missing material.

Two failure modes are indistinguishable from success unless something checks:

1. A link that resolves to nothing. Nobody notices, because a broken markdown
   link renders as ordinary text on GitHub and a 404 in the docs site — neither
   of which fails a build. `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-002`
   accumulated 69 of these before anyone looked.
2. A link into `docs/archive/` with no label. The archive exists precisely so
   superseded material cannot be mistaken for current authority; an unlabelled
   link re-creates the confusion the archive was built to prevent.

`SOP-DOC-000` §V (*Citing archived material*) states the rule these tests
enforce: a live document must not cite archived material in a **Dependencies**
section, and must not link to it without labelling it as archived.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
ARCHIVE_ROOT = DOCS_ROOT / "archive"

# Inline markdown links: [text](target). Reference-style links and bare URLs are
# not matched — neither form appears in the governed tree.
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

# Code is not prose. `DOM-[DOMAIN].check_[COND](context_id)` is a function
# signature, not a link, and treating it as one produces a failure that cannot
# be fixed without mangling the documentation.
_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    return _INLINE_CODE.sub("", _FENCE.sub("", text))

# A citation is labelled if the word "archived"/"superseded"/etc. appears on the
# same line. The line is the unit a reader takes in at a glance.
#
# The path itself must be excised before this is applied: every archive link
# contains the substring "archive", so searching the raw line would report every
# citation as labelled and the check could never fail. That is the same
# matches-nothing defect this module exists to catch, and the first draft of
# this file had it.
_LABEL = re.compile(r"archiv|supersed|removed|no longer|historic", re.IGNORECASE)
_ARCHIVE_PATH = re.compile(r"\S*archive/\S*")

# What the rule governs is citing an archived *document*. Naming the archive
# directory is not a citation — `docs/archive/v1-docs/` is self-evidently the
# archive and cannot be mistaken for current authority. A specific `.md` file
# under it can be, which is the confusion the label prevents.
_ARCHIVED_DOC = re.compile(r"archive/\S+\.md")

# Namespaced documents whose Dependencies sections assert governing authority.
_NORMATIVE_PREFIXES = ("INV-", "DOM-", "FEAT-", "SOP-", "SPEC-", "MAP-", "PRN-")


def _live_markdown_files() -> list[Path]:
    """Every markdown file under docs/ that is not itself archived."""
    return sorted(
        path
        for path in DOCS_ROOT.rglob("*.md")
        if ARCHIVE_ROOT not in path.parents
    )


def _resolve(source: Path, target: str) -> Path | None:
    """Resolve a link target to a filesystem path, or None if not a local file link."""
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None
    if target.startswith("/"):
        return REPO_ROOT / target.lstrip("/")
    return (source.parent / target).resolve()


def _dependencies_block(text: str) -> list[str]:
    """The lines of the document's Dependencies section, if it has one."""
    lines = text.split("\n")
    out: list[str] = []
    inside = False
    for line in lines:
        if re.match(r"^#{2,3}\s", line):
            inside = bool(re.search(r"Dependencies", line, re.IGNORECASE))
            continue
        if inside:
            out.append(line)
    return out


@pytest.mark.parametrize(
    "doc", _live_markdown_files(), ids=lambda p: str(p.relative_to(DOCS_ROOT))
)
def test_no_unlabelled_archive_citation(doc: Path) -> None:
    """A citation of an archived document must say on its own line that it is archived.

    Labelling is the whole point. The archived file is usually still present and
    the link still resolves, so nothing else in the suite can tell the
    difference between "cited as history" and "cited as authority".
    """
    text = doc.read_text(encoding="utf-8")
    offenders: list[str] = []

    for line in text.split("\n"):
        if not _ARCHIVED_DOC.search(line):
            continue
        # Strip the path before looking for the label, so the word "archive"
        # inside the target cannot vouch for itself.
        if _LABEL.search(_ARCHIVE_PATH.sub("", line)):
            continue
        offenders.append(line.strip())

    assert not offenders, (
        f"{doc.relative_to(REPO_ROOT)} links into docs/archive/ without labelling it "
        f"as archived (SOP-DOC-000 §V). Add '(archived)' or state what supersedes it:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "doc",
    [d for d in _live_markdown_files() if d.name.startswith(_NORMATIVE_PREFIXES)],
    ids=lambda p: str(p.relative_to(DOCS_ROOT)),
)
def test_dependencies_never_cite_archived_material(doc: Path) -> None:
    """A Dependencies section is a claim of governing authority.

    Archived material is superseded by definition, so it cannot govern anything.
    Unlike the label rule above, there is no way to write this one correctly —
    the citation has to go.
    """
    offenders = [
        line.strip()
        for line in _dependencies_block(doc.read_text(encoding="utf-8"))
        if "docs/archive/" in line or "/archive/" in line
    ]

    assert not offenders, (
        f"{doc.relative_to(REPO_ROOT)} declares archived material as a dependency "
        f"(SOP-DOC-000 §V). Superseded documents cannot carry authority; remove the "
        f"entry or cite what replaced it:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "doc", _live_markdown_files(), ids=lambda p: str(p.relative_to(DOCS_ROOT))
)
def test_internal_markdown_links_resolve(doc: Path) -> None:
    """Every relative link in a live doc must point at something that exists.

    A link that matches nothing is indistinguishable from one that was
    satisfied. This is the same failure class as a query filter that selects no
    rows, and it is why the documentation index rotted to 44% dead without
    anything reporting it.
    """
    text = _strip_code(doc.read_text(encoding="utf-8"))
    broken: list[str] = []

    for match in _LINK.finditer(text):
        target = match.group(1)
        resolved = _resolve(doc, target)
        if resolved is None:
            continue
        # Only govern links into the repository's own tracked content.
        if not str(resolved).startswith(str(REPO_ROOT)):
            continue
        if not (resolved.exists() or resolved.with_suffix(".md").exists()):
            broken.append(target)

    assert not broken, (
        f"{doc.relative_to(REPO_ROOT)} contains links that resolve to nothing:\n  "
        + "\n  ".join(broken)
    )
