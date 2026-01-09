"""Merge migration heads

Revision ID: 90f5161ac055
Revises: 49775b7f5b89, 7ee026ad3ad8
Create Date: 2026-01-09 05:41:34.714375

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90f5161ac055'
down_revision = ('49775b7f5b89', '7ee026ad3ad8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
