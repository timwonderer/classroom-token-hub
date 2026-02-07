"""add_rent_item_types_and_allocation

Revision ID: c2d9cf951ddc
Revises: f3fe270c6f0e
Create Date: 2026-02-06 07:04:32.975418

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
revision = 'c2d9cf951ddc'
down_revision = 'f3fe270c6f0e'
branch_labels = None
depends_on = None


def upgrade():
    # Add rent_item_type to rent_items (default 'privilege' for backward compat)
    if not column_exists('rent_items', 'rent_item_type'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('rent_item_type', sa.String(length=20), nullable=False, server_default='privilege'))

    if not column_exists('rent_items', 'use_limit'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('use_limit', sa.Integer(), nullable=True))

    if not column_exists('rent_items', 'hall_pass_count'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('hall_pass_count', sa.Integer(), nullable=True))

    if not column_exists('store_items', 'is_rent_linked'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_rent_linked', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))

    if not column_exists('student_blocks', 'rent_hall_passes'):
        with op.batch_alter_table('student_blocks', schema=None) as batch_op:
            batch_op.add_column(sa.Column('rent_hall_passes', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    if column_exists('student_blocks', 'rent_hall_passes'):
        with op.batch_alter_table('student_blocks', schema=None) as batch_op:
            batch_op.drop_column('rent_hall_passes')

    if column_exists('store_items', 'is_rent_linked'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.drop_column('is_rent_linked')

    if column_exists('rent_items', 'hall_pass_count'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.drop_column('hall_pass_count')

    if column_exists('rent_items', 'use_limit'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.drop_column('use_limit')

    if column_exists('rent_items', 'rent_item_type'):
        with op.batch_alter_table('rent_items', schema=None) as batch_op:
            batch_op.drop_column('rent_item_type')
