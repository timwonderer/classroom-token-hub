"""Add coverage period fields to rent_payments for pre-paid system

Revision ID: 0266e565c900
Revises: w2x3y4z5a6b7
Create Date: 2026-02-03 22:00:00.000000

This migration adds coverage_month and coverage_year fields to track which
period a rent payment covers, enabling a pre-paid rent system where:
- Payment for January can be made in December
- Students retain privileges until the next due date
- Back rent accumulates for missed payments
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '0266e565c900'
down_revision = 'w2x3y4z5a6b7'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Add coverage_month and coverage_year to rent_payments table."""
    # Add coverage fields as nullable first
    if not column_exists('rent_payments', 'coverage_month'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('coverage_month', sa.Integer(), nullable=True))
        print("✅ Added coverage_month column to rent_payments")
    else:
        print("⚠️  Column 'coverage_month' already exists on 'rent_payments', skipping...")
    
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
    """Remove coverage_month and coverage_year from rent_payments table."""
    if column_exists('rent_payments', 'coverage_month'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.drop_column('coverage_month')
        print("✅ Removed coverage_month column from rent_payments")
    
    if column_exists('rent_payments', 'coverage_year'):
        with op.batch_alter_table('rent_payments', schema=None) as batch_op:
            batch_op.drop_column('coverage_year')
        print("✅ Removed coverage_year column from rent_payments")
