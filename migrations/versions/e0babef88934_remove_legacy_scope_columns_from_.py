"""Remove legacy scope columns from HallPassSettings

Revision ID: e0babef88934
Revises: c8f1e2d3a4b5
Create Date: 2026-06-05 04:08:52.796269

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
revision = 'e0babef88934'
down_revision = 'c8f1e2d3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_select ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_insert ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_update ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_delete ON hall_pass_settings")

    if index_exists('hall_pass_settings', 'ix_hall_pass_settings_join_code'):
        op.drop_index(op.f('ix_hall_pass_settings_join_code'), table_name='hall_pass_settings')
    if index_exists('hall_pass_settings', 'ix_hall_pass_settings_teacher_id'):
        op.drop_index(op.f('ix_hall_pass_settings_teacher_id'), table_name='hall_pass_settings')
    
    fks = get_foreign_keys_by_column('hall_pass_settings', 'teacher_id')
    for fk in fks:
        op.drop_constraint(fk['name'], 'hall_pass_settings', type_='foreignkey')

    if column_exists('hall_pass_settings', 'block'):
        op.drop_column('hall_pass_settings', 'block')
    if column_exists('hall_pass_settings', 'join_code'):
        op.drop_column('hall_pass_settings', 'join_code')
    if column_exists('hall_pass_settings', 'teacher_id'):
        op.drop_column('hall_pass_settings', 'teacher_id')


def downgrade():
    if not column_exists('hall_pass_settings', 'teacher_id'):
        op.add_column('hall_pass_settings', sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=True))
    if not column_exists('hall_pass_settings', 'join_code'):
        op.add_column('hall_pass_settings', sa.Column('join_code', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    if not column_exists('hall_pass_settings', 'block'):
        op.add_column('hall_pass_settings', sa.Column('block', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    
    if not index_exists('hall_pass_settings', 'ix_hall_pass_settings_teacher_id'):
        op.create_index(op.f('ix_hall_pass_settings_teacher_id'), 'hall_pass_settings', ['teacher_id'], unique=False)
    if not index_exists('hall_pass_settings', 'ix_hall_pass_settings_join_code'):
        op.create_index(op.f('ix_hall_pass_settings_join_code'), 'hall_pass_settings', ['join_code'], unique=False)
