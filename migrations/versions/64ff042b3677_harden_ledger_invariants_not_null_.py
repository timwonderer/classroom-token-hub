"""Harden ledger invariants: NOT NULL correlation_id, StudentItem correlation, and improved idempotency index

Revision ID: 64ff042b3677
Revises: 94585623994c
Create Date: 2026-04-24 15:47:20.224434

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '64ff042b3677'
down_revision = '94585623994c'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add correlation_id to student_items
    op.add_column('student_items', sa.Column('correlation_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_student_items_correlation_id'), 'student_items', ['correlation_id'], unique=False)

    # 2. Backfill Transaction correlation_id
    op.execute("UPDATE transaction SET correlation_id = 'legacy_' || id WHERE correlation_id IS NULL")

    # 3. Harden Transaction correlation_id and index
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.alter_column('correlation_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
        
        # Drop old index (using its name)
        # Note: In previous migrations it might have been named differently or missing.
        # We use batch_op.drop_index if possible, but op.execute for safety if it's a named constraint.
        batch_op.drop_index('uq_transaction_idempotency_scope')
        
        # Create new hardened index
        batch_op.create_index(
            'uq_transaction_idempotency_scope', 
            ['class_id', 'student_id', 'seat_id', 'feat_code', 'idempotency_key', 'type'], 
            unique=True, 
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        )

def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_index('uq_transaction_idempotency_scope')
        batch_op.create_index(
            'uq_transaction_idempotency_scope', 
            ['class_id', 'seat_id', 'feat_code', 'idempotency_key', 'type'], 
            unique=True, 
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        )
        batch_op.alter_column('correlation_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)

    op.drop_index(op.f('ix_student_items_correlation_id'), table_name='student_items')
    op.drop_column('student_items', 'correlation_id')
