"""add hall_pass_verify_token to admins

Revision ID: a1b2c3d4e5f0
Revises: 96c2fc5e680c
Create Date: 2026-02-24 03:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f0'
down_revision = '96c2fc5e680c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hall_pass_verify_token', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_admins_hall_pass_verify_token', ['hall_pass_verify_token'], unique=True)


def downgrade():
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.drop_index('ix_admins_hall_pass_verify_token')
        batch_op.drop_column('hall_pass_verify_token')
