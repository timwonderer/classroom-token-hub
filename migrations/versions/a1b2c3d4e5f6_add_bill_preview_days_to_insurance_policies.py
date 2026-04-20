"""Add bill_preview_days to insurance_policies

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2026-04-20 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    if not column_exists('insurance_policies', 'bill_preview_days'):
        op.add_column(
            'insurance_policies',
            sa.Column('bill_preview_days', sa.Integer(), nullable=False, server_default='5'),
        )
        print("✅ Added bill_preview_days to insurance_policies")
    else:
        print("⚠️  bill_preview_days already exists on insurance_policies, skipping")


def downgrade():
    if column_exists('insurance_policies', 'bill_preview_days'):
        op.drop_column('insurance_policies', 'bill_preview_days')
        print("❌ Dropped bill_preview_days from insurance_policies")
    else:
        print("⚠️  bill_preview_days does not exist on insurance_policies, skipping")
