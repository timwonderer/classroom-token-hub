"""Add rent_amount_snapshot to rent_payments

Revision ID: a8b9c0d1e2f3
Revises: b1c2d3e4f5a6
Create Date: 2026-04-17 06:30:00.000000

Adds rent_amount_snapshot (nullable Decimal) to rent_payments so that
_get_locked_rent_amount_for_join_code_cycle can return the configured rent
amount at the time of the first payment, rather than the installment
amount_paid.

Without this, the first *partial* payment (e.g. $200 of a $570 rent) was
used as the class-wide "locked rate", making subsequent partial payments
appear fully paid and silently rejected.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8b9c0d1e2f3'
down_revision = 'b1c2d3e4f5a6'
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


# ============================================================================
# MIGRATION OPERATIONS
# ============================================================================

def upgrade():
    """Add rent_amount_snapshot column to rent_payments table.

    The column is nullable so existing rows are unaffected. New payments
    populate it with settings.rent_amount at creation time so that partial
    installments no longer corrupt the class-wide rate lock.
    """
    if not column_exists('rent_payments', 'rent_amount_snapshot'):
        print("⚙️  Adding rent_amount_snapshot column to rent_payments...")
        op.add_column(
            'rent_payments',
            sa.Column(
                'rent_amount_snapshot',
                sa.Numeric(precision=12, scale=2),
                nullable=True,
            ),
        )
        print("✅ Added rent_amount_snapshot column")
    else:
        print("⚠️  Column 'rent_amount_snapshot' already exists on 'rent_payments', skipping...")


def downgrade():
    """Remove rent_amount_snapshot column from rent_payments table."""
    if column_exists('rent_payments', 'rent_amount_snapshot'):
        print("⚙️  Dropping rent_amount_snapshot column from rent_payments...")
        op.drop_column('rent_payments', 'rent_amount_snapshot')
        print("✅ Dropped rent_amount_snapshot column")
    else:
        print("⚠️  Column 'rent_amount_snapshot' does not exist on 'rent_payments', skipping...")
