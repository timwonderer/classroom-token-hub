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

# Migrations written before the retirement, and the retirement itself. They are
# history (SOP-DB-001 Golden Rule 3): they name the tables because they created,
# altered, remapped or dropped them.
HISTORICAL_MIGRATIONS = frozenset({
    "migrations/baseline/0001_baseline_schema.sql",
    "migrations/versions/0007_obligations_schema_contract.py",
    "migrations/versions/3bb29ef4e874_payroll_hall_pass_settings_append_only.py",
    "migrations/versions/7c3d4e5f6a7b_drop_all_unauthorized_tables.py",
    "migrations/versions/8f1a2c3d4b5e_add_policy_transition_created_by_fk.py",
    "migrations/versions/a1b2c3d4e5f6_repoint_obligation_assessment_policy_version_.py",
    "migrations/versions/a7e3c9d1f5b2_payroll_settings_effective_dated_authority.py",
    "migrations/versions/b2c3d4e5f8a_align_prod_domain_schema_contract.py",
    "migrations/versions/b3c4d5e6f7a8_manual_credit_without_payroll_policy.py",
    "migrations/versions/b7d3e2064c15_drop_prohibited_policy_version_pointer_from_payroll_settings.py",
    "migrations/versions/c3d4e5f8a9b_align_prod_domain_schema_contract_v2.py",
    "migrations/versions/c4e36a4ab2f1_add_policy_lineage_tables.py",
    "migrations/versions/c7a7b8c9d0e1_seat_owned_records.py",
    "migrations/versions/d4e5f6a7b8c9_normalize_insurance_claim_type_taxonomy.py",
    "migrations/versions/dd4e5f6a7b8c_add_policy_uuid_to_payroll_provenance.py",
    "migrations/versions/dd52b19d48d8_retire_policy_versions_and_transitions.py",
    "migrations/versions/e5f6a7b8c9d0_align_prod_indexes_with_orm.py",
    "migrations/versions/f6a7b8c9d0e2_restrict_payroll_event_policy_fk.py",
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
