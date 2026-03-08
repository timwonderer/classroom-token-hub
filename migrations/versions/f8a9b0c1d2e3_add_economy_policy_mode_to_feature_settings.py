"""add economy policy mode to feature settings

Revision ID: f8a9b0c1d2e3
Revises: e7f8g9h0i1j2
Create Date: 2026-03-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8g9h0i1j2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('feature_settings', sa.Column('economy_policy_mode', sa.String(length=20), nullable=False, server_default='default'))
    op.add_column('feature_settings', sa.Column('economy_policy_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('feature_settings', sa.Column('economy_policy_alignment_status', sa.String(length=32), nullable=True))
    op.add_column('feature_settings', sa.Column('economy_last_rebalanced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('feature_settings', sa.Column('economy_last_rebalanced_by', sa.Integer(), nullable=True))
    op.add_column('feature_settings', sa.Column('economy_pending_rebalance_json', sa.Text(), nullable=True))

    op.execute("UPDATE feature_settings SET economy_policy_updated_at = CURRENT_TIMESTAMP WHERE economy_policy_updated_at IS NULL")
    op.alter_column('feature_settings', 'economy_policy_updated_at', nullable=False)
    op.alter_column('feature_settings', 'economy_policy_mode', server_default=None)


def downgrade():
    op.drop_column('feature_settings', 'economy_pending_rebalance_json')
    op.drop_column('feature_settings', 'economy_last_rebalanced_by')
    op.drop_column('feature_settings', 'economy_last_rebalanced_at')
    op.drop_column('feature_settings', 'economy_policy_alignment_status')
    op.drop_column('feature_settings', 'economy_policy_updated_at')
    op.drop_column('feature_settings', 'economy_policy_mode')
