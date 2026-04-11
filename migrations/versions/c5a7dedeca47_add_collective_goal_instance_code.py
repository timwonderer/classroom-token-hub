"""Add collective_goal_instance_code

Revision ID: c5a7dedeca47
Revises: 2bde3e5f00ac
Create Date: 2026-04-11 23:25:51.728161

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

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
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
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

# revision identifiers, used by Alembic.
revision = 'c5a7dedeca47'
down_revision = '2bde3e5f00ac'
branch_labels = None
depends_on = None


def upgrade():
    # Schema changes
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('collective_goal_instance_code', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_store_items_collective_goal_instance_code'), ['collective_goal_instance_code'], unique=False)

    with op.batch_alter_table('student_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('collective_goal_instance_code', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_student_items_collective_goal_instance_code'), ['collective_goal_instance_code'], unique=False)

    # Data migration: Ensure existing collective goals and purchases get their first instance code.
    op.execute("""
        UPDATE store_items
        SET collective_goal_instance_code = gen_random_uuid()::varchar
        WHERE item_type = 'collective' 
          AND collective_goal_instance_code IS NULL
    """)
    
    op.execute("""
        UPDATE student_items
        SET collective_goal_instance_code = si.collective_goal_instance_code
        FROM store_items si
        WHERE student_items.store_item_id = si.id
          AND si.item_type = 'collective'
          AND student_items.collective_goal_instance_code IS NULL
    """)


def downgrade():
    with op.batch_alter_table('student_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_items_collective_goal_instance_code'))
        batch_op.drop_column('collective_goal_instance_code')

    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_store_items_collective_goal_instance_code'))
        batch_op.drop_column('collective_goal_instance_code')
