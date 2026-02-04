"""Add coverage period fields to rent_payments for pre-paid system

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2026-02-04 00:00:00.000000

This migration adds coverage_month and coverage_year fields to track which
period a rent payment covers, enabling a pre-paid rent system where:
- Payment for January covers the student until the February due date
- Students retain privileges until the next due date
- Back rent accumulates for missed payments
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
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


def constraint_exists(table_name, constraint_name):
    """Check if a unique constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign key constraints that reference a specific column."""
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
    # Add coverage_month as nullable first
    if not column_exists('rent_payments', 'coverage_month'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('coverage_month', sa.Integer(), nullable=True))
        print("✅ Added coverage_month column to rent_payments")
    else:
        print("⚠️  Column 'coverage_month' already exists on 'rent_payments', skipping...")

    # Add coverage_year as nullable first
    if not column_exists('rent_payments', 'coverage_year'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('coverage_year', sa.Integer(), nullable=True))
        print("✅ Added coverage_year column to rent_payments")
    else:
        print("⚠️  Column 'coverage_year' already exists on 'rent_payments', skipping...")

    # Backfill existing records: assume payment covers the month/year it was made
    # This maintains current behavior for existing payments
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE rent_payments
        SET coverage_month = period_month,
            coverage_year = period_year
        WHERE coverage_month IS NULL OR coverage_year IS NULL
    """))
    print("✅ Backfilled coverage fields for existing rent_payments")

    # Now make the columns NOT NULL since all records have values
    if column_exists('rent_payments', 'coverage_month'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.alter_column('coverage_month', nullable=False)
        print("✅ Made coverage_month NOT NULL")

    if column_exists('rent_payments', 'coverage_year'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.alter_column('coverage_year', nullable=False)
        print("✅ Made coverage_year NOT NULL")


def downgrade():
    if column_exists('rent_payments', 'coverage_year'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.drop_column('coverage_year')
        print("❌ Dropped coverage_year from rent_payments")
    else:
        print("⚠️  Column 'coverage_year' does not exist on 'rent_payments', skipping...")

    if column_exists('rent_payments', 'coverage_month'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.drop_column('coverage_month')
        print("❌ Dropped coverage_month from rent_payments")
    else:
        print("⚠️  Column 'coverage_month' does not exist on 'rent_payments', skipping...")
