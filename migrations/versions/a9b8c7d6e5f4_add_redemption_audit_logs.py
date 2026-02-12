"""Add redemption audit logs table

Revision ID: a9b8c7d6e5f4
Revises: z2a3b4c5d6e7
Create Date: 2026-02-11 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a9b8c7d6e5f4'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


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


def upgrade():
    action_enum = sa.Enum('request', 'approved', 'rejected', name='redemption_audit_action_enum')
    source_enum = sa.Enum('live', name='redemption_audit_source_enum')
    # Avoid duplicate enum DDL during create_table after explicit create(checkfirst=True).
    action_enum_col = postgresql.ENUM(
        'request', 'approved', 'rejected',
        name='redemption_audit_action_enum',
        create_type=False,
    )
    source_enum_col = postgresql.ENUM(
        'live',
        name='redemption_audit_source_enum',
        create_type=False,
    )

    bind = op.get_bind()
    action_enum.create(bind, checkfirst=True)
    source_enum.create(bind, checkfirst=True)

    if not table_exists('redemption_audit_logs'):
        op.create_table(
            'redemption_audit_logs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('student_item_id', sa.Integer(), nullable=True),
            sa.Column('student_display_name', sa.String(length=120), nullable=False),
            sa.Column('class_display_label', sa.String(length=120), nullable=False),
            sa.Column('action', action_enum_col, nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('teacher_id', sa.Integer(), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('source', source_enum_col, nullable=False),
            sa.ForeignKeyConstraint(['student_item_id'], ['student_items.id']),
            sa.ForeignKeyConstraint(['teacher_id'], ['admins.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if table_exists('redemption_audit_logs'):
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_timestamp'):
            op.create_index('ix_redemption_audit_logs_timestamp', 'redemption_audit_logs', ['timestamp'])
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_student_item_id'):
            op.create_index('ix_redemption_audit_logs_student_item_id', 'redemption_audit_logs', ['student_item_id'])
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_teacher_id'):
            op.create_index('ix_redemption_audit_logs_teacher_id', 'redemption_audit_logs', ['teacher_id'])
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_action'):
            op.create_index('ix_redemption_audit_logs_action', 'redemption_audit_logs', ['action'])
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_source'):
            op.create_index('ix_redemption_audit_logs_source', 'redemption_audit_logs', ['source'])
        if not index_exists('redemption_audit_logs', 'ix_redemption_audit_logs_teacher_timestamp'):
            op.create_index('ix_redemption_audit_logs_teacher_timestamp', 'redemption_audit_logs', ['teacher_id', 'timestamp'])


def downgrade():
    raise RuntimeError(
        "Downgrade is not supported for migration a9b8c7d6e5f4. "
        "The redemption_audit_logs table is append-only and must not be removed or "
        "contracted. If a downgrade is required, manually drop related indexes and "
        "enum types before adjusting the Alembic revision."
    )
