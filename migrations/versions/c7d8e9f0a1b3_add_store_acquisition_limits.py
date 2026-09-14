"""Add source-independent Store acquisition fields.

Revision ID: c7d8e9f0a1b3
Revises: f1a9c3e60b72
"""
from alembic import op
import sqlalchemy as sa

revision = 'c7d8e9f0a1b3'
down_revision = 'f1a9c3e60b72'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    """Check if a named check constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        names = [c['name'] for c in inspector.get_check_constraints(table_name)]
        return constraint_name in names
    except Exception:
        return False


def upgrade():
    if not column_exists('store_products', 'holding_limit'):
        op.add_column('store_products', sa.Column('holding_limit', sa.Integer(), nullable=True))
    if not column_exists('store_products', 'direct_purchase_allowed'):
        op.add_column(
            'store_products',
            sa.Column('direct_purchase_allowed', sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if not constraint_exists('store_products', 'ck_store_products_holding_limit_positive'):
        op.create_check_constraint(
            'ck_store_products_holding_limit_positive',
            'store_products',
            'holding_limit IS NULL OR holding_limit > 0',
        )


def downgrade():
    if constraint_exists('store_products', 'ck_store_products_holding_limit_positive'):
        op.drop_constraint('ck_store_products_holding_limit_positive', 'store_products', type_='check')
    if column_exists('store_products', 'direct_purchase_allowed'):
        op.drop_column('store_products', 'direct_purchase_allowed')
    if column_exists('store_products', 'holding_limit'):
        op.drop_column('store_products', 'holding_limit')
