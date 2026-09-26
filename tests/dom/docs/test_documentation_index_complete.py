"""SOP-DOC-001 claims to index every formal document. This holds it to that.

The index is normative (SOP-DOC-001 §III) and §I calls it "the canonical master
index of all formal documentation within the Classroom Token Hub repository".
Version 3.3 listed 85 of 131 numbered documents while saying exactly that.

An index fails differently from other documents: every link in 3.3 resolved, so
nothing looked wrong. Absence is the defect, and absence has no symptom on the
page — only a reader who already knows the document exists can notice it is
missing. That is why this is a test rather than a review item.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO_ROOT / "docs"
INDEX = DOCS_ROOT / "STANDARD_OPERATING_PROCEDURES" / "SOP-DOC-001_DOCUMENTATION_INDEX.md"

# The registered namespaces, per SOP-DOC-000. A numbered filename in any of
# them is a formal document; docs/user-guides, docs/archive, docs/TRACKING,
# docs/ops and docs/self-hosting hold no numbered documents and are out of
# scope per SOP-DOC-001 §II.
_DOC_ID = re.compile(r"((?:INV|DOM|FEAT|SPEC|SOP|MAP|REF|PRN)-[A-Z]+-\d{3}[A-Z]?)")


def registered_documents(docs_root):
    """Every numbered document on disk, as {id: path relative to docs/}.

    Pure over a directory tree so the detector can be pointed at a synthetic
    tree containing a document the index cannot possibly list.
    """
    found = {}
    for path in sorted(Path(docs_root).rglob("*.md")):
        if "archive" in path.parts:
            continue
        match = _DOC_ID.match(path.name)
        if match:
            found[match.group(1)] = path.relative_to(docs_root)
    return found


def indexed_documents(index_source):
    """Document ids the index links to, as {id: link target}."""
    linked = {}
    for _, target in re.findall(r"\[([^\]]+)\]\(\s*([^)\s]+)\s*\)", index_source):
        match = _DOC_ID.match(Path(target).name)
        if match:
            linked[match.group(1)] = target
    return linked


def test_the_detectors_see_a_document_the_index_omits(tmp_path):
    """Mutation proof: a document present on disk and absent from the index.

    The near miss is a new FEAT contract added without an index entry, which is
    how 3.3 lost most of the FEAT namespace in the first place.
    """
    (tmp_path / "FEATURE-EXECUTION").mkdir()
    (tmp_path / "FEATURE-EXECUTION" / "FEAT-ZZZ-001_NEW_CONTRACT.md").write_text(
        "# FEAT-ZZZ-001: New Contract\n", encoding="utf-8"
    )

    on_disk = registered_documents(tmp_path)
    indexed = indexed_documents("- [SOP-DOC-000](SOP-DOC-000_DOCUMENTATION_STANDARD.md)\n")

    assert "FEAT-ZZZ-001" in on_disk
    assert set(on_disk) - set(indexed) == {"FEAT-ZZZ-001"}


def test_every_numbered_document_is_indexed():
    on_disk = registered_documents(DOCS_ROOT)
    indexed = indexed_documents(INDEX.read_text(encoding="utf-8"))

    missing = sorted(set(on_disk) - set(indexed))
    assert not missing, (
        f"{len(missing)} document(s) exist but SOP-DOC-001 does not list them: {missing}"
    )


def test_the_index_lists_no_document_that_does_not_exist():
    on_disk = registered_documents(DOCS_ROOT)
    indexed = indexed_documents(INDEX.read_text(encoding="utf-8"))

    phantom = sorted(set(indexed) - set(on_disk))
    assert not phantom, f"SOP-DOC-001 lists document(s) that do not exist: {phantom}"


def test_every_index_link_resolves():
    """A link that resolves to nothing is indistinguishable from one satisfied."""
    broken = []
    for _, target in re.findall(
        r"\[([^\]]+)\]\(\s*([^)\s]+)\s*\)", INDEX.read_text(encoding="utf-8")
    ):
        if target.startswith(("http://", "https://", "#")):
            continue
        resolved = (INDEX.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            broken.append(target)

    assert not broken, f"SOP-DOC-001 links that resolve to nothing: {broken}"
