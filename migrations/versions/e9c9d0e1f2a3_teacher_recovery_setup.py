"""Server-owned teacher recovery setup authorization and encrypted progress."""
from alembic import op
import sqlalchemy as sa

revision = 'e9c9d0e1f2a3'
down_revision = 'd8b8c9d0e1f2'
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


_SETUP_COLUMNS = [('setup_nonce_hash', sa.String(64)), ('setup_totp_encrypted', sa.Text()), ('setup_username', sa.Text())]


def upgrade():
    for name, type_ in _SETUP_COLUMNS:
        if not column_exists('recovery_requests', name):
            op.add_column('recovery_requests', sa.Column(name, type_, nullable=True))
    op.alter_column('recovery_requests', 'resume_new_username', type_=sa.Text())


def downgrade():
    for name, _type in _SETUP_COLUMNS:
        if column_exists('recovery_requests', name):
            op.drop_column('recovery_requests', name)
