"""add student archive and transaction links

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'b0c1d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('students', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.create_index(op.f('ix_students_is_active'), 'students', ['is_active'], unique=False)

    op.add_column('transaction', sa.Column('original_transaction_id', sa.Integer(), nullable=True))
    op.add_column('transaction', sa.Column('reversal_transaction_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_transaction_original_transaction_id'), 'transaction', ['original_transaction_id'], unique=False)
    op.create_index(op.f('ix_transaction_reversal_transaction_id'), 'transaction', ['reversal_transaction_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_transaction_reversal_transaction_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_original_transaction_id'), table_name='transaction')
    op.drop_column('transaction', 'reversal_transaction_id')
    op.drop_column('transaction', 'original_transaction_id')

    op.drop_index(op.f('ix_students_is_active'), table_name='students')
    op.drop_column('students', 'is_active')
