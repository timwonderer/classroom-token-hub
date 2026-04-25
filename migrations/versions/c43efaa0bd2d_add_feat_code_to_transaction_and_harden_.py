"""Add feat_code to Transaction and Harden idempotency constraints

Revision ID: c43efaa0bd2d
Revises: 9839123f646a
Create Date: 2026-04-24 15:10:36.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c43efaa0bd2d'
down_revision = '9839123f646a'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add class_id and feat_code columns
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('class_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('feat_code', sa.String(length=50), nullable=True))
        
        # 2. Drop the old idempotency unique constraint
        batch_op.drop_constraint('uq_transaction_idempotency_scope', type_='unique')
        
        # 3. Create indices for new columns
        batch_op.create_index(batch_op.f('ix_transaction_class_id'), ['class_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transaction_feat_code'), ['feat_code'], unique=False)
        
        # 4. Create the new hardened idempotency index
        # Using a partial index to allow multiple null idempotency_key rows if needed (though our logic avoids them)
        batch_op.create_index(
            'uq_transaction_idempotency_scope',
            ['class_id', 'seat_id', 'feat_code', 'idempotency_key', 'type'],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        )
        
        # 5. Add foreign key for class_id
        batch_op.create_foreign_key(
            'fk_transaction_class_id_class_economies',
            'class_economies',
            ['class_id'], ['class_id'],
            ondelete='CASCADE'
        )

def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_constraint('fk_transaction_class_id_class_economies', type_='foreignkey')
        batch_op.drop_index('uq_transaction_idempotency_scope', postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'"))
        batch_op.drop_index(batch_op.f('ix_transaction_feat_code'))
        batch_op.drop_index(batch_op.f('ix_transaction_class_id'))
        
        # Restore old unique constraint
        batch_op.create_unique_constraint('uq_transaction_idempotency_scope', ['join_code', 'seat_id', 'idempotency_key', 'type'])
        
        batch_op.drop_column('feat_code')
        batch_op.drop_column('class_id')
