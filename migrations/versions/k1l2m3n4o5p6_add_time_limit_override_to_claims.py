"""Add time_limit_override_reason to insurance_claims

Revision ID: k1l2m3n4o5p6
Revises: j2k3l4m5n6o7
Create Date: 2026-03-19 00:00:00.000000

Adds a time_limit_override_reason column to insurance_claims so that teachers
can document why they approved a claim that was filed outside the policy's
claim time limit.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'k1l2m3n4o5p6'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if table_exists('insurance_claims') and not column_exists('insurance_claims', 'time_limit_override_reason'):
        op.add_column(
            'insurance_claims',
            sa.Column('time_limit_override_reason', sa.Text(), nullable=True),
        )


def downgrade():
    if table_exists('insurance_claims') and column_exists('insurance_claims', 'time_limit_override_reason'):
        op.drop_column('insurance_claims', 'time_limit_override_reason')
