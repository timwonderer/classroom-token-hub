"""Invalidate previous claim authorizations when a teacher unclaims a Seat."""
from alembic import op
import sqlalchemy as sa
revision = 'd8b8c9d0e1f2'
down_revision = 'c7a7b8c9d0e1'
branch_labels = None
depends_on = None

def upgrade():
    if 'claim_generation' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('seats')}:
        op.add_column('seats', sa.Column('claim_generation', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('seats', 'claim_generation')
