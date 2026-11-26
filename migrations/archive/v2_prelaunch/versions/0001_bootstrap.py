"""bootstrap migration for v2 squash baseline

Revision ID: 0001
Revises: None
Create Date: 2026-04-30

Frozen baseline (2026-09-28, SOP-DB-001 §V.B "Standing remedy").
Until this date the bootstrap called ``metadata.create_all`` on the *live* ORM
models, so every model change retroactively changed the schema at step 0 of
the chain, underneath historical migrations written against something else.
It now executes ``migrations/baseline/0001_baseline_schema.sql``: the exact
schema the live-model bootstrap produced on 2026-09-28, captured with
``pg_dump --schema-only`` (session settings removed). A fresh chain reaches the
same head schema as before; a model changed after that date no longer reaches
back into step 0.

Only a database with no tables ever runs this. Every existing database
recorded revision 0001 long ago and never re-runs it.
"""
from pathlib import Path

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


BASELINE_SCHEMA = Path(__file__).resolve().parent.parent / "baseline" / "0001_baseline_schema.sql"


def upgrade():
    if table_exists("users"):
        print("⚠️  Baseline tables already present, skipping bootstrap")
        return
    # No parameters are passed, so the DDL is sent verbatim.
    op.get_bind().exec_driver_sql(BASELINE_SCHEMA.read_text())
    print("✅ Created frozen baseline schema")


def downgrade():
    # Bootstrap migration is intentionally non-destructive.
    pass
