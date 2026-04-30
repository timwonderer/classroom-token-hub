"""add economy snapshot table

Revision ID: q9r0s1t2u3v4
Revises: p6q7r8s9t0u1
Create Date: 2026-03-30 11:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'q9r0s1t2u3v4'
down_revision = 'p6q7r8s9t0u1'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    if not table_exists('economy_snapshot'):
        op.create_table(
            'economy_snapshot',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('join_code', sa.String(length=20), nullable=False),
            sa.Column('policy_mode', sa.String(length=20), nullable=False),
            sa.Column('pay_rate', sa.Numeric(precision=12, scale=4), nullable=False),
            sa.Column('expected_hours', sa.Numeric(precision=8, scale=2), nullable=False),
            sa.Column('weekly_cwi', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('rent_min', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('rent_recommended', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('rent_max', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_min', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_recommended', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('insurance_weekly_max', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('store_tier_min', sa.JSON(), nullable=False),
            sa.Column('store_tier_max', sa.JSON(), nullable=False),
            sa.Column('analysis_payload', sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(['join_code'], ['class_economies.join_code'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    if table_exists('economy_snapshot') and not index_exists('economy_snapshot', 'ix_economy_snapshot_join_code'):
        op.create_index('ix_economy_snapshot_join_code', 'economy_snapshot', ['join_code'], unique=False)

    if table_exists('economy_snapshot') and not index_exists('economy_snapshot', 'ix_economy_snapshot_effective_at'):
        op.create_index('ix_economy_snapshot_effective_at', 'economy_snapshot', ['effective_at'], unique=False)


def downgrade():
    if table_exists('economy_snapshot'):
        if index_exists('economy_snapshot', 'ix_economy_snapshot_effective_at'):
            op.drop_index('ix_economy_snapshot_effective_at', table_name='economy_snapshot')
        if index_exists('economy_snapshot', 'ix_economy_snapshot_join_code'):
            op.drop_index('ix_economy_snapshot_join_code', table_name='economy_snapshot')
        op.drop_table('economy_snapshot')
