"""Add prospective Store activation date.

Revision ID: f3a4b5c6d7e8
Revises: f2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a4b5c6d7e8'
down_revision = 'f2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('store_products', sa.Column('activation_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('store_products', 'activation_at')
