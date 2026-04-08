"""Add transfer_correlation_id to transactions

Revision ID: 9845e9a9baca
Revises: b5c6d7e8f9g0
Create Date: 2026-04-07 00:00:00.000000

Adds transfer_correlation_id (String(36)) to the transaction table.

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
revision = '9845e9a9baca'
down_revision = 'b5c6d7e8f9g0'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED — per SOP-DB-009/011)
# ============================================================================

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


def get_foreign_keys_by_column(table_name, column_name):
    """Get FK constraints for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if not column_exists('transaction', 'transfer_correlation_id'):
        op.add_column(
            'transaction',
            sa.Column('transfer_correlation_id', sa.String(36), nullable=True),
        )
        print("✅ Added transfer_correlation_id column to transaction")
    else:
        print("⚠️  Column 'transfer_correlation_id' already exists on 'transaction', skipping")

    if not index_exists('transaction', 'ix_transaction_transfer_correlation_id'):
        op.create_index(
            'ix_transaction_transfer_correlation_id',
            'transaction',
            ['transfer_correlation_id'],
        )
        print("✅ Created index ix_transaction_transfer_correlation_id")
    else:
        print("⚠️  Index 'ix_transaction_transfer_correlation_id' already exists, skipping")


def downgrade():
    if index_exists('transaction', 'ix_transaction_transfer_correlation_id'):
        op.drop_index('ix_transaction_transfer_correlation_id', table_name='transaction')
        print("❌ Dropped index ix_transaction_transfer_correlation_id")

    if column_exists('transaction', 'transfer_correlation_id'):
        op.drop_column('transaction', 'transfer_correlation_id')
        print("❌ Dropped transfer_correlation_id column from transaction")
