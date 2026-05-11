"""Add lineage fields to transaction table

Revision ID: 53e7c7148fea
Revises: 3447255cb1af
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '53e7c7148fea'
down_revision = '3447255cb1af'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # lineage_event_id — FK to audit_events; nullable (pre-rollout rows are UNVERIFIED)
    if not column_exists('transaction', 'lineage_event_id'):
        with op.batch_alter_table('transaction') as batch_op:
            batch_op.add_column(sa.Column('lineage_event_id', sa.Integer(), nullable=True))
        print("✅ Added lineage_event_id to transaction")
    else:
        print("⚠️  lineage_event_id already exists on transaction, skipping...")

    if not foreign_key_exists('transaction', 'fk_transaction_lineage_event_id'):
        with op.batch_alter_table('transaction') as batch_op:
            batch_op.create_foreign_key(
                'fk_transaction_lineage_event_id',
                'audit_events',
                ['lineage_event_id'],
                ['id'],
            )
        print("✅ Added FK fk_transaction_lineage_event_id")

    if not index_exists('transaction', 'ix_transaction_lineage_event_id'):
        op.create_index('ix_transaction_lineage_event_id', 'transaction', ['lineage_event_id'])

    # lineage_token — fast provenance pointer (copy of AuditEvent.hmac_signature)
    if not column_exists('transaction', 'lineage_token'):
        with op.batch_alter_table('transaction') as batch_op:
            batch_op.add_column(sa.Column('lineage_token', sa.String(length=64), nullable=True))
        print("✅ Added lineage_token to transaction")

    # lineage_version — signing algorithm version for future rotation
    if not column_exists('transaction', 'lineage_version'):
        with op.batch_alter_table('transaction') as batch_op:
            batch_op.add_column(sa.Column('lineage_version', sa.Integer(), nullable=True))
        print("✅ Added lineage_version to transaction")


def downgrade():
    for fk in get_foreign_keys_by_column('transaction', 'lineage_event_id'):
        with op.batch_alter_table('transaction') as batch_op:
            batch_op.drop_constraint(fk['name'], type_='foreignkey')

    if index_exists('transaction', 'ix_transaction_lineage_event_id'):
        op.drop_index('ix_transaction_lineage_event_id', table_name='transaction')

    for col in ('lineage_version', 'lineage_token', 'lineage_event_id'):
        if column_exists('transaction', col):
            with op.batch_alter_table('transaction') as batch_op:
                batch_op.drop_column(col)
            print(f"❌ Dropped {col} from transaction")
