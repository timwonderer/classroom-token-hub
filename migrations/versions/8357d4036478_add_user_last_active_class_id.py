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


def upgrade():
    op.add_column('users', sa.Column('last_active_class_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_users_last_active_class_id'), 'users', ['last_active_class_id'], unique=False)
    op.create_foreign_key(
        'fk_users_last_active_class_id_classes',
        'users',
        'classes',
        ['last_active_class_id'],
        ['class_id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_users_last_active_class_id_classes', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_last_active_class_id'), table_name='users')
    op.drop_column('users', 'last_active_class_id')
