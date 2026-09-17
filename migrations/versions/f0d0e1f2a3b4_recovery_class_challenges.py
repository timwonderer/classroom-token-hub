"""Frozen random recipients and persistent class confirmations."""
from alembic import op
import sqlalchemy as sa

revision = 'f0d0e1f2a3b4'
down_revision = 'e9c9d0e1f2a3'
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
    if not column_exists('recovery_requests', 'required_class_ids'):
        op.add_column('recovery_requests', sa.Column('required_class_ids', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    if not column_exists('recovery_requests', 'attempt_nonce_hash'):
        op.add_column('recovery_requests', sa.Column('attempt_nonce_hash', sa.String(64), nullable=True))
    if not column_exists('recovery_requests', 'selection_started_at'):
        op.add_column('recovery_requests', sa.Column('selection_started_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('recovery_requests', 'submission_round'):
        op.add_column('recovery_requests', sa.Column('submission_round', sa.Integer(), nullable=False, server_default='0'))
    if not column_exists('student_recovery_codes', 'issued_round'):
        op.add_column('student_recovery_codes', sa.Column('issued_round', sa.Integer(), nullable=True))
    if not column_exists('student_recovery_codes', 'code_expires_at'):
        op.add_column('student_recovery_codes', sa.Column('code_expires_at', sa.DateTime(timezone=True), nullable=True))
    if not table_exists('recovery_class_challenges'):
        op.create_table('recovery_class_challenges',
            sa.Column('recovery_request_id', sa.Integer(), sa.ForeignKey('recovery_requests.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('proof_verified_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('selected_at', sa.DateTime(timezone=True)), sa.Column('selected_count', sa.Integer()),
            sa.Column('satisfied_at', sa.DateTime(timezone=True)),
            sa.Column('satisfied_round', sa.Integer()), sa.Column('received_round', sa.Integer()))


def downgrade():
    if table_exists('recovery_class_challenges'):
        op.drop_table('recovery_class_challenges')
    for table, name in [('student_recovery_codes', 'code_expires_at'), ('student_recovery_codes', 'issued_round'),
                        ('recovery_requests', 'submission_round'), ('recovery_requests', 'required_class_ids'),
                        ('recovery_requests', 'attempt_nonce_hash'), ('recovery_requests', 'selection_started_at')]:
        if column_exists(table, name):
            op.drop_column(table, name)
