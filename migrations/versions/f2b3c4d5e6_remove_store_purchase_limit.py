"""Remove obsolete per-student purchase limit.

Revision ID: f2b3c4d5e6
Revises: e0f1a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa

revision = 'f2b3c4d5e6'
down_revision = 'e0f1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('store_products', 'limit_per_student')


def downgrade():
    op.add_column('store_products', sa.Column('limit_per_student', sa.Integer(), nullable=True))
