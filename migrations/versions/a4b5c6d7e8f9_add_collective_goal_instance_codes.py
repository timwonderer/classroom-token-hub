"""Add collective goal instance codes

Revision ID: a4b5c6d7e8f9
Revises: z2a3b4c5d6e7
Create Date: 2026-03-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'a4b5c6d7e8f9'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def foreign_key_exists(table_name, fk_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys


def upgrade():
    if table_exists('store_items') and not column_exists('store_items', 'collective_goal_instance_code'):
        op.add_column('store_items', sa.Column('collective_goal_instance_code', sa.String(length=64), nullable=True))

    if table_exists('student_items') and not column_exists('student_items', 'collective_goal_instance_code'):
        op.add_column('student_items', sa.Column('collective_goal_instance_code', sa.String(length=64), nullable=True))

    if table_exists('store_items') and not index_exists('store_items', 'ix_store_items_collective_goal_instance_code'):
        op.create_index('ix_store_items_collective_goal_instance_code', 'store_items', ['collective_goal_instance_code'], unique=False)

    if table_exists('student_items') and not index_exists('student_items', 'ix_student_items_collective_goal_instance_code'):
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
    if table_exists('student_items') and index_exists('student_items', 'ix_student_items_collective_goal_instance_code'):
        op.drop_index('ix_student_items_collective_goal_instance_code', table_name='student_items')

    if table_exists('store_items') and index_exists('store_items', 'ix_store_items_collective_goal_instance_code'):
        op.drop_index('ix_store_items_collective_goal_instance_code', table_name='store_items')

    if table_exists('student_items') and column_exists('student_items', 'collective_goal_instance_code'):
        op.drop_column('student_items', 'collective_goal_instance_code')

    if table_exists('store_items') and column_exists('store_items', 'collective_goal_instance_code'):
        op.drop_column('store_items', 'collective_goal_instance_code')
