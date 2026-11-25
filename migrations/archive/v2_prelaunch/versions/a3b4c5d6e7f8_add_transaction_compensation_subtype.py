"""record the business subtype of a compensating ledger transaction

FEAT-LED-002 §III.2.1 requires a reversal to persist ``REVERSAL`` as its
transaction type, never the business reason it was raised for. The reason still
has to survive — an issue reversal and an issue compensating entry are answered
differently by Operations — so it moves to its own column instead of occupying
``type``.

Revision ID: a3b4c5d6e7f8
Revises: f1a2c3d4e5b6
"""

from alembic import op
import sqlalchemy as sa


revision = "a3b4c5d6e7f8"
down_revision = "f1a2c3d4e5b6"
branch_labels = None
depends_on = None

LEGACY_COMPENSATION_TYPES = ("refund", "issue_reversal", "issue_compensation")


def table_exists(table_name):
    """Check if a table exists."""
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    inspector = sa.inspect(op.get_bind())
    try:
        return column_name in [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    inspector = sa.inspect(op.get_bind())
    try:
        return index_name in [idx["name"] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def upgrade():
    if not table_exists("ledger_transaction"):
        print("⚠️  ledger_transaction does not exist, skipping...")
        return

    if not column_exists("ledger_transaction", "compensation_subtype"):
        op.add_column(
            "ledger_transaction",
            sa.Column("compensation_subtype", sa.String(length=50), nullable=True),
        )
        print("✅ Added compensation_subtype to ledger_transaction")
    else:
        print("⚠️  Column 'compensation_subtype' already exists, skipping...")

    if not index_exists("ledger_transaction", "ix_ledger_transaction_compensation_subtype"):
        op.create_index(
            "ix_ledger_transaction_compensation_subtype",
            "ledger_transaction",
            ["compensation_subtype"],
        )

    # Rows already written by reverse_transaction carry the business reason in
    # `type`. Move it to the new column and restate `type` as REVERSAL so a
    # rebuild from history reads one vocabulary rather than two. Only rows that
    # a reversal actually produced are touched: a compensating row is the one
    # that names the transaction it counteracts.
    values = ", ".join(f"'{value}'" for value in LEGACY_COMPENSATION_TYPES)
    op.execute(
        sa.text(
            "UPDATE ledger_transaction SET compensation_subtype = type, "
            "type = 'REVERSAL' "
            f"WHERE type IN ({values}) AND original_transaction_id IS NOT NULL"
        )
    )
    print("✅ Backfilled compensation_subtype from legacy compensation types")


def downgrade():
    if not table_exists("ledger_transaction"):
        print("⚠️  ledger_transaction does not exist, skipping...")
        return

    if column_exists("ledger_transaction", "compensation_subtype"):
        # Restore the pre-revision shape: the business reason goes back into
        # `type`. Rows with no recorded subtype fall back to 'refund', which is
        # the default reverse_transaction used before the split.
        op.execute(
            sa.text(
                "UPDATE ledger_transaction "
                "SET type = COALESCE(compensation_subtype, 'refund') "
                "WHERE type = 'REVERSAL'"
            )
        )
        if index_exists("ledger_transaction", "ix_ledger_transaction_compensation_subtype"):
            op.drop_index(
                "ix_ledger_transaction_compensation_subtype",
                table_name="ledger_transaction",
            )
        op.drop_column("ledger_transaction", "compensation_subtype")
        print("❌ Dropped compensation_subtype from ledger_transaction")
    else:
        print("⚠️  Column 'compensation_subtype' does not exist, skipping...")
