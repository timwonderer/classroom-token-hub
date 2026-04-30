"""Add transaction idempotency key

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-03-30 20:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
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
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if table_exists("transaction") and not column_exists("transaction", "idempotency_key"):
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))

    if table_exists("transaction") and not index_exists("transaction", "ix_transaction_idempotency_key"):
        op.create_index("ix_transaction_idempotency_key", "transaction", ["idempotency_key"], unique=True)


def downgrade():
    if table_exists("transaction") and index_exists("transaction", "ix_transaction_idempotency_key"):
        op.drop_index("ix_transaction_idempotency_key", table_name="transaction")

    if table_exists("transaction") and column_exists("transaction", "idempotency_key"):
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.drop_column("idempotency_key")
