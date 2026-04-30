"""Merge reason-code and join-code migration heads

Revision ID: 6c7d8e9f0a1b
Revises: 3d54e2e343df, 5b6c7d8e9f0a
Create Date: 2026-02-28 14:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c7d8e9f0a1b'
down_revision = ('3d54e2e343df', '5b6c7d8e9f0a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
