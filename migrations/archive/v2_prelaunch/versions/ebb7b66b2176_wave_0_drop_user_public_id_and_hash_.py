"""Wave 0: Drop User.public_id and hash username

Revision ID: ebb7b66b2176
Revises: e4a2b7c9d1f0
Create Date: 2026-06-01 04:54:55.324895

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

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = 'ebb7b66b2176'
down_revision = 'e4a2b7c9d1f0'
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists('users', 'username_hash'):
        op.add_column('users', sa.Column('username_hash', sa.String(length=64), nullable=True))
    
    if column_exists('users', 'username'):
        op.execute("UPDATE users SET username_hash = username WHERE username_hash IS NULL")
    
    if index_exists('users', 'ix_users_username'):
        op.drop_index(op.f('ix_users_username'), table_name='users')
        
    if column_exists('users', 'username'):
        op.drop_column('users', 'username')

    if index_exists('users', 'ix_users_public_id'):
        op.drop_index(op.f('ix_users_public_id'), table_name='users')
        
    if column_exists('users', 'public_id'):
        op.drop_column('users', 'public_id')
        
    # Make username_hash non-nullable and indexed
    op.alter_column('users', 'username_hash', nullable=False)
    if not index_exists('users', 'ix_users_username_hash'):
        op.create_index(op.f('ix_users_username_hash'), 'users', ['username_hash'], unique=True)


def downgrade():
    if not column_exists('users', 'username'):
        op.add_column('users', sa.Column('username', sa.String(length=255), nullable=True))
        
    op.execute("UPDATE users SET username = username_hash WHERE username IS NULL")
        
    if not column_exists('users', 'public_id'):
        op.add_column('users', sa.Column('public_id', sa.String(length=36), nullable=True))
        
    op.execute("UPDATE users SET public_id = gen_random_uuid()::text WHERE public_id IS NULL")
        
    if index_exists('users', 'ix_users_username_hash'):
        op.drop_index(op.f('ix_users_username_hash'), table_name='users')
        
    if column_exists('users', 'username_hash'):
        op.drop_column('users', 'username_hash')
        
    op.alter_column('users', 'username', nullable=False)
    if not index_exists('users', 'ix_users_username'):
        op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
        
    op.alter_column('users', 'public_id', nullable=False)
    if not index_exists('users', 'ix_users_public_id'):
        op.create_index(op.f('ix_users_public_id'), 'users', ['public_id'], unique=True)
