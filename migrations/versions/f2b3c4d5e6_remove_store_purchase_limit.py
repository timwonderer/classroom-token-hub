"""Remove obsolete per-student purchase limit.

Revision ID: f2b3c4d5e6
Revises: e0f1a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa

revision = 'f2b3c4d5e6'
down_revision = 'e0f1a2b3c4d5'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    if column_exists('store_products', 'limit_per_student'):
        op.drop_column('store_products', 'limit_per_student')


def downgrade():
    # The column comes back empty. Its values were a per-student *purchase*
    # cap and nothing in the forward direction preserved them, so this restores
    # the shape, not the data.
    if not column_exists('store_products', 'limit_per_student'):
        op.add_column('store_products', sa.Column('limit_per_student', sa.Integer(), nullable=True))
