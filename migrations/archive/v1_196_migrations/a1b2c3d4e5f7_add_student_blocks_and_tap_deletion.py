"""Add StudentBlock model and tap deletion fields

Revision ID: a1b2c3d4e5f7
Revises: 1n7bslh69u6x
Create Date: 2025-12-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '1n7bslh69u6x'
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

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        # Check unique constraints
        uniques = [uc['name'] for uc in inspector.get_unique_constraints(table_name)]
        if constraint_name in uniques:
            return True
        # Check foreign keys
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        if constraint_name in fks:
            return True
        return False
    except Exception:
        return False

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # Create student_blocks table
    if not table_exists('student_blocks'):
        op.create_table('student_blocks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('period', sa.String(length=10), nullable=False),
            sa.Column('tap_enabled', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('done_for_day_date', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'period', name='uq_student_blocks_student_period')
        )
    
    # Create indexes for student_blocks
    if not index_exists('student_blocks', 'ix_student_blocks_student_id'):
        op.create_index('ix_student_blocks_student_id', 'student_blocks', ['student_id'])
    if not index_exists('student_blocks', 'ix_student_blocks_period'):
        op.create_index('ix_student_blocks_period', 'student_blocks', ['period'])

    # Add deletion tracking fields to tap_events
    if not column_exists('tap_events', 'is_deleted'):
        op.add_column('tap_events', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
    if not column_exists('tap_events', 'deleted_at'):
        op.add_column('tap_events', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    if not column_exists('tap_events', 'deleted_by'):
        op.add_column('tap_events', sa.Column('deleted_by', sa.Integer(), nullable=True))

    # Add foreign key for deleted_by
    if not constraint_exists('tap_events', 'fk_tap_events_deleted_by'):
        op.create_foreign_key('fk_tap_events_deleted_by', 'tap_events', 'admins', ['deleted_by'], ['id'], ondelete='SET NULL')


def downgrade():
    # Remove foreign key and columns from tap_events
    op.drop_constraint('fk_tap_events_deleted_by', 'tap_events', type_='foreignkey')
    op.drop_column('tap_events', 'deleted_by')
    op.drop_column('tap_events', 'deleted_at')
    op.drop_column('tap_events', 'is_deleted')

    # Drop indexes and table for student_blocks
    op.drop_index('ix_student_blocks_period', 'student_blocks')
    op.drop_index('ix_student_blocks_student_id', 'student_blocks')
    op.drop_table('student_blocks')
