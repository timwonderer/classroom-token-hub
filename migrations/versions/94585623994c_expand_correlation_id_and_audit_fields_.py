"""Expand correlation_id and audit fields to 100 chars

Revision ID: 94585623994c
Revises: c43efaa0bd2d
Create Date: 2026-04-24 15:31:24.982114

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '94585623994c'
down_revision = 'c43efaa0bd2d'
branch_labels = None
depends_on = None

def upgrade():
    # Expand transaction columns
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.alter_column('correlation_id',
               existing_type=sa.VARCHAR(length=36),
               type_=sa.String(length=100),
               existing_nullable=True)
        batch_op.alter_column('feat_code',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=100),
               existing_nullable=True)
        batch_op.alter_column('idempotency_key',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=100),
               existing_nullable=True)

def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.alter_column('idempotency_key',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=128),
               existing_nullable=True)
        batch_op.alter_column('feat_code',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=50),
               existing_nullable=True)
        batch_op.alter_column('correlation_id',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=36),
               existing_nullable=True)
