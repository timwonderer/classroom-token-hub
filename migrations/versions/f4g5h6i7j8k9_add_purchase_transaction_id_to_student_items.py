"""Add purchase_transaction_id to student_items

Revision ID: f4g5h6i7j8k9
Revises: e3f4g5h6i7j8
Create Date: 2026-02-27 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4g5h6i7j8k9'
down_revision = 'e3f4g5h6i7j8'
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


def upgrade():
    if not column_exists('student_items', 'purchase_transaction_id'):
        with op.batch_alter_table('student_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('purchase_transaction_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_student_items_purchase_transaction_id',
                'transaction',
                ['purchase_transaction_id'],
                ['id'],
            )
            batch_op.create_index(
                'ix_student_items_purchase_transaction_id',
                ['purchase_transaction_id'],
                unique=False,
            )


def downgrade():
    if column_exists('student_items', 'purchase_transaction_id'):
        with op.batch_alter_table('student_items', schema=None) as batch_op:
            batch_op.drop_index('ix_student_items_purchase_transaction_id')
            batch_op.drop_constraint('fk_student_items_purchase_transaction_id', type_='foreignkey')
            batch_op.drop_column('purchase_transaction_id')
