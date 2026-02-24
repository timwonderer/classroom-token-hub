"""add sysadmin username hashing

Revision ID: c1d2e3f4a5b7
Revises: b9c8d7e6f5a4
Create Date: 2026-02-24 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b7'
down_revision = 'b9c8d7e6f5a4'
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


def upgrade():
    if not table_exists('system_admins'):
        return

    with op.batch_alter_table('system_admins', schema=None) as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(length=80), nullable=True)

    if not column_exists('system_admins', 'username_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('username_hash', sa.String(length=64), nullable=True))

    if not column_exists('system_admins', 'username_lookup_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('username_lookup_hash', sa.String(length=64), nullable=True))

    if not column_exists('system_admins', 'salt'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('salt', sa.LargeBinary(length=16), nullable=True))

    if not index_exists('system_admins', 'ix_system_admins_username_lookup_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.create_index('ix_system_admins_username_lookup_hash', ['username_lookup_hash'], unique=True)


def downgrade():
    if not table_exists('system_admins'):
        return

    if index_exists('system_admins', 'ix_system_admins_username_lookup_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.drop_index('ix_system_admins_username_lookup_hash')

    if column_exists('system_admins', 'salt'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.drop_column('salt')

    if column_exists('system_admins', 'username_lookup_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.drop_column('username_lookup_hash')

    if column_exists('system_admins', 'username_hash'):
        with op.batch_alter_table('system_admins', schema=None) as batch_op:
            batch_op.drop_column('username_hash')
