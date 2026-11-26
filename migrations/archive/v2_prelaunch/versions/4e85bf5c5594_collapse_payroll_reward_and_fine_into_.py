"""Collapse payroll reward and fine into saved adjustment

Revision ID: 4e85bf5c5594
Revises: f7b8c9d0e1f2
Create Date: 2026-06-04 01:26:57.612108

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
revision = '4e85bf5c5594'
down_revision = 'f7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists('saved_adjustments'):
        op.create_table('saved_adjustments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seat_id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.String(length=36), nullable=True),
        sa.Column('join_code', sa.String(length=20), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_saved_adjustments_class_id'), 'saved_adjustments', ['class_id'], unique=False)
        op.create_index(op.f('ix_saved_adjustments_join_code'), 'saved_adjustments', ['join_code'], unique=False)
        op.create_index(op.f('ix_saved_adjustments_seat_id'), 'saved_adjustments', ['seat_id'], unique=False)

    if index_exists('payroll_rewards', 'ix_payroll_rewards_class_id'):
        op.drop_index(op.f('ix_payroll_rewards_class_id'), table_name='payroll_rewards')
    if index_exists('payroll_rewards', 'ix_payroll_rewards_join_code'):
        op.drop_index(op.f('ix_payroll_rewards_join_code'), table_name='payroll_rewards')
    if table_exists('payroll_rewards'):
        op.drop_table('payroll_rewards')

    if index_exists('payroll_fines', 'ix_payroll_fines_class_id'):
        op.drop_index(op.f('ix_payroll_fines_class_id'), table_name='payroll_fines')
    if index_exists('payroll_fines', 'ix_payroll_fines_join_code'):
        op.drop_index(op.f('ix_payroll_fines_join_code'), table_name='payroll_fines')
    if table_exists('payroll_fines'):
        op.drop_table('payroll_fines')


def downgrade():
    if not table_exists('payroll_fines'):
        op.create_table('payroll_fines',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('amount', sa.NUMERIC(precision=12, scale=2), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('join_code', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column('class_id', sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], name=op.f('fk_payroll_fines_class_id_classes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('fk_payroll_fines_teacher')),
        sa.PrimaryKeyConstraint('id', name=op.f('payroll_fines_pkey'))
        )
        op.create_index(op.f('ix_payroll_fines_join_code'), 'payroll_fines', ['join_code'], unique=False)
        op.create_index(op.f('ix_payroll_fines_class_id'), 'payroll_fines', ['class_id'], unique=False)

    if not table_exists('payroll_rewards'):
        op.create_table('payroll_rewards',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('amount', sa.NUMERIC(precision=12, scale=2), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('join_code', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column('class_id', sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], name=op.f('fk_payroll_rewards_class_id_classes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('fk_payroll_rewards_teacher')),
        sa.PrimaryKeyConstraint('id', name=op.f('payroll_rewards_pkey'))
        )
        op.create_index(op.f('ix_payroll_rewards_join_code'), 'payroll_rewards', ['join_code'], unique=False)
        op.create_index(op.f('ix_payroll_rewards_class_id'), 'payroll_rewards', ['class_id'], unique=False)

    if index_exists('saved_adjustments', 'ix_saved_adjustments_seat_id'):
        op.drop_index(op.f('ix_saved_adjustments_seat_id'), table_name='saved_adjustments')
    if index_exists('saved_adjustments', 'ix_saved_adjustments_join_code'):
        op.drop_index(op.f('ix_saved_adjustments_join_code'), table_name='saved_adjustments')
    if index_exists('saved_adjustments', 'ix_saved_adjustments_class_id'):
        op.drop_index(op.f('ix_saved_adjustments_class_id'), table_name='saved_adjustments')
    if table_exists('saved_adjustments'):
        op.drop_table('saved_adjustments')
