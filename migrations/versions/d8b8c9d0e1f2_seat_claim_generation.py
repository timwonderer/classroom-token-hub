"""Invalidate previous claim authorizations when a teacher unclaims a Seat."""
from alembic import op
import sqlalchemy as sa

revision = 'd8b8c9d0e1f2'
down_revision = 'c7a7b8c9d0e1'
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
    if not column_exists('seats', 'claim_generation'):
        op.add_column('seats', sa.Column('claim_generation', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    if column_exists('seats', 'claim_generation'):
        op.drop_column('seats', 'claim_generation')
