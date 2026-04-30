"""Merge remaining v2 heads.

Revision ID: e8f1a2b3c4d5
Revises: 3d3898de8611, a7477b6ca18f, d1f2e3c4b5a6
Create Date: 2026-03-08 13:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f1a2b3c4d5'
down_revision = ('3d3898de8611', 'a7477b6ca18f', 'd1f2e3c4b5a6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
