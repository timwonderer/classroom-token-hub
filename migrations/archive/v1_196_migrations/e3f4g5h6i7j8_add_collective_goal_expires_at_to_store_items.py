"""Add collective_goal_expires_at to store_items

Revision ID: e3f4g5h6i7j8
Revises: d2e4f6a8b0c1
Create Date: 2026-02-27 00:00:00.000000

Adds an optional expiration deadline for collective goal store items.
When the deadline passes without the goal being met, pending purchases
are automatically refunded and the item is deactivated.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f4g5h6i7j8'
down_revision = 'd2e4f6a8b0c1'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    if not column_exists('store_items', 'collective_goal_expires_at'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'collective_goal_expires_at',
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )
        print("✅ Added collective_goal_expires_at to store_items")
    else:
        print("⚠️  Column 'collective_goal_expires_at' already exists on 'store_items', skipping...")


def downgrade():
    if column_exists('store_items', 'collective_goal_expires_at'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.drop_column('collective_goal_expires_at')
        print("❌ Dropped collective_goal_expires_at from store_items")
    else:
        print("⚠️  Column 'collective_goal_expires_at' does not exist on 'store_items', skipping...")
