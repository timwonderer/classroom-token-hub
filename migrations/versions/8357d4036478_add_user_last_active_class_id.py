"""add user last_active_class_id

Revision ID: 8357d4036478
Revises: 53e7c7148fea
Create Date: 2026-05-12 04:59:14.513302

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8357d4036478'
down_revision = '53e7c7148fea'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    inspector = sa.inspect(op.get_bind())
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def index_exists(table_name, index_name):
    inspector = sa.inspect(op.get_bind())
    return index_name in [index["name"] for index in inspector.get_indexes(table_name)]


def foreign_key_exists(table_name, fk_name):
    inspector = sa.inspect(op.get_bind())
    return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table_name)]


def get_foreign_keys_by_column(table_name, column_name):
    inspector = sa.inspect(op.get_bind())
    return [
        fk
        for fk in inspector.get_foreign_keys(table_name)
        if column_name in fk["constrained_columns"]
    ]


def upgrade():
    if not column_exists('users', 'last_active_class_id'):
        op.add_column('users', sa.Column('last_active_class_id', sa.String(length=36), nullable=True))
    if not index_exists('users', 'ix_users_last_active_class_id'):
        op.create_index('ix_users_last_active_class_id', 'users', ['last_active_class_id'], unique=False)
    if not foreign_key_exists('users', 'fk_users_last_active_class_id_classes'):
        op.create_foreign_key(
            'fk_users_last_active_class_id_classes',
            'users',
            'classes',
            ['last_active_class_id'],
            ['class_id'],
            ondelete='SET NULL',
        )


def downgrade():
    for fk in get_foreign_keys_by_column('users', 'last_active_class_id'):
        op.drop_constraint(fk['name'], 'users', type_='foreignkey')
    if index_exists('users', 'ix_users_last_active_class_id'):
        op.drop_index('ix_users_last_active_class_id', table_name='users')
    if column_exists('users', 'last_active_class_id'):
        op.drop_column('users', 'last_active_class_id')
