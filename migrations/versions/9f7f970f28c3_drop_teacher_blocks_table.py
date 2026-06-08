"""Drop teacher_blocks table

Revision ID: 9f7f970f28c3
Revises: 0007
Create Date: 2026-06-08 02:27:40.725204

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
revision = '9f7f970f28c3'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('teacher_blocks'):
        op.drop_index(op.f('ix_teacher_blocks_claimed'), table_name='teacher_blocks')
        op.drop_index(op.f('ix_teacher_blocks_class_id'), table_name='teacher_blocks')
        op.drop_index(op.f('ix_teacher_blocks_dedupe_key'), table_name='teacher_blocks')
        op.drop_index(op.f('ix_teacher_blocks_identity_id'), table_name='teacher_blocks')
        op.drop_index(op.f('ix_teacher_blocks_join_code'), table_name='teacher_blocks')
        op.drop_index(op.f('ix_teacher_blocks_teacher_block'), table_name='teacher_blocks')
        op.drop_table('teacher_blocks')


def downgrade():
    if not table_exists('teacher_blocks'):
        op.create_table('teacher_blocks',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('block', sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column('first_name', postgresql.BYTEA(), autoincrement=False, nullable=False),
        sa.Column('last_initial', sa.VARCHAR(length=1), autoincrement=False, nullable=False),
        sa.Column('last_name_hash_by_part', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('salt', postgresql.BYTEA(), autoincrement=False, nullable=False),
        sa.Column('first_half_hash', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('join_code', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column('student_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('is_claimed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('claimed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('is_teacher', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('class_label', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('class_id', sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column('dob_sum_hash', sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.Column('dedupe_key', sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.Column('identity_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], name=op.f('fk_teacher_blocks_class_id_classes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['identity_id'], ['identity_profiles.id'], name=op.f('fk_teacher_blocks_identity_id'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('teacher_blocks_student_id_fkey')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('teacher_blocks_teacher_id_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('teacher_blocks_pkey'))
        )
        op.create_index(op.f('ix_teacher_blocks_teacher_block'), 'teacher_blocks', ['teacher_id', 'block'], unique=False)
        op.create_index(op.f('ix_teacher_blocks_join_code'), 'teacher_blocks', ['join_code'], unique=False)
        op.create_index(op.f('ix_teacher_blocks_identity_id'), 'teacher_blocks', ['identity_id'], unique=False)
        op.create_index(op.f('ix_teacher_blocks_dedupe_key'), 'teacher_blocks', ['dedupe_key'], unique=False)
        op.create_index(op.f('ix_teacher_blocks_class_id'), 'teacher_blocks', ['class_id'], unique=False)
        op.create_index(op.f('ix_teacher_blocks_claimed'), 'teacher_blocks', ['is_claimed'], unique=False)
