"""Detection of the retired class-wide policy-lineage tables.

Operator ruling 2026-09-30: ``policy_versions`` and ``policy_transitions``
(models ``PolicyVersion`` / ``PolicyTransition``) were never authorized as
canonical and are retired. Each domain's own append-only, effective-dated table
is its policy history (DOM-POL-001 §VI.0, DOM-CLASS-003 §V). They were removed
once already (``184910af8``) and came back through a new document
(``abb49d75e``), so both the runtime and the normative documents are guarded.

Factored out of the tests so each detector can be fed a synthetic violation and
proved to report it (SOP-TEST-003 §IX.A).

* ``find_code_references`` reports any mention in a source file — code, SQL
  text, template, comment. Nothing under ``app/``, ``scripts/`` or
  ``templates/`` has a reason to name the tables, and a new migration has a
  reason only to have dropped them; the historical migrations are the one
  allowlist.
* ``find_canonical_doc_mentions`` reports a paragraph of a normative document
  that names the tables without recording their retirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ``PolicyVersion``, ``PolicyTransitions``, ``policy_versions``,
# ``policy_transition``, ``policy_version_id`` … as whole identifiers. A longer
# identifier that merely ends in one of them (``rent_policy_version_id``) is a
# different name.
RETIRED_NAME = re.compile(
    r"(?<![A-Za-z0-9_])(?:Policy(?:Version|Transition)s?|policy_(?:version|transition)s?(?:_id)?)(?![A-Za-z0-9_])"
)

# The v2 launch baseline (the tables existed at launch), the migrations written
# before the retirement, and the retirement itself. They are history (SOP-DB-001
# Golden Rule 3): they name the tables because they created, altered, remapped or
# dropped them. Pre-launch revisions are provenance under migrations/archive/,
# which the guard does not scan.
HISTORICAL_MIGRATIONS = frozenset({
    "migrations/baseline/d7a3e9b1c5f2_v2_launch_schema.sql",
    "migrations/versions/a7e3c9d1f5b2_payroll_settings_effective_dated_authority.py",
    "migrations/versions/dd52b19d48d8_retire_policy_versions_and_transitions.py",
})

# Words that make a paragraph a record of the retirement rather than a use.
RETIREMENT_MARKERS = re.compile(r"\bretire(?:d|ment)\b|\bnever authorized\b", re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — retired policy-lineage table named: {self.excerpt}"


def _normalized(path: str) -> str:
    return path.replace("\\", "/")


def find_code_references(path: str, text: str) -> list[Violation]:
    """Every line of one source file that names a retired table or model."""
    if _normalized(path) in HISTORICAL_MIGRATIONS:
        return []
    return [
        Violation(path, number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if RETIRED_NAME.search(line)
    ]


def _paragraphs(text: str):
    """(first line number, lines) for each block separated by blank lines.

    Each Markdown table row is a block of its own: a table lists many things,
    and one retired row must not excuse its neighbours.
    """
    block: list[str] = []
    start = 1
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("|"):
            if block:
                yield start, block
                block = []
            yield number, [line]
        elif line.strip():
            if not block:
                start = number
            block.append(line)
        elif block:
            yield start, block
            block = []
    if block:
        yield start, block


def find_canonical_doc_mentions(path: str, text: str) -> list[Violation]:
    """Paragraphs that name a retired table without recording its retirement.

    A normative document may name the tables only to say they are retired —
    a changelog note, an amendment record, a prohibition. Anything else presents
    them as part of the schema, which is the drift this guard exists to stop.
    """
    found = []
    for start, lines in _paragraphs(text):
        paragraph = "\n".join(lines)
        if not RETIRED_NAME.search(paragraph) or RETIREMENT_MARKERS.search(paragraph):
            continue
        for offset, line in enumerate(lines):
            if RETIRED_NAME.search(line):
                found.append(Violation(path, start + offset, line.strip()))
                break
    return found
