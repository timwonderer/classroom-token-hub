"""Exercise the installed Flask-Migrate CLI against a private migration tree."""
from pathlib import Path
from shutil import copyfile
from uuid import UUID

import pytest
from alembic.script import ScriptDirectory

from scripts import generate_revision_id as ids


@pytest.fixture
def private_migrations(tmp_path):
    root = tmp_path / "migrations"
    versions = root / "versions"
    versions.mkdir(parents=True)
    template = Path(__file__).resolve().parents[1] / "migrations" / "script.py.mako"
    copyfile(template, root / "script.py.mako")
    (versions / "unrelated_filename.py").write_text("revision = 'aaaaaaaaaaaa'\ndown_revision = None\n")
    return root


@pytest.mark.parametrize("command", ["migrate", "revision", "merge"])
def test_explicit_duplicate_is_refused_before_generation(app, private_migrations, command):
    result = app.test_cli_runner().invoke(args=[
        "db", command, "--rev-id", "aaaaaaaaaaaa", "-d", str(private_migrations),
    ])
    assert result.exit_code == 1, result.output
    assert "Revision ID 'aaaaaaaaaaaa' already exists" in result.output
    assert len(list((private_migrations / "versions").glob("*.py"))) == 1


def test_revision_retries_collision_and_merge_preserves_requested_id(app, private_migrations, monkeypatch):
    draws = iter((UUID("a" * 32), UUID("b" * 32)))
    monkeypatch.setattr(ids, "uuid4", lambda: next(draws))
    runner = app.test_cli_runner()
    command = ["db", "-d", str(private_migrations)]
    for args in (
        ["revision", "-m", "first branch"],
        ["revision", "--head", "aaaaaaaaaaaa", "--splice", "--rev-id", "second", "-m", "second branch"],
        ["merge", "--rev-id", "joined", "heads", "-m", "merge"],
    ):
        result = runner.invoke(args=[*command, *args])
        assert result.exit_code == 0, (result.output, result.exception)
    merged = ScriptDirectory(str(private_migrations)).get_revision("joined")
    assert set(merged.down_revision) == {"bbbbbbbbbbbb", "second"}


def test_autogenerate_uses_unused_id(app, private_migrations, monkeypatch):
    """Use the migrated PostgreSQL test DB and generate a file only in tmp_path."""
    from sqlalchemy import text
    from app.extensions import db

    # Give this independent test tree the database's actual current revision.
    current = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    versions = private_migrations / "versions"
    (versions / "database_head.py").write_text(
        f"revision = {current!r}\ndown_revision = 'aaaaaaaaaaaa'\n"
    )
    (private_migrations / "env.py").write_text(
        "from alembic import context\n"
        "from sqlalchemy import MetaData, Table, Column, Integer\n"
        "from flask import current_app\n"
        "metadata = MetaData()\n"
        "Table('collision_guard_fixture', metadata, Column('id', Integer, primary_key=True))\n"
        "with current_app.extensions['migrate'].db.engine.connect() as conn:\n"
        "    context.configure(connection=conn, target_metadata=metadata,\n"
        "                      include_name=lambda name, typ, parents: typ != 'table')\n"
        "    context.run_migrations()\n"
    )
    draws = iter((UUID("a" * 32), UUID("b" * 32)))
    monkeypatch.setattr(ids, "uuid4", lambda: next(draws))
    result = app.test_cli_runner().invoke(args=["db", "migrate", "-m", "fixture", "-d", str(private_migrations)])
    assert result.exit_code == 0, (result.output, result.exception)
    generated = ScriptDirectory(str(private_migrations)).get_revision("bbbbbbbbbbbb")
    assert generated.down_revision == current
    assert "collision_guard_fixture" in Path(generated.path).read_text()
