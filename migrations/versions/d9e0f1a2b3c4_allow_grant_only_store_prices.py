"""Allow grant-only Store products to omit purchase pricing.

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b3
"""
from alembic import op


revision = 'd9e0f1a2b3c4'
down_revision = 'c7d8e9f0a1b3'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('store_products', 'price', nullable=True)


def downgrade():
    op.alter_column('store_products', 'price', nullable=False)
