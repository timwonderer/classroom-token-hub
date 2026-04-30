"""Add seat_id to transaction and balance_cache with legacy backfill.

Revision ID: j1k2l3m4n5o6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j1k2l3m4n5o6"
down_revision = "f1a2b3c4d5e6"
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

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def unique_constraint_exists(table_name, uq_name):
    """Check if a unique constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        uqs = [uq['name'] for uq in inspector.get_unique_constraints(table_name)]
        return uq_name in uqs
    except Exception:
        return False

def upgrade():
    with op.batch_alter_table("transaction", schema=None) as batch_op:
        if not column_exists("transaction", "seat_id"):
            batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        if not foreign_key_exists("transaction", "fk_transaction_seat_id"):
            try:
                batch_op.create_foreign_key("fk_transaction_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
            except Exception:
                pass
        if not index_exists("transaction", "ix_transaction_seat_id"):
            batch_op.create_index("ix_transaction_seat_id", ["seat_id"], unique=False)
        if not index_exists("transaction", "ix_transaction_seat_ledger"):
            batch_op.create_index(
                "ix_transaction_seat_ledger",
                ["join_code", "seat_id", "status", "account_type"],
                unique=False,
            )

    if column_exists("transaction", "seat_id") and table_exists("seats"):
        op.execute(
            sa.text(
                """
                UPDATE "transaction"
                SET seat_id = (
                    SELECT s.id
                    FROM seats s
                    WHERE s.student_id = "transaction".student_id
                      AND s.join_code = "transaction".join_code
                    LIMIT 1
                )
                WHERE seat_id IS NULL
                  AND join_code IS NOT NULL
                """
            )
        )

    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        if not column_exists("balance_cache", "seat_id"):
            batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        if not foreign_key_exists("balance_cache", "fk_balance_cache_seat_id"):
            try:
                batch_op.create_foreign_key("fk_balance_cache_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
            except Exception:
                pass
        if not index_exists("balance_cache", "ix_balance_cache_seat_id"):
            batch_op.create_index("ix_balance_cache_seat_id", ["seat_id"], unique=False)

    if column_exists("balance_cache", "seat_id") and table_exists("seats"):
        op.execute(
            sa.text(
                """
                UPDATE balance_cache
                SET seat_id = (
                    SELECT s.id
                    FROM seats s
                    WHERE s.student_id = balance_cache.student_id
                      AND s.join_code = balance_cache.join_code
                    LIMIT 1
                )
                WHERE seat_id IS NULL
                """
            )
        )

    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        if not unique_constraint_exists("balance_cache", "uq_balance_cache_seat_scope"):
             try:
                batch_op.create_unique_constraint("uq_balance_cache_seat_scope", ["join_code", "seat_id"])
             except Exception:
                pass


def downgrade():
    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        if unique_constraint_exists("balance_cache", "uq_balance_cache_seat_scope"):
            batch_op.drop_constraint("uq_balance_cache_seat_scope", type_="unique")
        if index_exists("balance_cache", "ix_balance_cache_seat_id"):
            batch_op.drop_index("ix_balance_cache_seat_id")
        if foreign_key_exists("balance_cache", "fk_balance_cache_seat_id"):
            batch_op.drop_constraint("fk_balance_cache_seat_id", type_="foreignkey")
        if column_exists("balance_cache", "seat_id"):
            batch_op.drop_column("seat_id")

    with op.batch_alter_table("transaction", schema=None) as batch_op:
        if index_exists("transaction", "ix_transaction_seat_ledger"):
            batch_op.drop_index("ix_transaction_seat_ledger")
        if index_exists("transaction", "ix_transaction_seat_id"):
            batch_op.drop_index("ix_transaction_seat_id")
        if foreign_key_exists("transaction", "fk_transaction_seat_id"):
            batch_op.drop_constraint("fk_transaction_seat_id", type_="foreignkey")
        if column_exists("transaction", "seat_id"):
            batch_op.drop_column("seat_id")
