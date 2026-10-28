"""Migration e3b7c1d9a2f4 removes `bug_reward` from the ledger type vocabulary.

DOM-LED-001 v2.18 drops `bug_reward` from INV-LED-017 (owner ruling 2026-10-27).
The constraint is NOT VALID, so the migration itself must refuse to run while a
row still carries the retired type. Each test runs the revision against an
old-shape `ledger_transaction` in a scratch schema, inside a transaction that is
rolled back, so the shared test database is untouched.
"""
import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db

MIGRATION = "migrations/versions/e3b7c1d9a2f4_remove_bug_reward_from_ledger_type_vocabulary.py"
CHECK = "ck_ledger_transaction_type_closed_vocabulary"


def _migration(connection):
    path = Path(__file__).resolve().parents[3] / MIGRATION
    spec = importlib.util.spec_from_file_location("bug_reward_vocabulary_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


@pytest.fixture
def old_schema(app):
    """A connection whose search_path is a scratch schema holding the v2.17 table."""
    schema = f"rehearsal_{uuid.uuid4().hex[:12]}"
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        connection.execute(sa.text(f"CREATE SCHEMA {schema}"))
        connection.execute(sa.text(f"SET LOCAL search_path TO {schema}"))
        migration = _migration(connection)
        connection.execute(sa.text("CREATE TABLE ledger_transaction (id serial PRIMARY KEY, type varchar(50))"))
        connection.execute(sa.text(
            f"ALTER TABLE ledger_transaction ADD CONSTRAINT {CHECK} "
            f"CHECK ({migration._check_sql(migration._PREVIOUS_ALLOWED_TYPES)}) NOT VALID"
        ))
        try:
            yield connection, migration
        finally:
            transaction.rollback()
            connection.close()


def _insert(connection, type_value):
    with connection.begin_nested():
        connection.execute(sa.text("INSERT INTO ledger_transaction (type) VALUES (:t)"), {"t": type_value})


def _types(connection):
    return connection.execute(sa.text("SELECT type FROM ledger_transaction ORDER BY id")).scalars().all()


def test_DOM_LED_001__upgrade_retires_bug_reward_and_downgrade_restores_it(old_schema):
    connection, migration = old_schema
    for value in ("payroll", "Interest", "REVERSAL", None):
        _insert(connection, value)
    before = _types(connection)

    migration.upgrade()

    with pytest.raises(sa.exc.IntegrityError, match=CHECK):
        _insert(connection, "bug_reward")
    _insert(connection, "manual_payment")
    assert _types(connection) == before + ["manual_payment"]

    migration.upgrade()  # idempotent: the constraint already excludes it
    migration.downgrade()

    _insert(connection, "bug_reward")
    assert _types(connection) == before + ["manual_payment", "bug_reward"]


def test_DOM_LED_001__upgrade_refuses_while_a_bug_reward_row_exists(old_schema):
    connection, migration = old_schema
    _insert(connection, "bug_reward")

    with pytest.raises(RuntimeError, match="1 ledger_transaction row"):
        migration.upgrade()

    _insert(connection, "bug_reward")  # the v2.17 constraint is still in force
