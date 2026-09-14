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


def upgrade():
    op.add_column('store_products', sa.Column('holding_limit', sa.Integer(), nullable=True))
    op.add_column(
        'store_products',
        sa.Column('direct_purchase_allowed', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_check_constraint(
        'ck_store_products_holding_limit_positive',
        'store_products',
        'holding_limit IS NULL OR holding_limit > 0',
    )


def downgrade():
    op.drop_constraint('ck_store_products_holding_limit_positive', 'store_products', type_='check')
    op.drop_column('store_products', 'direct_purchase_allowed')
    op.drop_column('store_products', 'holding_limit')
