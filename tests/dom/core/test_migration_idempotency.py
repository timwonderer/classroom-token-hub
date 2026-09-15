"""
Test migration idempotency to ensure migrations can be run multiple times safely.

These tests run against the shared Postgres test database rather than SQLite.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import inspect, text

from app import db
from app.feats.base import FEATContext
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from app.services.context_resolver import CanonicalContext
from app.services.store_service import set_product_visibility
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.store_products import publish_store_product

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations" / "versions"


def _load_revision_module(revision_prefix):
    """Import one migration module by the revision id its filename starts with."""
    matches = sorted(MIGRATIONS_DIR.glob(f"{revision_prefix}*.py"))
    assert matches, f"No migration file found for revision {revision_prefix}"
    assert len(matches) == 1, f"Ambiguous revision prefix {revision_prefix}: {matches}"
    spec = importlib.util.spec_from_file_location(
        f"_migration_{revision_prefix}", matches[0]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == revision_prefix, (
        f"{matches[0].name} declares revision {module.revision!r}, which does not "
        f"match its filename prefix {revision_prefix!r}"
    )
    return module


def _reapply(revision_prefix):
    """Run one revision's ``upgrade()`` against a schema that already has it.

    This is the deployment failure mode the idempotency helpers exist for: a
    migration re-run over a database where its changes are already present. It
    binds a real Alembic operations context so ``op.*`` inside the migration
    executes against the live connection, rather than simulating the migration
    with a throwaway table.
    """
    module = _load_revision_module(revision_prefix)
    with db.engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            module.upgrade()


def _reset_schema():
    db.session.remove()
    with db.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        enum_rows = conn.execute(
            text(
                """
                SELECT t.typname
                FROM pg_type AS t
                JOIN pg_namespace AS n ON n.oid = t.typnamespace
                WHERE t.typtype = 'e' AND n.nspname = 'public'
                """
            )
        )
        for row in enum_rows:
            conn.execute(text(f'DROP TYPE IF EXISTS "{row.typname}" CASCADE'))
    db.engine.dispose()
    db.create_all()


@pytest.fixture
def test_db(app):
    """Create a clean Postgres test database with all necessary tables."""
    with app.app_context():
        _reset_schema()
        yield db


@pytest.fixture
def migrated_db(app):
    """Build the schema by running the migration chain, not from ORM metadata.

    ``db.create_all()`` builds whatever the models currently declare, which says
    nothing about whether the migrations that are supposed to produce that shape
    actually do. These tests need the migrated schema, so they apply the chain.
    """
    with app.app_context():
        db.session.remove()
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            enum_rows = conn.execute(
                text(
                    """
                    SELECT t.typname
                    FROM pg_type AS t
                    JOIN pg_namespace AS n ON n.oid = t.typnamespace
                    WHERE t.typtype = 'e' AND n.nspname = 'public'
                    """
                )
            )
            for row in enum_rows:
                conn.execute(text(f'DROP TYPE IF EXISTS "{row.typname}" CASCADE'))
        db.engine.dispose()
        alembic_upgrade()
        yield db
        db.session.remove()


def test_column_exists_helper(test_db):
    """Test the column existence detection logic used in migrations."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    test_column VARCHAR(50)
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("test_table")]
    assert "test_column" in columns
    assert "nonexistent_column" not in columns


def test_store_products_consolidation_is_idempotent(migrated_db):
    """The canonical store migration survives a second application.

    The migration chain runs first, then ``b7c41e9a2f30.upgrade()`` runs again
    over the schema the whole chain produced. This used to be exercised against a
    throwaway ``test_store_items`` table, so the test passed whether or not the
    real migration was idempotent — or even whether it produced ``store_products``
    at all.

    Matching columns are not enough. Each destructive step was guarded by bare
    existence, so a re-application dropped and recreated ``store_products``,
    cleared ``store_item_visibility`` and NULLed ``entitlement_events.product_id``.
    Until later Store revisions changed the table's shape, the recreated table
    had the same columns and the data loss passed unseen. So a product, a
    visibility restriction and a grant are written through their canonical paths
    first, and all three must survive.
    """
    inspector = inspect(db.engine)
    assert "store_products" in inspector.get_table_names()
    assert "store_items" not in inspector.get_table_names()
    columns = [col["name"] for col in inspector.get_columns("store_products")]
    assert "user_id" in columns
    assert "teacher_id" not in columns
    assert "product_lineage_uuid" in columns

    classroom = provision_classroom("chemistry_p1")
    student_seat_id = classroom.students[0].seat_id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="reapply-b7c41e9a2f30:product"):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="HALL_PASS",
            name="Reapplied Hall Pass",
            created_by_seat_id=classroom.teacher_seat_id,
        )
        set_product_visibility(product.product_lineage_uuid, [student_seat_id])
    db.session.commit()
    granted = execute_direct_grant(
        canonical_context=CanonicalContext(
            user_id=classroom.teacher_user_id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat_id,
            actor_role="teacher",
        ),
        target_seat_id=student_seat_id,
        policy_uuid=product.policy_uuid,
    )
    assert granted.success is True
    db.session.commit()

    def _store_state():
        with db.engine.connect() as conn:
            return {
                "products": conn.execute(
                    text("SELECT policy_uuid, product_lineage_uuid, name FROM store_products")
                ).all(),
                "visibility": conn.execute(
                    text("SELECT product_lineage_uuid, seat_id FROM store_item_visibility")
                ).all(),
                "event_products": conn.execute(
                    text("SELECT event_id, product_id FROM entitlement_events ORDER BY event_id")
                ).all(),
            }

    before = _store_state()
    assert before["products"] == [
        (product.policy_uuid, product.product_lineage_uuid, "Reapplied Hall Pass")
    ]
    assert before["visibility"] == [(product.product_lineage_uuid, student_seat_id)]
    assert before["event_products"]
    assert {product_id for _, product_id in before["event_products"]} == {
        product.product_lineage_uuid
    }

    db.session.remove()
    _reapply("b7c41e9a2f30")

    # Data first: it is the loss that matching columns used to hide.
    assert _store_state() == before
    inspector = inspect(db.engine)
    assert "store_products" in inspector.get_table_names()
    columns_after = [col["name"] for col in inspector.get_columns("store_products")]
    assert sorted(columns_after) == sorted(columns)


