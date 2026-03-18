"""add analysis payload to economy snapshot

Revision ID: i1j2k3l4m5n6
Revises: h0i1j2k3l4m
Create Date: 2026-03-17 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i1j2k3l4m5n6'
down_revision = 'h0i1j2k3l4m'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [column['name'] for column in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    if not column_exists('economy_snapshot', 'analysis_payload'):
        op.add_column('economy_snapshot', sa.Column('analysis_payload', sa.JSON(), nullable=True))


def downgrade():
    if column_exists('economy_snapshot', 'analysis_payload'):
        op.drop_column('economy_snapshot', 'analysis_payload')
