"""Structural guards: the retired policy-lineage tables stay retired.

Operator ruling 2026-09-30. ``policy_versions`` / ``policy_transitions`` were
removed from the Policies domain in ``184910af8`` and came back through a new
document in ``abb49d75e``, so two guards hold the retirement:

* no source under ``app/``, ``scripts/``, ``templates/`` or ``migrations/``
  (outside the historical migrations) names them;
* no normative document presents them as canonical — a paragraph may name them
  only to record that they are retired.

The detectors live in ``tests/guards/retired_policy_lineage.py``; the mutation
proofs feed each the spellings a regression would really use (SOP-TEST-003 §IX.A),
so a green run means "no violation", not "the detector stopped detecting".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guards.retired_policy_lineage import (
    HISTORICAL_MIGRATIONS,
    find_canonical_doc_mentions,
    find_code_references,
)

REPO = Path(__file__).resolve().parents[1]
CODE_ROOTS = ("app", "scripts", "templates", "migrations")
CODE_SUFFIXES = {".py", ".html", ".js", ".sql", ".jinja", ".j2", ".txt", ".mako", ".sh"}
NORMATIVE_ROOTS = (
    "docs/INVARIANT",
    "docs/DOMAIN",
    "docs/FEATURE-EXECUTION",
    "docs/SPEC",
    "docs/STANDARD_OPERATING_PROCEDURES",
)


def _files(roots, suffixes):
    for root in roots:
        for path in sorted((REPO / root).rglob("*")):
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts:
                yield str(path.relative_to(REPO)), path.read_text(encoding="utf-8", errors="replace")


def test_no_source_names_the_retired_tables():
    violations = [
        violation
        for path, text in _files(CODE_ROOTS, CODE_SUFFIXES)
        if not path.startswith("migrations/archive/")
        for violation in find_code_references(path, text)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


def test_no_normative_document_presents_the_retired_tables_as_canonical():
    violations = [
        violation
        for path, text in _files(NORMATIVE_ROOTS, {".md"})
        for violation in find_canonical_doc_mentions(path, text)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


def test_the_allowlist_names_only_files_that_exist():
    """A stale allowlist entry would silently excuse a new file of that name."""
    missing = sorted(path for path in HISTORICAL_MIGRATIONS if not (REPO / path).is_file())
    assert not missing, missing


@pytest.mark.parametrize("snippet", [
    "from app.models import PolicyVersion\n",
    "from app.models import PolicyTransition as PT\n",
    "rows = db.session.execute(text('SELECT * FROM policy_versions'))\n",
    "op.create_table('policy_transitions', sa.Column('id', sa.Integer()))\n",
    "policy_version_id = db.Column(db.Integer, db.ForeignKey('policy_versions.id'))\n",
    "# pending changes live in PolicyTransitions\n",
    "{{ policy_version.policy_payload_json }}\n",
    "request.policy_version_id\n",
])
def test_mutation_proof__each_code_reference_is_reported(snippet):
    assert find_code_references("app/example.py", snippet), snippet


def test_mutation_proof__a_new_migration_is_not_excused():
    create = "op.create_table('policy_versions', sa.Column('id', sa.Integer()))\n"
    assert find_code_references("migrations/versions/abc123_new.py", create)
    assert find_code_references(
        "migrations/versions/dd52b19d48d8_retire_policy_versions_and_transitions.py", create
    ) == []


def test_mutation_proof__a_longer_identifier_is_not_reported():
    assert find_code_references("app/example.py", "rent_policy_version_id = 1\n") == []
    assert find_code_references("app/example.py", "get_last_entitlement_end_for_policy_version()\n") == []


@pytest.mark.parametrize("paragraph", [
    "## 1. policy_versions\n\nRepresents immutable constitutional economics policy truth.\n",
    "A pending change is a `policy_transitions` row with `activation_mode = next_boundary`.\n",
    "`DOM-CLASS-003` (`policy_versions` / `policy_transitions`) records economic-policy evolution only.\n",
    "| `policy_versions` | DOM-CLASS | class-wide economic policy versions |\n",
    "Payroll reads `PolicyVersion` rows at the boundary.\n",
])
def test_mutation_proof__a_canonical_presentation_is_reported(paragraph):
    assert find_canonical_doc_mentions("docs/DOMAIN/DOM-X.md", paragraph), paragraph


def test_mutation_proof__a_retirement_record_is_not_reported():
    text = (
        "`policy_versions` and `policy_transitions` were retired by operator ruling "
        "2026-09-30; they were never authorized as canonical.\n\n"
        "| `policy_versions` | Retired 2026-09-30 |\n"
    )
    assert find_canonical_doc_mentions("docs/DOMAIN/DOM-X.md", text) == []


def test_mutation_proof__one_retired_table_row_does_not_excuse_its_neighbour():
    table = (
        "| Table | Status |\n"
        "| `policy_transitions` | Retired 2026-09-30 |\n"
        "| `policy_versions` | DOM-CLASS |\n"
    )
    violations = find_canonical_doc_mentions("docs/DOMAIN/DOM-X.md", table)
    assert [v.line for v in violations] == [3]
