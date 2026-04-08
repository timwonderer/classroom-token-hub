"""Add transfer_correlation_id to transactions

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2026-04-07 00:00:00.000000

Adds transfer_correlation_id (String(36)) to the transactions table.

Purpose: Links the two legs of a transfer pair (debit + credit) via a shared
UUID generated once at the call site and set on both Transaction rows. Enables
the invariant system to perform true pair-by-pair integrity checks
(COUNT(*) == 2, SUM(amount_cents) == 0) instead of relying on description
string matching.

Backward compatibility:
  - Nullable. Existing rows are left as NULL — the invariant only enforces
    strict pair rules for rows where transfer_correlation_id IS NOT NULL.
  - No data backfill. All new transfers set this field going forward.

See: app/invariants/money_supply.py (pair-based transfer zero-sum check).
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


# ── Idempotency helpers ──────────────────────────────────────────────────────

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


# ── Upgrade ──────────────────────────────────────────────────────────────────

def upgrade():
    if not column_exists('transactions', 'transfer_correlation_id'):
        op.add_column(
            'transactions',
            sa.Column('transfer_correlation_id', sa.String(36), nullable=True),
        )
        print("✅ Added transfer_correlation_id column to transactions")
    else:
        print("⚠️  Column 'transfer_correlation_id' already exists on 'transactions', skipping")

    if not index_exists('transactions', 'ix_transactions_transfer_correlation_id'):
        op.create_index(
            'ix_transactions_transfer_correlation_id',
            'transactions',
            ['transfer_correlation_id'],
        )
        print("✅ Created index ix_transactions_transfer_correlation_id")
    else:
        print("⚠️  Index 'ix_transactions_transfer_correlation_id' already exists, skipping")


# ── Downgrade ────────────────────────────────────────────────────────────────

def downgrade():
    if index_exists('transactions', 'ix_transactions_transfer_correlation_id'):
        op.drop_index('ix_transactions_transfer_correlation_id', table_name='transactions')
        print("❌ Dropped index ix_transactions_transfer_correlation_id")

    if column_exists('transactions', 'transfer_correlation_id'):
        op.drop_column('transactions', 'transfer_correlation_id')
        print("❌ Dropped transfer_correlation_id column from transactions")
