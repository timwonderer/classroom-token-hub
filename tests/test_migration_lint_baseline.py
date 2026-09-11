"""The lint baseline must not be able to excuse the branch that edits it.

`migrations/lint_baseline.txt` freezes the pre-gate non-compliance SOP-DB-009 VI
accepts, and the gate reads it from the checkout under review. That means the
file a branch is judged against is a file the branch can edit: appending one
basename suppressed the error it was added to hide. The baseline only shrinks,
so additions are rejected against a copy taken from the base branch.

The CLI is driven as a subprocess because the exit code *is* the contract CI
consumes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LINTER = ROOT / "scripts" / "lint_migrations.py"

NON_IDEMPOTENT_MIGRATION = '''"""A migration the linter must reject"""
revision = 'zz99sneaky'
down_revision = None


def upgrade():
    op.create_table('sneaky', sa.Column('id', sa.Integer()))


def downgrade():
    op.drop_table('sneaky')
'''


def _run(*args):
    return subprocess.run(
        [sys.executable, str(LINTER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def failing_migration(tmp_path):
    path = tmp_path / "zz99_sneaky_migration.py"
    path.write_text(NON_IDEMPOTENT_MIGRATION, encoding="utf-8")
    return path


def test_a_non_idempotent_migration_fails_on_its_own(failing_migration):
    """The premise of the whole test: this file is genuinely rejected."""
    result = _run(str(failing_migration))
    assert result.returncode == 1, result.stdout


def test_self_added_baseline_entry_cannot_suppress_the_failure(failing_migration, tmp_path):
    """The hole: the branch adds its own migration to the baseline it is judged by."""
    trusted = tmp_path / "trusted.txt"
    trusted.write_text("", encoding="utf-8")
    tampered = tmp_path / "tampered.txt"
    tampered.write_text(f"{failing_migration.name}\n", encoding="utf-8")

    result = _run(
        str(failing_migration),
        "--baseline", str(tampered),
        "--trusted-baseline", str(trusted),
    )

    assert result.returncode == 1, result.stdout
    assert failing_migration.name in result.stdout


def test_an_entry_present_on_the_base_branch_still_suppresses(failing_migration, tmp_path):
    """Accepted debt must keep being accepted, or the gate blocks every PR."""
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(f"{failing_migration.name}\n", encoding="utf-8")

    result = _run(
        str(failing_migration),
        "--baseline", str(baseline),
        "--trusted-baseline", str(baseline),
    )

    assert result.returncode == 0, result.stdout


def test_comments_and_blank_lines_are_not_read_as_additions(failing_migration, tmp_path):
    """Reformatting the baseline is not an addition to it."""
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        f"# accepted pre-gate debt\n\n{failing_migration.name}  # SOP-DB-009 VI\n",
        encoding="utf-8",
    )
    trusted = tmp_path / "trusted.txt"
    trusted.write_text(f"{failing_migration.name}\n", encoding="utf-8")

    result = _run(
        str(failing_migration),
        "--baseline", str(baseline),
        "--trusted-baseline", str(trusted),
    )

    assert result.returncode == 0, result.stdout
