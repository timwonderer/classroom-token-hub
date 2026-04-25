"""Add purchase_duration to rent_items

Revision ID: h7i8j9k0l1m2
Revises: 6feaa660d6c3
Create Date: 2026-01-02 12:00:00.000000

This migration adds the purchase_duration field to rent_items table.
This allows teachers to specify whether store-purchased rent items are
'per_use' (buy each time) or 'per_period' (buy once per rent period).

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h7i8j9k0l1m2'
down_revision = '6feaa660d6c3'
branch_labels = None
depends_on = None

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # Add purchase_duration column to rent_items
    with op.batch_alter_table('rent_items', schema=None) as batch_op:
        if not column_exists('rent_items', 'purchase_duration'):
            batch_op.add_column(sa.Column('purchase_duration', sa.String(length=20), nullable=True, server_default='per_use'))


def downgrade():
    # Remove purchase_duration column from rent_items
    with op.batch_alter_table('rent_items', schema=None) as batch_op:
        batch_op.drop_column('purchase_duration')
