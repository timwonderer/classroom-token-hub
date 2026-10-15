"""Add marketing_badge to insurance_policies (DOM-POL-001A §D)

An optional, teacher-chosen presentation flair shown to students in the insurance
marketplace (ported from v1). Presentation metadata only: it never enters claim,
premium or coverage evaluation. FEAT-CLASS-003 restricts it to the fixed catalog in
``app/services/insurance_policy_service.MARKETING_BADGES``; the column itself is a
nullable string so adding a catalog entry needs no migration.

Revision ID: e5b7c9d1f3a4
Revises: 6a01dc7a606b
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5b7c9d1f3a4'
down_revision = '6a01dc7a606b'
branch_labels = None
depends_on = None


TABLE = 'insurance_policies'
COLUMN = 'marketing_badge'


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  Table '{TABLE}' does not exist, skipping...")
        return
    if not column_exists(TABLE, COLUMN):
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=40), nullable=True))
        print(f"✅ Added {COLUMN} to {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' already exists on '{TABLE}', skipping...")


def downgrade():
    if not table_exists(TABLE):
        return
    if column_exists(TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
        print(f"❌ Dropped {COLUMN} from {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' does not exist on '{TABLE}', skipping...")
