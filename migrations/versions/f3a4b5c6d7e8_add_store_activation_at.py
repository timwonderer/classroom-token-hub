"""Add prospective Store activation date.

Revision ID: f3a4b5c6d7e8
Revises: f2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a4b5c6d7e8'
down_revision = 'f2b3c4d5e6'
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
    if not column_exists('store_products', 'activation_at'):
        op.add_column('store_products', sa.Column('activation_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if column_exists('store_products', 'activation_at'):
        op.drop_column('store_products', 'activation_at')
