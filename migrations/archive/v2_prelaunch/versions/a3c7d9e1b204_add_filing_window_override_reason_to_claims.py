"""Add filing_window_override_reason to insurance_claims

Restores a mechanism that existed pre-rewrite (main_legacy_v1.10.0,
k1l2m3n4o5p6_add_time_limit_override_to_claims.py) and was dropped when
insurance was rebuilt from scratch on 2026-08-28 (02d412e6b). Operator
decision 2026-09-21: a TRANSACTION claim filed after the policy's filing
window closes should still be SUBMITTED (not rejected outright), and a
teacher should be able to approve it anyway -- but only by recording a
written justification. `decision_note` is a general annotation attached to
every decision; this column is distinct because approval of a late claim
must be blocked on ITS absence specifically, not satisfied by any note.

Revision ID: a3c7d9e1b204
Revises: f2b8c7e4a916
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c7d9e1b204'
down_revision = 'f2b8c7e4a916'
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


def upgrade():
    if not table_exists('insurance_claims'):
        print("⚠️  insurance_claims does not exist, skipping...")
        return

    if not column_exists('insurance_claims', 'filing_window_override_reason'):
        op.add_column(
            'insurance_claims',
            sa.Column('filing_window_override_reason', sa.Text(), nullable=True),
        )
        print("✅ Added filing_window_override_reason to insurance_claims")
    else:
        print("⚠️  Column 'filing_window_override_reason' already exists, skipping...")


def downgrade():
    if not table_exists('insurance_claims'):
        print("⚠️  insurance_claims does not exist, skipping...")
        return

    if column_exists('insurance_claims', 'filing_window_override_reason'):
        op.drop_column('insurance_claims', 'filing_window_override_reason')
        print("❌ Dropped filing_window_override_reason from insurance_claims")
    else:
        print("⚠️  Column 'filing_window_override_reason' does not exist, skipping...")
