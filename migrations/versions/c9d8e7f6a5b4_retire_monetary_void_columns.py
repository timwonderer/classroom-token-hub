"""Retire the legacy monetary-transaction void columns.

Monetary corrections are append-only reversals. ``is_void`` and ``voided_at``
allowed an unsettled monetary debit to disappear without a compensating ledger
fact, contradicting SPEC-OPS-001 and the ledger reconstruction invariant.
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d8e7f6a5b4"
down_revision = "b7c41e9a2f30"
branch_labels = None
depends_on = None


def table_exists(table_name):
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def column_exists(table_name, column_name):
    if not table_exists(table_name):
        return False
    try:
        return column_name in {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
        }
    except Exception:
        return False


def index_exists(table_name, index_name):
    if not table_exists(table_name):
        return False
    try:
        return index_name in {
            index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    if not table_exists(table_name):
        return False
    try:
        return fk_name in {
            fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        }
    except Exception:
        return False


def upgrade():
    if column_exists("ledger_transaction", "is_void"):
        op.drop_column("ledger_transaction", "is_void")
    if column_exists("ledger_transaction", "voided_at"):
        op.drop_column("ledger_transaction", "voided_at")


def downgrade():
    if table_exists("ledger_transaction") and not column_exists("ledger_transaction", "voided_at"):
        op.add_column(
            "ledger_transaction",
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        )
    if table_exists("ledger_transaction") and not column_exists("ledger_transaction", "is_void"):
        op.add_column(
            "ledger_transaction",
            sa.Column("is_void", sa.Boolean(), nullable=True, server_default=sa.false()),
        )
