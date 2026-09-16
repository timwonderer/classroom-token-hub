"""Persist per-category teacher permissions for support disclosure."""
from alembic import op
import sqlalchemy as sa

revision = 'd2b2c3d4e5f6'
down_revision = 'c1a1b2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('issues') and 'support_permissions' not in {c['name'] for c in inspector.get_columns('issues')}:
        op.add_column('issues', sa.Column('support_permissions', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('issues') and 'support_permissions' in {c['name'] for c in inspector.get_columns('issues')}:
        op.drop_column('issues', 'support_permissions')
