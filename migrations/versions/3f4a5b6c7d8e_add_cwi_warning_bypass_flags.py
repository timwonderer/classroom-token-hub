"""add cwi warning bypass flags

Revision ID: 3f4a5b6c7d8e
Revises: 6d78309c34c1
Create Date: 2026-03-19 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f4a5b6c7d8e'
down_revision = '6d78309c34c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('store_items', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('rent_settings', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('insurance_policies', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.alter_column('store_items', 'bypass_cwi_warnings', server_default=None)
    op.alter_column('rent_settings', 'bypass_cwi_warnings', server_default=None)
    op.alter_column('insurance_policies', 'bypass_cwi_warnings', server_default=None)


def downgrade():
    op.drop_column('insurance_policies', 'bypass_cwi_warnings')
    op.drop_column('rent_settings', 'bypass_cwi_warnings')
    op.drop_column('store_items', 'bypass_cwi_warnings')
