"""Harden Transaction with correlation_id and idempotency scope

Revision ID: 9839123f646a
Revises: t1u2v3w4x5y6
Create Date: 2026-04-24 03:55:45.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9839123f646a'
down_revision = 't1u2v3w4x5y6'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add correlation_id column
    op.add_column('transaction', sa.Column('correlation_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_transaction_correlation_id'), 'transaction', ['correlation_id'], unique=False)
    
    # 2. Relax global unique constraint on idempotency_key (moving to composite)
    # Note: We keep the index but make it non-unique globally to allow composite uniqueness
    op.drop_index('ix_transaction_idempotency_key', table_name='transaction')
    op.create_index(op.f('ix_transaction_idempotency_key'), 'transaction', ['idempotency_key'], unique=False)
    
    # 3. Add composite unique constraint
    op.create_unique_constraint(
        'uq_transaction_idempotency_scope', 
        'transaction', 
        ['join_code', 'seat_id', 'idempotency_key', 'type']
    )

def downgrade():
    # 1. Remove composite unique constraint
    op.drop_constraint('uq_transaction_idempotency_scope', 'transaction', type_='unique')
    
    # 2. Restore global unique constraint on idempotency_key
    op.drop_index(op.f('ix_transaction_idempotency_key'), table_name='transaction')
    op.create_index('ix_transaction_idempotency_key', 'transaction', ['idempotency_key'], unique=True)
    
    # 3. Remove correlation_id column
    op.drop_index(op.f('ix_transaction_correlation_id'), table_name='transaction')
    op.drop_column('transaction', 'correlation_id')
