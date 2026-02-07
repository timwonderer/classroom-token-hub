"""add_uses_remaining_to_student_item

Revision ID: 9b0e06f05fcf
Revises: c2d9cf951ddc
Create Date: 2026-02-06 07:15:41.994556

"""
from alembic import op
import sqlalchemy as sa


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.

    Use this instead of hardcoding FK names in downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = '9b0e06f05fcf'
down_revision = 'c2d9cf951ddc'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('student_items') and not column_exists('student_items', 'uses_remaining'):
        with op.batch_alter_table('student_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('uses_remaining', sa.Integer(), nullable=True))


def downgrade():
    if table_exists('student_items') and column_exists('student_items', 'uses_remaining'):
        with op.batch_alter_table('student_items', schema=None) as batch_op:
            batch_op.drop_column('uses_remaining')
