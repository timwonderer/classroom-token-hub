"""Every forward-only Alembic revision is registered (SOP-DB-004 §V.5, §IX.4).

Past the first forward-only revision in a release, recovery is snapshot restore
or a reviewed fix-forward, so the operator must know which revisions those are
before the window opens. ``SOP-DEP-001`` §XIV's prose list was hand-kept and had
fallen behind the chain; the definition is each revision's own ``downgrade()``.

The detector lives in ``tests/guards/forward_only_revisions.py`` and the
mutation proofs below feed it the spellings a future revision would use
(SOP-TEST-003 §IX.A).
"""
from __future__ import annotations

from pathlib import Path

from tests.guards.forward_only_revisions import (
    classify_revision,
    derive_forward_only,
    read_register,
)

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"
REGISTER = ROOT / "migrations" / "forward_only_register.txt"


def _revision(downgrade_body: str, *, down="'abc'", upgrade_body="op.add_column('t', sa.Column('c', sa.Integer()))", extra=""):
    return (
        f"revision = 'zz01'\ndown_revision = {down}\n{extra}\n"
        f"def upgrade():\n    {upgrade_body}\n\n"
        f"def downgrade():\n    {downgrade_body}\n"
    )


# ---- the guard on the real chain -------------------------------------------

def test_register_equals_forward_only_revisions_in_chain():
    derived = set(derive_forward_only(VERSIONS))
    registered = read_register(REGISTER)
    unregistered = sorted(derived - registered)
    stale = sorted(registered - derived)
    assert not unregistered, (
        f"forward-only revisions missing from {REGISTER.name}: {unregistered}. "
        "Add them in the PR that creates them and name them in the release record (SOP-DB-004 §IX.4)."
    )
    assert not stale, f"{REGISTER.name} lists revisions that are not forward-only or do not exist: {stale}"


def test_detector_still_finds_the_known_forward_only_revisions():
    """A rename or refactor must not turn the guard into a no-op that keeps passing."""
    derived = derive_forward_only(VERSIONS)
    for revision in ("f9a3c7d1e620", "f8b2d6e0a410", "e7c2a9d4f610", "c7a7b8c9d0e1"):
        assert revision in derived, revision
    assert len(derived) >= 30


def test_sop_documents_point_at_the_register():
    for doc in (
        ROOT / "docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001_Live_Test_Runbook.md",
        ROOT / "docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-004_Live_V2_Migration_And_Versioning_Contract.md",
    ):
        assert "migrations/forward_only_register.txt" in doc.read_text(encoding="utf-8"), doc.name


# ---- mutation proofs: each of these must be reported ------------------------

def test_mutation_downgrade_that_raises_is_reported():
    assert classify_revision(_revision("raise RuntimeError('no')")).forward_only


def test_mutation_downgrade_that_raises_only_on_some_data_is_reported():
    body = "if op.get_bind().execute('select 1').scalar():\n        raise RuntimeError('rows exist')\n    op.drop_column('t', 'c')"
    assert classify_revision(_revision(body)).forward_only


def test_mutation_raise_hidden_in_a_helper_is_reported():
    extra = "def _refuse():\n    raise RuntimeError('no')\n"
    assert classify_revision(_revision("_refuse()", extra=extra)).forward_only


def test_mutation_noop_spellings_are_reported():
    for body in ("pass", "return", "return None", "print('nothing to undo')", "'''docstring only'''", "pass  # comment"):
        assert classify_revision(_revision(body)).forward_only, body


def test_mutation_noop_dressed_as_logging_or_control_flow_is_reported():
    bodies = (
        "logger.warning('nothing to undo')",
        "if True:\n        print('a')\n    else:\n        print('b')",
        "import logging\n    logging.getLogger(__name__).info('skipped')",
    )
    for body in bodies:
        assert classify_revision(_revision(body)).forward_only, body


def test_mutation_noop_hidden_in_a_helper_is_reported():
    extra = "def _undo():\n    pass\n"
    assert classify_revision(_revision("_undo()", extra=extra)).forward_only


def test_mutation_missing_downgrade_is_reported():
    source = "revision = 'zz01'\ndown_revision = 'abc'\ndef upgrade():\n    op.drop_table('t')\n"
    assert classify_revision(source).forward_only


def test_mutation_merge_revision_that_does_work_is_judged_on_its_downgrade():
    source = _revision("pass", down="('a', 'b')")
    assert classify_revision(source).forward_only


# ---- lawful inputs stay quiet -----------------------------------------------

def test_reversible_downgrade_is_not_reported():
    assert not classify_revision(_revision("op.drop_column('t', 'c')")).forward_only


def test_downgrade_calling_a_non_raising_helper_is_not_reported():
    extra = "def _undo():\n    op.drop_column('t', 'c')\n"
    assert not classify_revision(_revision("_undo()", extra=extra)).forward_only


def test_downgrade_that_executes_sql_is_not_reported():
    assert not classify_revision(_revision("op.get_bind().execute('update t set c = 1')")).forward_only
    assert not classify_revision(_revision("connection.execute(sa.text('delete from t'))")).forward_only


def test_downgrade_using_batch_alter_table_is_not_reported():
    body = "with op.batch_alter_table('t') as batch:\n        batch.drop_column('c')"
    assert not classify_revision(_revision(body)).forward_only


def test_pure_merge_revision_is_not_reported():
    source = _revision("pass", down="('a', 'b')", upgrade_body="pass")
    assert not classify_revision(source).forward_only
