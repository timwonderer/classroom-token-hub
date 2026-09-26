"""bootstrap migration for v2 squash baseline

Revision ID: 0001
Revises: None
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c["name"] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def _create_tables_if_missing(metadata, bind):
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    # Avoid metadata.sorted_tables here because the bootstrap metadata contains
    # intentional FK cycles that produce noisy SAWarnings during test setup.
    target_tables = [table for table in metadata.tables.values() if table.name not in existing]
    if target_tables:
        metadata.create_all(bind=bind, tables=target_tables, checkfirst=True)


def _create_retired_baseline_tables(bind):
    """Recreate baseline tables that the ORM no longer defines.

    This migration builds the baseline by materializing *today's* ORM metadata,
    which means deleting a model retroactively removes a table that existed at
    baseline time — and later migrations in the chain still legitimately
    reference it. A fresh database then fails on a foreign key to a table that
    every already-migrated database has.

    So tables that were part of the baseline but have since left the ORM are
    recreated here, in the minimal shape the rest of the chain needs (a primary
    key to point foreign keys at; every later column operation on them is
    existence-guarded). The migration that legitimately removes such a table
    still runs later and still drops it — this only restores the precondition
    those migrations were written against.

    ``store_items``: removed from the ORM when the store's two-table split was
    consolidated into the single versioned ``store_products`` table
    (b7c41e9a2f30). Referenced by ``store_purchases`` (0009) and
    ``entitlements`` (1761e2187234), both of which are dropped further along.
    """
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'store_items' not in existing:
        op.create_table(
            'store_items',
            sa.Column('id', sa.Integer(), primary_key=True),
        )

    # The mirror-image problem: a table whose *shape* changed later in the chain
    # arrives here already carrying its final columns, so the migrations that
    # own its history find it present and skip, or find their columns missing
    # and fail. Dropping it hands its lifecycle back to the migrations that
    # actually describe it — e13a59b6aa6b creates store_products, 0009 creates
    # store_item_visibility, and b7c41e9a2f30 rewrites both into the shape the
    # ORM declares.
    #
    # Only ever reached on a database that has not been migrated yet, and the
    # emptiness check makes that structural rather than assumed.
    for table_name in ('store_products', 'store_item_visibility'):
        if table_name not in existing:
            continue
        has_rows = bind.execute(
            sa.text(f'SELECT 1 FROM {table_name} LIMIT 1')  # noqa: S608 — fixed literals
        ).first() is not None
        if has_rows:
            raise RuntimeError(
                f"Bootstrap wants to hand {table_name} back to the migrations that "
                f"own it, but it already holds rows. Refusing to drop data."
            )
        op.drop_table(table_name)


def upgrade():
    bind = op.get_bind()

    # Section A: legacy/transitional tables
    import app.models as legacy_models
    _create_tables_if_missing(legacy_models.db.Model.metadata, bind)

    # Section B: canonical DOM-CORE-002 tables now live in the active ORM layer.
    from app import models as canonical_models
    _create_tables_if_missing(canonical_models.db.Model.metadata, bind)

    # Section C: baseline tables the ORM has since dropped.
    _create_retired_baseline_tables(bind)


def downgrade():
    # Bootstrap migration is intentionally non-destructive.
    pass
