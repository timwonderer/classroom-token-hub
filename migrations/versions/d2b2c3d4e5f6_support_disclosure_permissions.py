"""Persist per-category teacher permissions for support disclosure."""
from alembic import op
import sqlalchemy as sa

revision = 'd2b2c3d4e5f6'
down_revision = 'c1a1b2d3e4f5'
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
    if table_exists('issues'):
        if not column_exists('issues', 'support_permissions'):
            op.add_column('issues', sa.Column('support_permissions', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    if column_exists('issues', 'support_permissions'):
        op.drop_column('issues', 'support_permissions')