def test_item_type_vocabulary_migration_is_idempotent(migrated_db):
    """The item_type check constraint is added once and re-applies cleanly."""
    def _constraint_present():
        with db.engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT 1 FROM information_schema.table_constraints "
                    "WHERE table_name = 'store_products' "
                    "AND constraint_name = 'ck_store_products_item_type'"
                )
            ).first() is not None

    assert _constraint_present()
    _reapply("f1a2c3d4e5b6")
    assert _constraint_present()


def test_compensation_subtype_migration_is_idempotent(migrated_db):
    """The reversal subtype column is added once and re-applies cleanly."""
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("ledger_transaction")]
    assert "compensation_subtype" in columns

    _reapply("a3b4c5d6e7f8")

    inspector = inspect(db.engine)
    assert sorted(
        col["name"] for col in inspector.get_columns("ledger_transaction")
    ) == sorted(columns)


def test_migration_w2x3y4z5a6b7_idempotency(test_db):
    """Test that the canonical settings tables no longer expose legacy teacher scoping."""
    tables = ["rent_settings", "payroll_settings", "hall_pass_settings"]

    inspector = inspect(db.engine)
    for table in tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "class_id" in columns
        assert "teacher_id" not in columns

    test_tables = ["test_rent", "test_payroll", "test_banking", "test_hall_pass"]
    with db.engine.begin() as conn:
        for table in test_tables:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INTEGER PRIMARY KEY,
                        setting_value VARCHAR(100)
                    )
                    """
                )
            )

    inspector = inspect(db.engine)
    for table in test_tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "teacher_id" not in columns

    with db.engine.begin() as conn:
        for table in test_tables:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))

    inspector = inspect(db.engine)
    for table in test_tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "user_id" in columns


def test_migration_00212c18b0ac_idempotency(test_db):
    """Test that migration 00212c18b0ac can handle existing columns and indexes."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS transaction_test (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER,
                    class_id VARCHAR(64),
                    amount INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_transaction_test_class_id
                ON transaction_test (class_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_transaction_test_student_class_id
                ON transaction_test (student_id, class_id)
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("transaction_test")]
    assert "class_id" in columns

    indexes = [idx["name"] for idx in inspector.get_indexes("transaction_test")]
    assert "ix_transaction_test_class_id" in indexes
    assert "ix_transaction_test_student_class_id" in indexes


def test_helper_functions_dont_crash_with_existing_schema(test_db):
    """Test that helper functions handle existing schema elements gracefully."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS parent_table (
                    id INTEGER PRIMARY KEY
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS child_table (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER REFERENCES parent_table(id)
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("child_table")]
    assert "parent_id" in columns

    foreign_keys = inspector.get_foreign_keys("child_table")
    assert len(foreign_keys) >= 0


def test_nullable_column_check(test_db):
    """Test checking if a column is nullable."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_nullable (
                    id INTEGER PRIMARY KEY,
                    nullable_col INTEGER,
                    not_null_col INTEGER NOT NULL
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = inspector.get_columns("test_nullable")

    nullable_col = next((col for col in columns if col["name"] == "nullable_col"), None)
    not_null_col = next((col for col in columns if col["name"] == "not_null_col"), None)

    assert nullable_col is not None
    assert nullable_col.get("nullable", True) is True

    assert not_null_col is not None
    assert not_null_col.get("nullable") is False
