"""Rename legacy ledger tables to canonical Wave 5 names.

Revision ID: b1c2d3e4f5a6
Revises: a91cf11e8b2d
Create Date: 2026-05-25

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a91cf11e8b2d"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    if table_exists("transaction") and not table_exists("ledger_transaction"):
        op.rename_table("transaction", "ledger_transaction")

    if table_exists("balance_cache") and not table_exists("ledger_balance_snapshot"):
        op.rename_table("balance_cache", "ledger_balance_snapshot")


def downgrade():
    if table_exists("ledger_balance_snapshot") and not table_exists("balance_cache"):
        op.rename_table("ledger_balance_snapshot", "balance_cache")

    if table_exists("ledger_transaction") and not table_exists("transaction"):
        op.rename_table("ledger_transaction", "transaction")
