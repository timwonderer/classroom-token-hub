"""Add Store essential overdue-purchase flag.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""
from alembic import op
import sqlalchemy as sa

revision = 'e0f1a2b3c4d5'
down_revision = 'd9e0f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('store_products', sa.Column('essential_when_overdue', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('store_products', 'essential_when_overdue')
