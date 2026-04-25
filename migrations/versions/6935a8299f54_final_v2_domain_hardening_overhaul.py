"""Final V2 Domain Hardening Overhaul

Revision ID: 6935a8299f54
Revises: 2abbf488403b
Create Date: 2026-04-24 23:45:24.713844

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
revision = '6935a8299f54'
down_revision = '2abbf488403b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Prepare class_economies for PK change
    
    # 2. Fix class_economies PK and columns
    with op.batch_alter_table('class_economies', schema=None) as batch_op:
        batch_op.alter_column('class_timezone',
               existing_type=sa.VARCHAR(length=64),
               nullable=False,
               server_default='UTC')
    
    # Manually swap PK in Postgres
    op.execute("ALTER TABLE class_economies DROP CONSTRAINT IF EXISTS class_economies_pkey CASCADE")
    op.execute("ALTER TABLE class_economies ADD PRIMARY KEY (class_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_class_economies_join_code ON class_economies (join_code)")

    # 3. Handle activity tables with backfill
    
    # --- Rent Payments ---
    op.add_column('rent_payments', sa.Column('class_id', sa.String(length=36), nullable=True))
    op.execute("""
        UPDATE rent_payments rp
        SET class_id = (SELECT ce.class_id FROM class_economies ce WHERE ce.join_code = rp.join_code)
        WHERE rp.class_id IS NULL AND rp.join_code IS NOT NULL
    """)
    with op.batch_alter_table('rent_payments', schema=None) as batch_op:
        batch_op.alter_column('student_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('seat_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('class_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.create_index(batch_op.f('ix_rent_payments_class_id'), ['class_id'], unique=False)
        # Safely drop existing FK on seat_id before recreating with CASCADE
        for fk in get_foreign_keys_by_column('rent_payments', 'seat_id'):
            batch_op.drop_constraint(fk['name'], type_='foreignkey')
        batch_op.create_foreign_key('rent_payments_class_id_fkey', 'class_economies', ['class_id'], ['class_id'], ondelete='CASCADE')
        batch_op.create_foreign_key('rent_payments_seat_id_fkey', 'seats', ['seat_id'], ['id'], ondelete='CASCADE')

    # --- Student Insurance ---
    op.add_column('student_insurance', sa.Column('seat_id', sa.Integer(), nullable=True))
    op.add_column('student_insurance', sa.Column('class_id', sa.String(length=36), nullable=True))
    op.execute("""
        UPDATE student_insurance si
        SET class_id = (SELECT ce.class_id FROM class_economies ce WHERE ce.join_code = si.join_code),
            seat_id = (SELECT s.id FROM seats s WHERE s.student_id = si.student_id AND s.join_code = si.join_code LIMIT 1)
        WHERE si.class_id IS NULL
    """)
    with op.batch_alter_table('student_insurance', schema=None) as batch_op:
        batch_op.alter_column('student_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('seat_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('class_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.create_index(batch_op.f('ix_student_insurance_class_id'), ['class_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_student_insurance_seat_id'), ['seat_id'], unique=False)
        batch_op.create_foreign_key('student_insurance_class_id_fkey', 'class_economies', ['class_id'], ['class_id'], ondelete='CASCADE')
        batch_op.create_foreign_key('student_insurance_seat_id_fkey', 'seats', ['seat_id'], ['id'], ondelete='CASCADE')

    # --- Transactions ---
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.alter_column('student_id', existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column('seat_id', existing_type=sa.INTEGER(), nullable=False)
        for fk in get_foreign_keys_by_column('transaction', 'seat_id'):
            batch_op.drop_constraint(fk['name'], type_='foreignkey')
        batch_op.create_foreign_key('transaction_seat_id_fkey', 'seats', ['seat_id'], ['id'], ondelete='CASCADE')

    # --- Snapshots ---
    op.add_column('economy_snapshot', sa.Column('class_id', sa.String(length=36), nullable=True))
    op.execute("""
        UPDATE economy_snapshot es
        SET class_id = (SELECT ce.class_id FROM class_economies ce WHERE ce.join_code = es.join_code)
        WHERE es.class_id IS NULL
    """)
    with op.batch_alter_table('economy_snapshot', schema=None) as batch_op:
        batch_op.alter_column('class_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('join_code', existing_type=sa.VARCHAR(length=20), nullable=True)
        batch_op.create_index(batch_op.f('ix_economy_snapshot_class_id'), ['class_id'], unique=False)
        for fk in get_foreign_keys_by_column('economy_snapshot', 'join_code'):
            batch_op.drop_constraint(fk['name'], type_='foreignkey')
        batch_op.create_foreign_key('economy_snapshot_class_id_fkey', 'class_economies', ['class_id'], ['class_id'], ondelete='CASCADE')

    # --- Memberships ---
    op.add_column('class_memberships', sa.Column('class_id', sa.String(length=36), nullable=True))
    op.execute("""
        UPDATE class_memberships cm
        SET class_id = (SELECT ce.class_id FROM class_economies ce WHERE ce.join_code = cm.join_code)
        WHERE cm.class_id IS NULL
    """)
    with op.batch_alter_table('class_memberships', schema=None) as batch_op:
        batch_op.alter_column('join_code', existing_type=sa.VARCHAR(length=20), nullable=True)
        batch_op.create_index(batch_op.f('ix_class_memberships_class_id'), ['class_id'], unique=False)
        for fk in get_foreign_keys_by_column('class_memberships', 'join_code'):
            batch_op.drop_constraint(fk['name'], type_='foreignkey')
        batch_op.create_foreign_key('class_memberships_class_id_fkey', 'class_economies', ['class_id'], ['class_id'], ondelete='CASCADE')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('transaction_seat_id_fkey'), 'seats', ['seat_id'], ['id'], ondelete='SET NULL')
        batch_op.alter_column('seat_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('student_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    with op.batch_alter_table('student_insurance', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_student_insurance_seat_id'))
        batch_op.drop_index(batch_op.f('ix_student_insurance_class_id'))
        batch_op.alter_column('student_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('class_id')
        batch_op.drop_column('seat_id')

    with op.batch_alter_table('rent_payments', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('rent_payments_seat_id_fkey'), 'seats', ['seat_id'], ['id'], ondelete='SET NULL')
        batch_op.drop_index(batch_op.f('ix_rent_payments_class_id'))
        batch_op.alter_column('seat_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('student_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('class_id')

    with op.batch_alter_table('economy_snapshot', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('economy_snapshot_join_code_fkey'), 'class_economies', ['join_code'], ['join_code'], ondelete='CASCADE')
        batch_op.drop_index(batch_op.f('ix_economy_snapshot_class_id'))
        batch_op.alter_column('join_code',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
        batch_op.drop_column('class_id')

    with op.batch_alter_table('class_memberships', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('class_memberships_join_code_fkey'), 'class_economies', ['join_code'], ['join_code'], ondelete='CASCADE')
        batch_op.drop_index(batch_op.f('ix_class_memberships_class_id'))
        batch_op.alter_column('join_code',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
        batch_op.drop_column('class_id')

    with op.batch_alter_table('class_economies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_class_economies_join_code'))
        batch_op.create_index(batch_op.f('ix_class_economies_class_id'), ['class_id'], unique=True)
        batch_op.alter_column('class_timezone',
               existing_type=sa.VARCHAR(length=64),
               nullable=True)

    # ### end Alembic commands ###
