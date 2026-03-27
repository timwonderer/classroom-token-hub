"""Add collective goal instance codes

Revision ID: a4b5c6d7e8f9
Revises: z2a3b4c5d6e7
Create Date: 2026-03-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4b5c6d7e8f9'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('store_items', sa.Column('collective_goal_instance_code', sa.String(length=64), nullable=True))
    op.add_column('student_items', sa.Column('collective_goal_instance_code', sa.String(length=64), nullable=True))
    op.create_index('ix_store_items_collective_goal_instance_code', 'store_items', ['collective_goal_instance_code'], unique=False)
    op.create_index('ix_student_items_collective_goal_instance_code', 'student_items', ['collective_goal_instance_code'], unique=False)

    # Backfill existing collective items so current in-flight goals keep their progress.
    op.execute("""
        UPDATE store_items
        SET collective_goal_instance_code = 'legacy-item-' || id
        WHERE item_type = 'collective'
          AND collective_goal_instance_code IS NULL
    """)
    op.execute("""
        UPDATE student_items
        SET collective_goal_instance_code = (
            SELECT store_items.collective_goal_instance_code
            FROM store_items
            WHERE store_items.id = student_items.store_item_id
        )
        WHERE store_item_id IN (
            SELECT id FROM store_items WHERE item_type = 'collective'
        )
          AND collective_goal_instance_code IS NULL
    """)


def downgrade():
    op.drop_index('ix_student_items_collective_goal_instance_code', table_name='student_items')
    op.drop_index('ix_store_items_collective_goal_instance_code', table_name='store_items')
    op.drop_column('student_items', 'collective_goal_instance_code')
    op.drop_column('store_items', 'collective_goal_instance_code')
