"""add cwi warning bypass flags

Revision ID: 3f4a5b6c7d8e
Revises: k1l2m3n4o5p6
Create Date: 2026-03-19 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '3f4a5b6c7d8e'
down_revision = 'k1l2m3n4o5p6'
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
    if table_exists('store_items') and not column_exists('store_items', 'bypass_cwi_warnings'):
        op.add_column('store_items', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column('store_items', 'bypass_cwi_warnings', server_default=None)

    if table_exists('rent_settings') and not column_exists('rent_settings', 'bypass_cwi_warnings'):
        op.add_column('rent_settings', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column('rent_settings', 'bypass_cwi_warnings', server_default=None)

    if table_exists('insurance_policies') and not column_exists('insurance_policies', 'bypass_cwi_warnings'):
        op.add_column('insurance_policies', sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column('insurance_policies', 'bypass_cwi_warnings', server_default=None)


def downgrade():
    if table_exists('insurance_policies') and column_exists('insurance_policies', 'bypass_cwi_warnings'):
        op.drop_column('insurance_policies', 'bypass_cwi_warnings')
    if table_exists('rent_settings') and column_exists('rent_settings', 'bypass_cwi_warnings'):
        op.drop_column('rent_settings', 'bypass_cwi_warnings')
    if table_exists('store_items') and column_exists('store_items', 'bypass_cwi_warnings'):
        op.drop_column('store_items', 'bypass_cwi_warnings')
