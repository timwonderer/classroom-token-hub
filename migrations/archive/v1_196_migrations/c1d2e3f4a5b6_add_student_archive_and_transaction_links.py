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


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if not column_exists('students', 'is_active'):
        op.add_column('students', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        print("  Added is_active column to students")
    else:
        print("  Column 'is_active' already exists on 'students', skipping...")

    if not index_exists('students', 'ix_students_is_active'):
        op.create_index(op.f('ix_students_is_active'), 'students', ['is_active'], unique=False)
        print("  Created ix_students_is_active index")
    else:
        print("  Index 'ix_students_is_active' already exists, skipping...")

    if not column_exists('transaction', 'original_transaction_id'):
        op.add_column('transaction', sa.Column('original_transaction_id', sa.Integer(), nullable=True))
        print("  Added original_transaction_id column to transaction")
    else:
        print("  Column 'original_transaction_id' already exists on 'transaction', skipping...")

    if not column_exists('transaction', 'reversal_transaction_id'):
        op.add_column('transaction', sa.Column('reversal_transaction_id', sa.Integer(), nullable=True))
        print("  Added reversal_transaction_id column to transaction")
    else:
        print("  Column 'reversal_transaction_id' already exists on 'transaction', skipping...")

    if not index_exists('transaction', 'ix_transaction_original_transaction_id'):
        op.create_index(op.f('ix_transaction_original_transaction_id'), 'transaction', ['original_transaction_id'], unique=False)
        print("  Created ix_transaction_original_transaction_id index")
    else:
        print("  Index 'ix_transaction_original_transaction_id' already exists, skipping...")

    if not index_exists('transaction', 'ix_transaction_reversal_transaction_id'):
        op.create_index(op.f('ix_transaction_reversal_transaction_id'), 'transaction', ['reversal_transaction_id'], unique=False)
        print("  Created ix_transaction_reversal_transaction_id index")
    else:
        print("  Index 'ix_transaction_reversal_transaction_id' already exists, skipping...")


def downgrade():
    if index_exists('transaction', 'ix_transaction_reversal_transaction_id'):
        op.drop_index(op.f('ix_transaction_reversal_transaction_id'), table_name='transaction')
    if index_exists('transaction', 'ix_transaction_original_transaction_id'):
        op.drop_index(op.f('ix_transaction_original_transaction_id'), table_name='transaction')
    if column_exists('transaction', 'reversal_transaction_id'):
        op.drop_column('transaction', 'reversal_transaction_id')
    if column_exists('transaction', 'original_transaction_id'):
        op.drop_column('transaction', 'original_transaction_id')

    if index_exists('students', 'ix_students_is_active'):
        op.drop_index(op.f('ix_students_is_active'), table_name='students')
    if column_exists('students', 'is_active'):
        op.drop_column('students', 'is_active')
