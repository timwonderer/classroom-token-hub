"""Add bypass_cwi_warnings to store_items, rent_settings, and insurance_policies

Revision ID: 2bde3e5f00ac
Revises: q9r0s1t2u3v4
Create Date: 2026-04-01 00:24:27.189189

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2bde3e5f00ac'
down_revision = 'q9r0s1t2u3v4'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


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
