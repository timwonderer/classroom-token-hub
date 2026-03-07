"""add insurance policy snapshots to student enrollments

Revision ID: b6c7d8e9f0a1
Revises: f4g5h6i7j8k9
Create Date: 2026-02-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'b6c7d8e9f0a1'
down_revision = 'f4g5h6i7j8k9'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def foreign_key_exists(table_name, fk_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in fks


def upgrade():
    if table_exists('insurance_policies') and not column_exists('insurance_policies', 'version_number'):
        op.add_column('insurance_policies', sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'))

    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_policy_title'):
        op.add_column('student_insurance', sa.Column('frozen_policy_title', sa.String(length=100), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_policy_description'):
        op.add_column('student_insurance', sa.Column('frozen_policy_description', sa.Text(), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_max_claim_amount'):
        op.add_column('student_insurance', sa.Column('frozen_max_claim_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_max_payout_per_period'):
        op.add_column('student_insurance', sa.Column('frozen_max_payout_per_period', sa.Numeric(precision=12, scale=2), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_max_claims_count'):
        op.add_column('student_insurance', sa.Column('frozen_max_claims_count', sa.Integer(), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_max_claims_period'):
        op.add_column('student_insurance', sa.Column('frozen_max_claims_period', sa.String(length=20), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'frozen_claim_time_limit_days'):
        op.add_column('student_insurance', sa.Column('frozen_claim_time_limit_days', sa.Integer(), nullable=True))
    if table_exists('student_insurance') and not column_exists('student_insurance', 'policy_version'):
        op.add_column('student_insurance', sa.Column('policy_version', sa.Integer(), nullable=True))

    # Freeze existing active enrollments that predate snapshots.
    op.execute(
        """
        UPDATE student_insurance AS si
        SET
            frozen_policy_title = COALESCE(
                si.frozen_policy_title,
                (SELECT p.title FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_policy_description = COALESCE(
                si.frozen_policy_description,
                (SELECT p.description FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_max_claim_amount = COALESCE(
                si.frozen_max_claim_amount,
                (SELECT p.max_claim_amount FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_max_payout_per_period = COALESCE(
                si.frozen_max_payout_per_period,
                (SELECT p.max_payout_per_period FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_max_claims_count = COALESCE(
                si.frozen_max_claims_count,
                (SELECT p.max_claims_count FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_max_claims_period = COALESCE(
                si.frozen_max_claims_period,
                (SELECT p.max_claims_period FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            frozen_claim_time_limit_days = COALESCE(
                si.frozen_claim_time_limit_days,
                (SELECT p.claim_time_limit_days FROM insurance_policies AS p WHERE p.id = si.policy_id)
            ),
            policy_version = COALESCE(
                si.policy_version,
                (SELECT p.version_number FROM insurance_policies AS p WHERE p.id = si.policy_id)
            )
        WHERE si.status = 'active'
          AND (
            si.frozen_policy_title IS NULL
            OR si.frozen_policy_description IS NULL
            OR si.frozen_max_claim_amount IS NULL
            OR si.frozen_max_payout_per_period IS NULL
            OR si.frozen_max_claims_count IS NULL
            OR si.frozen_max_claims_period IS NULL
            OR si.frozen_claim_time_limit_days IS NULL
            OR si.policy_version IS NULL
          )
        """
    )

    if table_exists('insurance_policies') and column_exists('insurance_policies', 'version_number'):
        op.alter_column('insurance_policies', 'version_number', server_default=None)


def downgrade():
    if table_exists('student_insurance') and column_exists('student_insurance', 'policy_version'):
        op.drop_column('student_insurance', 'policy_version')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_claim_time_limit_days'):
        op.drop_column('student_insurance', 'frozen_claim_time_limit_days')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_max_claims_period'):
        op.drop_column('student_insurance', 'frozen_max_claims_period')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_max_claims_count'):
        op.drop_column('student_insurance', 'frozen_max_claims_count')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_max_payout_per_period'):
        op.drop_column('student_insurance', 'frozen_max_payout_per_period')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_max_claim_amount'):
        op.drop_column('student_insurance', 'frozen_max_claim_amount')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_policy_description'):
        op.drop_column('student_insurance', 'frozen_policy_description')
    if table_exists('student_insurance') and column_exists('student_insurance', 'frozen_policy_title'):
        op.drop_column('student_insurance', 'frozen_policy_title')

    if table_exists('insurance_policies') and column_exists('insurance_policies', 'version_number'):
        op.drop_column('insurance_policies', 'version_number')
