"""Encrypted PII staging for signup; no plaintext or existing-row conversion."""
from alembic import op
import sqlalchemy as sa

revision = 'a1e1f2a3b4c5'
down_revision = 'f0d0e1f2a3b4'
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
    # Initial migration bootstraps from current metadata.
    if not table_exists('teacher_signup_attempts'):
        op.create_table('teacher_signup_attempts',
            sa.Column('nonce_hash', sa.String(64), primary_key=True),
            sa.Column('payload_encrypted', sa.Text(), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    if not index_exists('teacher_signup_attempts', 'ix_teacher_signup_attempts_expires_at'):
        op.create_index('ix_teacher_signup_attempts_expires_at', 'teacher_signup_attempts', ['expires_at'])


def downgrade():
    if table_exists('teacher_signup_attempts'):
        op.drop_table('teacher_signup_attempts')
