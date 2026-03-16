"""add economy snapshot table

Revision ID: h0i1j2k3l4m
Revises: g9h0i1j2k3l4
Create Date: 2026-03-15 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h0i1j2k3l4m'
down_revision = 'g9h0i1j2k3l4'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if not table_exists('economy_snapshot'):
        op.create_table(
            'economy_snapshot',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('join_code_id', sa.String(length=36), nullable=False),
            sa.Column('policy_mode', sa.String(length=20), nullable=False, server_default='default'),
            sa.Column('pay_rate', sa.Numeric(precision=12, scale=4), nullable=False),
            sa.Column('expected_hours', sa.Numeric(precision=8, scale=2), nullable=False),
            sa.Column('weekly_cwi', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('rent_min', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('rent_recommended', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('rent_max', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_min', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_recommended', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_max', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('store_tier_min', sa.JSON(), nullable=False),
            sa.Column('store_tier_max', sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(['join_code_id'], ['join_codes.join_code_id'], ondelete='CASCADE'),
        )

    if table_exists('economy_snapshot') and not index_exists('economy_snapshot', 'ix_economy_snapshot_join_code_id'):
        op.create_index('ix_economy_snapshot_join_code_id', 'economy_snapshot', ['join_code_id'], unique=False)
    if table_exists('economy_snapshot') and not index_exists('economy_snapshot', 'ix_economy_snapshot_effective_at'):
        op.create_index('ix_economy_snapshot_effective_at', 'economy_snapshot', ['effective_at'], unique=False)


def downgrade():
    if table_exists('economy_snapshot') and index_exists('economy_snapshot', 'ix_economy_snapshot_effective_at'):
        op.drop_index('ix_economy_snapshot_effective_at', table_name='economy_snapshot')
    if table_exists('economy_snapshot') and index_exists('economy_snapshot', 'ix_economy_snapshot_join_code_id'):
        op.drop_index('ix_economy_snapshot_join_code_id', table_name='economy_snapshot')
    if table_exists('economy_snapshot'):
        op.drop_table('economy_snapshot')
