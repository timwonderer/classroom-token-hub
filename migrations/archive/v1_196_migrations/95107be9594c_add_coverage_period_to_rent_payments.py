"""Add coverage period fields to rent_payments for pre-paid system

Revision ID: 95107be9594c
Revises: abc123def456
Create Date: 2026-02-04 10:00:00.000000

This migration adds coverage_month and coverage_year fields to track which
period a rent payment covers, enabling a pre-paid rent system where:
- Payment for January covers the student until the February due date
- Students retain privileges until the next due date
- Back rent accumulates for missed payments
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95107be9594c'
down_revision = 'abc123def456'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
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
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign keys for a column (for downgrade without hardcoded names)."""
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
# MIGRATION OPERATIONS
# ============================================================================

def upgrade():
    """Add coverage_month and coverage_year columns to rent_payments table.

    These columns track which month/year a rent payment covers (not when it was paid).
    This enables pre-paid rent where January payment covers February.
    """
    # Add coverage_month column
    if not column_exists('rent_payments', 'coverage_month'):
        print("⚙️  Adding coverage_month column to rent_payments...")
        op.add_column('rent_payments', sa.Column('coverage_month', sa.Integer(), nullable=True))
        print("✅ Added coverage_month column")
    else:
        print("⚠️  Column 'coverage_month' already exists on 'rent_payments', skipping...")

    # Add coverage_year column
    if not column_exists('rent_payments', 'coverage_year'):
        print("⚙️  Adding coverage_year column to rent_payments...")
        op.add_column('rent_payments', sa.Column('coverage_year', sa.Integer(), nullable=True))
        print("✅ Added coverage_year column")
    else:
        print("⚠️  Column 'coverage_year' already exists on 'rent_payments', skipping...")

    # Backfill coverage fields for existing payments
    # Assumption: For pre-paid system, payment made in month M covers M+1
    # For existing data, we'll assume payment covers the same month it was paid
    if column_exists('rent_payments', 'coverage_month') and column_exists('rent_payments', 'coverage_year'):
        print("⚙️  Backfilling coverage fields for existing rent payments...")
        op.execute("""
            UPDATE rent_payments
            SET
                coverage_month = period_month,
                coverage_year = period_year
            WHERE coverage_month IS NULL OR coverage_year IS NULL
        """)
        print("✅ Backfilled coverage fields")

        # Make columns non-nullable after backfill
        if column_exists('rent_payments', 'coverage_month'):
            print("⚙️  Setting coverage_month to NOT NULL...")
            op.alter_column('rent_payments', 'coverage_month', nullable=False)
            print("✅ Set coverage_month to NOT NULL")

        if column_exists('rent_payments', 'coverage_year'):
            print("⚙️  Setting coverage_year to NOT NULL...")
            op.alter_column('rent_payments', 'coverage_year', nullable=False)
            print("✅ Set coverage_year to NOT NULL")


def downgrade():
    """Remove coverage_month and coverage_year columns from rent_payments table."""
    # Drop coverage_year column
    if column_exists('rent_payments', 'coverage_year'):
        print("⚙️  Dropping coverage_year column from rent_payments...")
        op.drop_column('rent_payments', 'coverage_year')
        print("✅ Dropped coverage_year column")
    else:
        print("⚠️  Column 'coverage_year' does not exist on 'rent_payments', skipping...")

    # Drop coverage_month column
    if column_exists('rent_payments', 'coverage_month'):
        print("⚙️  Dropping coverage_month column from rent_payments...")
        op.drop_column('rent_payments', 'coverage_month')
        print("✅ Dropped coverage_month column")
    else:
        print("⚠️  Column 'coverage_month' does not exist on 'rent_payments', skipping...")
