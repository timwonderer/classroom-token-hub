"""Add Ledger and Settlement models

Revision ID: ec84c1f59c15
Revises: 7ad546acf3bd
Create Date: 2026-02-14 22:06:42.429358

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

def enum_exists(enum_name):
    """Check if a postgres enum type exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"SELECT 1 FROM pg_type WHERE typname = '{enum_name}'"))
    return result.fetchone() is not None

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = 'ec84c1f59c15'
down_revision = '7ad546acf3bd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands manually adjusted to remove accidental drops ###
    bind = op.get_bind()
    
    # 1. Create BalanceCache table
    if not table_exists('balance_cache'):
        op.create_table('balance_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('join_code', sa.String(length=20), nullable=False),
        sa.Column('posted_checking_balance_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posted_savings_balance_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_settlement_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('join_code', 'student_id', name='uq_balance_cache_scope')
        )

    # 2. Update Transaction table schema
    # Create Enum type explicitly for Postgres (UPPERCASE for SQLAlchemy compatibility)
    if not enum_exists('transactionstatus'):
        transaction_status_enum = sa.Enum('PENDING', 'POSTED', 'VOID', name='transactionstatus')
        try:
            transaction_status_enum.create(bind)
        except Exception:
            pass

    with op.batch_alter_table('transaction', schema=None) as batch_op:
        if not column_exists('transaction', 'status'):
            # Default to 'POSTED' (uppercase)
            batch_op.add_column(sa.Column('status', sa.Enum('PENDING', 'POSTED', 'VOID', name='transactionstatus'), server_default='POSTED', nullable=False))
        if not column_exists('transaction', 'amount_cents'):
            batch_op.add_column(sa.Column('amount_cents', sa.Integer(), nullable=True))
        if not column_exists('transaction', 'posted_at'):
            batch_op.add_column(sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True))
        if not column_exists('transaction', 'voided_at'):
            batch_op.add_column(sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True))
        if not column_exists('transaction', 'effective_at'):
            batch_op.add_column(sa.Column('effective_at', sa.DateTime(timezone=True), nullable=True))
        
        # Add new indexes
        if not index_exists('transaction', 'ix_transaction_ledger_scope'):
            batch_op.create_index('ix_transaction_ledger_scope', ['join_code', 'student_id', 'status', 'account_type'], unique=False)
        if not index_exists('transaction', 'ix_transaction_student_ledger'):
            batch_op.create_index('ix_transaction_student_ledger', ['join_code', 'student_id'], unique=False)

    # 3. Data Migration (Backfill)
    # ---------------------------------------------------------
    # Backfill Transaction Columns
    
    # amount_cents = amount * 100
    op.execute("UPDATE transaction SET amount_cents = CAST(amount * 100 AS INTEGER) WHERE amount_cents IS NULL")

    with op.batch_alter_table('transaction', schema=None) as batch_op:
        if column_exists('transaction', 'amount_cents'):
            batch_op.alter_column('amount_cents', existing_type=sa.Integer(), nullable=False)
    
    # posted_at = timestamp (since all current ones are posted)
    op.execute("UPDATE transaction SET posted_at = timestamp WHERE posted_at IS NULL")
    
    # effective_at = timestamp
    op.execute("UPDATE transaction SET effective_at = timestamp WHERE effective_at IS NULL")
    
    # status is already defaulted to 'POSTED' by server_default
    
    # Populate Initial BalanceCache
    if table_exists('balance_cache') and not column_exists('balance_cache', 'class_id'):
        try:
            op.execute("""
                INSERT INTO balance_cache (
                    student_id,
                    join_code,
                    posted_checking_balance_cents,
                    posted_savings_balance_cents,
                    last_settlement_at,
                    updated_at
                )
                SELECT
                    student_id,
                    join_code,
                    COALESCE(SUM(CASE WHEN account_type = 'checking' THEN CAST(amount * 100 AS INTEGER) ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN account_type = 'savings' THEN CAST(amount * 100 AS INTEGER) ELSE 0 END), 0),
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM transaction
                WHERE is_void = FALSE
                  AND join_code IS NOT NULL
                GROUP BY student_id, join_code
                ON CONFLICT (join_code, student_id) DO NOTHING
            """)
        except Exception:
            pass
    # ---------------------------------------------------------


def downgrade():
    # ### commands manually adjusted ###
    bind = op.get_bind()
    if table_exists('transaction'):
        with op.batch_alter_table('transaction', schema=None) as batch_op:
            if index_exists('transaction', 'ix_transaction_student_ledger'):
                batch_op.drop_index('ix_transaction_student_ledger')
            if index_exists('transaction', 'ix_transaction_ledger_scope'):
                batch_op.drop_index('ix_transaction_ledger_scope')
            if column_exists('transaction', 'effective_at'):
                batch_op.drop_column('effective_at')
            if column_exists('transaction', 'voided_at'):
                batch_op.drop_column('voided_at')
            if column_exists('transaction', 'posted_at'):
                batch_op.drop_column('posted_at')
            if column_exists('transaction', 'amount_cents'):
                batch_op.drop_column('amount_cents')
            if column_exists('transaction', 'status'):
                batch_op.drop_column('status')
        
    # Drop Enum type (using UPPERCASE per upgrade definition)
    transaction_status_enum = sa.Enum('PENDING', 'POSTED', 'VOID', name='transactionstatus')
    try:
        transaction_status_enum.drop(bind)
    except Exception:
        pass
        
    if table_exists('balance_cache'):
        op.drop_table('balance_cache')
