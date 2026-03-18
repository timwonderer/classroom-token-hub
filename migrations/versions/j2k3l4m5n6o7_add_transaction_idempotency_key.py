"""add transaction idempotency key

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-03-17 22:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j2k3l4m5n6o7'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [column['name'] for column in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [index['name'] for index in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if not column_exists('transaction', 'idempotency_key'):
        op.add_column('transaction', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
    if not index_exists('transaction', 'ix_transaction_idempotency_key'):
        op.create_index('ix_transaction_idempotency_key', 'transaction', ['idempotency_key'], unique=True)


def downgrade():
    if index_exists('transaction', 'ix_transaction_idempotency_key'):
        op.drop_index('ix_transaction_idempotency_key', table_name='transaction')
    if column_exists('transaction', 'idempotency_key'):
        op.drop_column('transaction', 'idempotency_key')
