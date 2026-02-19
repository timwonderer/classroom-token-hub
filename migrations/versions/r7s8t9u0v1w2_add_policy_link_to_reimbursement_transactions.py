"""Add policy link to reimbursement transactions.

Revision ID: r7s8t9u0v1w2
Revises: e7f8g9h0i1j2
Create Date: 2026-02-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r7s8t9u0v1w2'
down_revision = 'e7f8g9h0i1j2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column('policy_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_transaction_policy_id'), 'transaction', ['policy_id'], unique=False)
    op.create_foreign_key(
        'fk_transaction_policy_id_insurance_policies',
        'transaction',
        'insurance_policies',
        ['policy_id'],
        ['id'],
    )
    op.create_unique_constraint(
        'uq_insurance_reimbursement_source_policy',
        'transaction',
        ['type', 'original_transaction_id', 'policy_id'],
    )


def downgrade():
    op.drop_constraint('uq_insurance_reimbursement_source_policy', 'transaction', type_='unique')
    op.drop_constraint('fk_transaction_policy_id_insurance_policies', 'transaction', type_='foreignkey')
    op.drop_index(op.f('ix_transaction_policy_id'), table_name='transaction')
    op.drop_column('transaction', 'policy_id')
