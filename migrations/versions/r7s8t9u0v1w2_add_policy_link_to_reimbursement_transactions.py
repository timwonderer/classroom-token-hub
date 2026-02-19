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


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk.get('name') for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    if not table_exists('transaction'):
        return

    if not column_exists('transaction', 'original_transaction_id'):
        op.add_column('transaction', sa.Column('original_transaction_id', sa.Integer(), nullable=True))

    if not index_exists('transaction', 'ix_transaction_original_transaction_id'):
        op.create_index('ix_transaction_original_transaction_id', 'transaction', ['original_transaction_id'], unique=False)

    if not column_exists('transaction', 'policy_id'):
        op.add_column('transaction', sa.Column('policy_id', sa.Integer(), nullable=True))

    if not index_exists('transaction', 'ix_transaction_policy_id'):
        op.create_index('ix_transaction_policy_id', 'transaction', ['policy_id'], unique=False)

    if not foreign_key_exists('transaction', 'fk_transaction_policy_id_insurance_policies'):
        op.create_foreign_key(
            'fk_transaction_policy_id_insurance_policies',
            'transaction',
            'insurance_policies',
            ['policy_id'],
            ['id'],
        )

    if not index_exists('transaction', 'uq_insurance_reimbursement_source_policy'):
        op.create_index(
            'uq_insurance_reimbursement_source_policy',
            'transaction',
            ['original_transaction_id', 'policy_id'],
            unique=True,
            postgresql_where=sa.text(
                "type = 'insurance_reimbursement' AND original_transaction_id IS NOT NULL AND policy_id IS NOT NULL"
            ),
        )


def downgrade():
    if not table_exists('transaction'):
        return

    if index_exists('transaction', 'uq_insurance_reimbursement_source_policy'):
        op.drop_index('uq_insurance_reimbursement_source_policy', table_name='transaction')

    if foreign_key_exists('transaction', 'fk_transaction_policy_id_insurance_policies'):
        op.drop_constraint('fk_transaction_policy_id_insurance_policies', 'transaction', type_='foreignkey')

    if index_exists('transaction', 'ix_transaction_policy_id'):
        op.drop_index('ix_transaction_policy_id', table_name='transaction')

    if column_exists('transaction', 'policy_id'):
        op.drop_column('transaction', 'policy_id')
