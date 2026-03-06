"""Add join_code to redemption_audit_logs

Revision ID: 7c5e1a2b9d4f
Revises: 5b6c7d8e9f0a
Create Date: 2026-02-28 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c5e1a2b9d4f'
down_revision = '5b6c7d8e9f0a'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    table_name = 'redemption_audit_logs'
    index_name = 'ix_redemption_audit_logs_join_code'

    if not table_exists(table_name):
        return

    if not column_exists(table_name, 'join_code'):
        op.add_column(table_name, sa.Column('join_code', sa.String(length=20), nullable=True))

    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, ['join_code'], unique=False)


def downgrade():
    table_name = 'redemption_audit_logs'
    index_name = 'ix_redemption_audit_logs_join_code'

    if not table_exists(table_name):
        return

    if index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)

    if column_exists(table_name, 'join_code'):
        op.drop_column(table_name, 'join_code')
