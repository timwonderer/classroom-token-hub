"""Minimize claim PII persistence and remove archive columns.

Revision ID: a9b8c7d6e5f4
Revises: z2a3b4c5d6e7
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9b8c7d6e5f4'
down_revision = 'b33ed424ad95'
branch_labels = None
depends_on = None


def _drop_column_if_exists(table_name: str, column_name: str):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    if column_name in cols:
        op.drop_column(table_name, column_name)


def _add_column_if_missing(table_name: str, column: sa.Column):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    if column.name not in cols:
        op.add_column(table_name, column)


def upgrade():
    _drop_column_if_exists('students', 'dob_sum')
    _drop_column_if_exists('students', 'last_name_hash_by_part')
    _drop_column_if_exists('students', 'is_active')

    _drop_column_if_exists('join_codes', 'is_archived')
    _drop_column_if_exists('join_codes', 'is_expired')
    _drop_column_if_exists('join_codes', 'expires_at')
    _drop_column_if_exists('join_codes', 'archived_at')


def downgrade():
    _add_column_if_missing('students', sa.Column('dob_sum', sa.Integer(), nullable=True))
    _add_column_if_missing('students', sa.Column('last_name_hash_by_part', sa.JSON(), nullable=True))
    _add_column_if_missing('students', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))

    _add_column_if_missing('join_codes', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    _add_column_if_missing('join_codes', sa.Column('is_expired', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    _add_column_if_missing('join_codes', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing('join_codes', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
