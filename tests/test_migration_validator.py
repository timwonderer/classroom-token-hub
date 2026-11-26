"""The migration idempotency gate must fail on real defects and only on those.

`scripts/validate-migrations.py` is auxiliary evidence for the CI-PERSIST
invariant family, so a false positive blocks every migration-touching PR and a
false negative lets a non-idempotent migration reach deployment. Both directions
are covered here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_migrations", ROOT / "scripts" / "validate-migrations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _check(tmp_path, source):
    path = tmp_path / "0001_example.py"
    path.write_text(source, encoding="utf-8")
    return [error for error in validator.check_idempotency(path) if error.startswith("❌")]


def test_unguarded_add_column_is_still_an_error(tmp_path):
    errors = _check(tmp_path, """
def upgrade():
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""")
    assert len(errors) == 1
    assert "Unguarded add_column()" in errors[0]


def test_add_column_nested_in_an_existence_check_passes(tmp_path):
    assert _check(tmp_path, """
def upgrade():
    if not column_exists('issues', 'class_label'):
        op.add_column('issues', sa.Column('class_label', sa.String(255)))
""") == []


def test_add_column_after_a_returning_guard_clause_passes(tmp_path):
    """The early-return guard is equivalent protection to an enclosing block."""
    assert _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        print("already applied")
        return
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""") == []


def test_a_guard_clause_that_does_not_return_protects_nothing(tmp_path):
    """Falling through an `if` leaves the following statement unconditional."""
    errors = _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        print("already applied")
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""")
    assert len(errors) == 1


def test_a_guard_clause_does_not_leak_into_a_later_function(tmp_path):
    errors = _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        return
    op.add_column('issues', sa.Column('class_label', sa.String(255)))


def downgrade():
    op.add_column('issues', sa.Column('resurrected', sa.String(255)))
""")
    assert len(errors) == 1
    assert "Unguarded add_column()" in errors[0]


@pytest.mark.parametrize("name", [
    "a1c4e7d92f30_issues_class_label_submission_freeze.py",
    "e6f7a8b9c0d1_canonicalize_ledger_persistence.py",
])
def test_committed_guard_clause_migrations_are_accepted(name):
    """Regression: these two used the early-return form and were falsely flagged.

    Both are pre-launch revisions kept as provenance (SOP-DB-001 §V.C); the
    validator reads them as text, which is all this regression needs.
    """
    path = ROOT / "migrations" / "archive" / "v2_prelaunch" / "versions" / name
    errors = [e for e in validator.check_idempotency(path) if e.startswith("❌")]
    assert errors == []


def test_final_tree_rejects_duplicate_ids_under_different_filenames(tmp_path, monkeypatch, capsys):
    source = "revision = 'same'\ndown_revision = None\ndef upgrade(): pass\ndef downgrade(): pass\n"
    (tmp_path / "first.py").write_text(source)
    (tmp_path / "second.py").write_text(source.replace("revision =", "revision: str ="))
    monkeypatch.setattr(validator, "MIGRATIONS_DIR", tmp_path)
    assert validator.validate_migrations() == 1
    assert "Duplicate revision ID 'same': first.py and second.py" in capsys.readouterr().out


@pytest.mark.parametrize("declaration", [
    "revision = 'first'\nrevision = 'parent'",
    "revision = 'first'\nrevision: str = 'parent'",
    "revision = alias = 'child'",
    "revision, alias = 'child', 1",
    "if True:\n    revision = 'child'",
    "revision = 'child'\nif True:\n    revision = 'parent'",
    "revision = 'child'\nmatch 'parent':\n    case revision:\n        pass",
    "revision = 'child'\ntry:\n    pass\nexcept Exception as revision:\n    pass",
    "revision = 'child'\nrevision += '_changed'",
    "revision = 'child'\ndel revision",
    "revision = str(123)",
])
def test_ambiguous_revision_fails_ci(tmp_path, monkeypatch, capsys, declaration):
    functions = "\ndef upgrade(): pass\ndef downgrade(): pass\n"
    (tmp_path / "base.py").write_text("revision = 'parent'\ndown_revision = None" + functions)
    (tmp_path / "child.py").write_text(declaration + "\ndown_revision = 'parent'" + functions)
    monkeypatch.setattr(validator, "MIGRATIONS_DIR", tmp_path)
    assert validator.validate_migrations() == 1
    assert "Error parsing child.py" in capsys.readouterr().out


@pytest.mark.parametrize("declaration", [
    "down_revision = 'parent'\ndown_revision = None",
    "down_revision: str = ''",
    "down_revision = ['parent']",
    "down_revision = ()",
    "down_revision = ('parent', None)",
    "down_revision = 1",
])
def test_invalid_parent_rejected_before_graph_traversal(tmp_path, declaration):
    path = tmp_path / "child.py"
    path.write_text("revision = 'child'\n" + declaration)
    with pytest.raises(ValueError, match="down_revision"):
        validator.extract_migration_info(path)


@pytest.mark.parametrize("declaration, parents", [
    ("down_revision = None", None),
    ("down_revision: str = 'parent'", "parent"),
    ("down_revision = (\n    'left',\n    'right',\n)", ("left", "right")),
])
def test_unambiguous_literal_declarations(tmp_path, declaration, parents):
    path = tmp_path / "example.py"
    path.write_text("revision: str = 'child'\n" + declaration
                    + "\ndef upgrade():\n    revision = 'local'\n")
    info = validator.extract_migration_info(path)
    assert (info["revision"], info["down_revision"]) == ("child", parents)
