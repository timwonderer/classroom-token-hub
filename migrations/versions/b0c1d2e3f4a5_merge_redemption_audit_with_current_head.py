"""Merge redemption audit migration with current head

Revision ID: b0c1d2e3f4a5
Revises: 2765a36d76ff, a9b8c7d6e5f4
Create Date: 2026-02-11 12:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0c1d2e3f4a5'
down_revision = ('2765a36d76ff', 'a9b8c7d6e5f4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # IRREVERSIBLE: append-only audit chain merge marker.
    pass
