"""modularize insurance products

Revision ID: g9h0i1j2k3l4
Revises: f8a9b0c1d2e3
Create Date: 2026-03-13 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g9h0i1j2k3l4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if table_exists('insurance_policies'):
        if not column_exists('insurance_policies', 'coverage_percent'):
            op.add_column('insurance_policies', sa.Column('coverage_percent', sa.Numeric(precision=5, scale=4), nullable=True))
        if not column_exists('insurance_policies', 'product_group_id'):
            op.add_column('insurance_policies', sa.Column('product_group_id', sa.Integer(), nullable=True))
        if not column_exists('insurance_policies', 'tier_rank'):
            op.add_column('insurance_policies', sa.Column('tier_rank', sa.Integer(), nullable=True))
        if not column_exists('insurance_policies', 'requires_review'):
            op.add_column('insurance_policies', sa.Column('requires_review', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    if table_exists('student_insurance'):
        if not column_exists('student_insurance', 'frozen_premium'):
            op.add_column('student_insurance', sa.Column('frozen_premium', sa.Numeric(precision=12, scale=2), nullable=True))
        if not column_exists('student_insurance', 'frozen_coverage_percent'):
            op.add_column('student_insurance', sa.Column('frozen_coverage_percent', sa.Numeric(precision=5, scale=4), nullable=True))
        if not column_exists('student_insurance', 'frozen_waiting_period_days'):
            op.add_column('student_insurance', sa.Column('frozen_waiting_period_days', sa.Integer(), nullable=True))

    conn = op.get_bind()

    conn.execute(sa.text(
        """
        UPDATE insurance_policies
        SET coverage_percent = 1.0,
            requires_review = TRUE
        WHERE claim_type = 'transaction_monetary'
          AND coverage_percent IS NULL
        """
    ))
    conn.execute(sa.text(
        """
        UPDATE insurance_policies
        SET requires_review = TRUE
        WHERE claim_type = 'transaction_monetary'
        """
    ))
    conn.execute(sa.text(
        """
        UPDATE insurance_policies
        SET product_group_id = tier_category_id
        WHERE product_group_id IS NULL
          AND tier_category_id IS NOT NULL
        """
    ))
    conn.execute(sa.text(
        """
        UPDATE insurance_policies
        SET tier_rank = CASE LOWER(COALESCE(tier_level, ''))
            WHEN 'basic' THEN 1
            WHEN 'mid' THEN 2
            WHEN 'premium' THEN 3
            ELSE tier_rank
        END
        WHERE tier_rank IS NULL
          AND tier_level IS NOT NULL
        """
    ))
    if table_exists('insurance_policies') and table_exists('student_insurance'):
        conn.execute(sa.text(
            """
            UPDATE student_insurance AS si
            SET frozen_premium = COALESCE(si.frozen_premium, ip.premium),
                frozen_coverage_percent = COALESCE(si.frozen_coverage_percent, ip.coverage_percent),
                frozen_waiting_period_days = COALESCE(si.frozen_waiting_period_days, ip.waiting_period_days)
            FROM insurance_policies AS ip
            WHERE si.policy_id = ip.id
              AND (
                si.frozen_premium IS NULL
                OR si.frozen_coverage_percent IS NULL
                OR si.frozen_waiting_period_days IS NULL
              )
            """
        ))

    if table_exists('insurance_policies') and not index_exists('insurance_policies', 'uq_insurance_policy_group_rank'):
        op.create_index(
            'uq_insurance_policy_group_rank',
            'insurance_policies',
            ['teacher_id', 'product_group_id', 'tier_rank'],
            unique=True,
            postgresql_where=sa.text('product_group_id IS NOT NULL AND tier_rank IS NOT NULL'),
        )


def downgrade():
    if table_exists('insurance_policies') and index_exists('insurance_policies', 'uq_insurance_policy_group_rank'):
        op.drop_index('uq_insurance_policy_group_rank', table_name='insurance_policies')

    if table_exists('student_insurance'):
        if column_exists('student_insurance', 'frozen_waiting_period_days'):
            op.drop_column('student_insurance', 'frozen_waiting_period_days')
        if column_exists('student_insurance', 'frozen_coverage_percent'):
            op.drop_column('student_insurance', 'frozen_coverage_percent')
        if column_exists('student_insurance', 'frozen_premium'):
            op.drop_column('student_insurance', 'frozen_premium')

    if table_exists('insurance_policies'):
        if column_exists('insurance_policies', 'requires_review'):
            op.drop_column('insurance_policies', 'requires_review')
        if column_exists('insurance_policies', 'tier_rank'):
            op.drop_column('insurance_policies', 'tier_rank')
        if column_exists('insurance_policies', 'product_group_id'):
            op.drop_column('insurance_policies', 'product_group_id')
        if column_exists('insurance_policies', 'coverage_percent'):
            op.drop_column('insurance_policies', 'coverage_percent')
