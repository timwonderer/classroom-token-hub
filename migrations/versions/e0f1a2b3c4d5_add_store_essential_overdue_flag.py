"""Add Store essential overdue-purchase flag.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""
from alembic import op
import sqlalchemy as sa

revision = 'e0f1a2b3c4d5'
down_revision = 'd9e0f1a2b3c4'
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
    if not column_exists('store_products', 'essential_when_overdue'):
        op.add_column(
            'store_products',
            sa.Column('essential_when_overdue', sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade():
    if column_exists('store_products', 'essential_when_overdue'):
        op.drop_column('store_products', 'essential_when_overdue')
