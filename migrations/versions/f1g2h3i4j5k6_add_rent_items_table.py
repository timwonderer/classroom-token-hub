"""Add RentItem table for itemized rent

Revision ID: f1g2h3i4j5k6
Revises: 3d66ea6ec5d3
Create Date: 2026-01-02 00:00:00.000000

This migration adds the rent_items table to support itemized rent feature.
Teachers can now specify what rent pays for (e.g., Desk, Chair, Locker) and
optionally make these items available as single-purchase alternatives in the
class store.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1g2h3i4j5k6'
down_revision = '3d66ea6ec5d3'
branch_labels = None
depends_on = None


def upgrade():
    # Create rent_items table
    op.create_table(
        'rent_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rent_setting_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_available_in_store', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('store_price', sa.Float(), nullable=True),
        sa.Column('store_item_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['rent_setting_id'], ['rent_settings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_item_id'], ['store_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for rent_items
    op.create_index('ix_rent_items_rent_setting_id', 'rent_items', ['rent_setting_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_rent_items_rent_setting_id', table_name='rent_items')

    # Drop table
    op.drop_table('rent_items')
