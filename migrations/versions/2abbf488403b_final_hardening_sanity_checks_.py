"""Final hardening sanity checks: idempotency scope and student_item correlation

Revision ID: 2abbf488403b
Revises: 64ff042b3677
Create Date: 2026-04-24 18:40:34.155581

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

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

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
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

# revision identifiers, used by Alembic.
revision = '2abbf488403b'
down_revision = '64ff042b3677'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Backfill StudentItem correlation_id
    op.execute("UPDATE student_items SET correlation_id = 'legacy_si_' || id WHERE correlation_id IS NULL")

    # 2. Make StudentItem correlation_id NOT NULL
    with op.batch_alter_table('student_items', schema=None) as batch_op:
        batch_op.alter_column('correlation_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)

    # 3. Refine Transaction idempotency scope
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_index('uq_transaction_idempotency_scope')
        batch_op.create_index(
            'uq_transaction_idempotency_scope', 
            ['class_id', 'seat_id', 'feat_code', 'idempotency_key', 'type'], 
            unique=True, 
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        )


def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_index('uq_transaction_idempotency_scope')
        batch_op.create_index(
            'uq_transaction_idempotency_scope', 
            ['class_id', 'student_id', 'seat_id', 'feat_code', 'idempotency_key', 'type'], 
            unique=True, 
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        )

    with op.batch_alter_table('student_items', schema=None) as batch_op:
        batch_op.alter_column('correlation_id',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)

