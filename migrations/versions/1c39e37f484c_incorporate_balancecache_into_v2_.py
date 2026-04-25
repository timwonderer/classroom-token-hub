"""Incorporate BalanceCache into V2 Overhaul

Revision ID: 1c39e37f484c
Revises: 6935a8299f54
Create Date: 2026-04-24 23:47:16.950533

"""
from alembic import op
import sqlalchemy as sa


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
revision = '1c39e37f484c'
down_revision = '6935a8299f54'
branch_labels = None
depends_on = None


def upgrade():
    # --- Balance Cache ---
    if not column_exists('balance_cache', 'class_id'):
        op.add_column('balance_cache', sa.Column('class_id', sa.String(length=36), nullable=True))
    op.execute("""
        UPDATE balance_cache bc
        SET class_id = (SELECT ce.class_id FROM class_economies ce WHERE ce.join_code = bc.join_code)
        WHERE bc.class_id IS NULL
    """)
    with op.batch_alter_table('balance_cache', schema=None) as batch_op:
        batch_op.alter_column('student_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('seat_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('class_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('join_code', existing_type=sa.VARCHAR(length=20), nullable=True)
        
        # Safely drop existing unique constraints
        # Constraint names might vary, so we use drop_constraint with known names from models
        op.execute("ALTER TABLE balance_cache DROP CONSTRAINT IF EXISTS uq_balance_cache_scope")
        op.execute("ALTER TABLE balance_cache DROP CONSTRAINT IF EXISTS uq_balance_cache_seat_scope")
        
        if not index_exists('balance_cache', 'ix_balance_cache_class_id'):
            batch_op.create_index(batch_op.f('ix_balance_cache_class_id'), ['class_id'], unique=False)
        
        # Check if unique constraint exists before adding
        # We need a helper for unique constraints.
        # inspector.get_unique_constraints doesn't always show them if they are part of create_table.
        # But we can use raw SQL if needed.
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_balance_cache_seat_universe') THEN
                    ALTER TABLE balance_cache ADD CONSTRAINT uq_balance_cache_seat_universe UNIQUE (class_id, seat_id);
                END IF;
            END
            $$;
        """)
        
        # Safely drop existing FK on seat_id
        for fk in get_foreign_keys_by_column('balance_cache', 'seat_id'):
            batch_op.drop_constraint(fk['name'], type_='foreignkey')
        batch_op.create_foreign_key('balance_cache_seat_id_fkey', 'seats', ['seat_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('balance_cache_class_id_fkey', 'class_economies', ['class_id'], ['class_id'], ondelete='CASCADE')

    # with op.batch_alter_table('class_economies', schema=None) as batch_op:
    #     # The index ix_class_economies_class_id might have been dropped by Postgres CASCADE in previous migration.
    #     # Check if it exists before dropping.
    #     if index_exists('class_economies', 'ix_class_economies_class_id'):
    #         batch_op.drop_index('ix_class_economies_class_id')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('class_economies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_class_economies_class_id'), ['class_id'], unique=True)

    with op.batch_alter_table('balance_cache', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('balance_cache_seat_id_fkey'), 'seats', ['seat_id'], ['id'], ondelete='SET NULL')
        batch_op.drop_constraint('uq_balance_cache_seat_universe', type_='unique')
        batch_op.drop_index(batch_op.f('ix_balance_cache_class_id'))
        batch_op.create_unique_constraint(batch_op.f('uq_balance_cache_seat_scope'), ['join_code', 'seat_id'], postgresql_nulls_not_distinct=False)
        batch_op.create_unique_constraint(batch_op.f('uq_balance_cache_scope'), ['join_code', 'student_id'], postgresql_nulls_not_distinct=False)
        batch_op.alter_column('join_code',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
        batch_op.alter_column('seat_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('student_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('class_id')

    # ### end Alembic commands ###
