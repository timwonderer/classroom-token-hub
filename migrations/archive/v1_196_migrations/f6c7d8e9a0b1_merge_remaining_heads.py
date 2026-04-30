"""merge remaining migration heads

Revision ID: f6c7d8e9a0b1
Revises: 2095eed48a99, e9a1b2c3d4f5, f5bf397b9d45
Create Date: 2026-02-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6c7d8e9a0b1'
down_revision = ('2095eed48a99', 'e9a1b2c3d4f5', 'f5bf397b9d45')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
