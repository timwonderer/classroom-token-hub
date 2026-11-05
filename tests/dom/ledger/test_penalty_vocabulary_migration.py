"""Migration a0faf8b2a35d adds `penalty` to the ledger type vocabulary.

DOM-LED-001 v2.19 adds `penalty` to INV-LED-017 for teacher-applied fines
(FEAT-LED-006; owner ruling 2026-11-04). Upgrade only widens the vocabulary;
downgrade narrows it, so it must refuse while a `penalty` row exists. Each test
runs the revision against a v2.18-shape `ledger_transaction` in a scratch
schema, inside a transaction that is rolled back.
"""
import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db

MIGRATION = "migrations/versions/a0faf8b2a35d_add_penalty_to_ledger_type_vocabulary.py"
CHECK = "ck_ledger_transaction_type_closed_vocabulary"


def _migration(connection):
    path = Path(__file__).resolve().parents[3] / MIGRATION
    spec = importlib.util.spec_from_file_location("penalty_vocabulary_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


@pytest.fixture
def old_schema(app):
    """A connection whose search_path is a scratch schema holding the v2.18 table."""
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


def test_DOM_LED_001__upgrade_admits_penalty_and_downgrade_removes_it(old_schema):
    connection, migration = old_schema
    with pytest.raises(sa.exc.IntegrityError, match=CHECK):
        _insert(connection, "penalty")

    migration.upgrade()
    migration.upgrade()  # idempotent: the constraint already admits it
    _insert(connection, "penalty")
    connection.execute(sa.text("DELETE FROM ledger_transaction"))

    migration.downgrade()
    with pytest.raises(sa.exc.IntegrityError, match=CHECK):
        _insert(connection, "penalty")
    _insert(connection, "manual_payment")


def test_DOM_LED_001__downgrade_refuses_while_a_penalty_row_exists(old_schema):
    connection, migration = old_schema
    migration.upgrade()
    _insert(connection, "penalty")

    with pytest.raises(RuntimeError, match="1 ledger_transaction row"):
        migration.downgrade()

    _insert(connection, "penalty")  # the v2.19 constraint is still in force
