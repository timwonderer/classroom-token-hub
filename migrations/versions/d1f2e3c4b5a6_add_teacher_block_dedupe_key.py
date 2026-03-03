"""Add dedupe_key to teacher_blocks for class-scoped roster deduplication.

Revision ID: d1f2e3c4b5a6
Revises: b8c9d0e1f2a3
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1f2e3c4b5a6'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('teacher_blocks')}

    if 'dedupe_key' not in cols:
        op.add_column('teacher_blocks', sa.Column('dedupe_key', sa.String(length=64), nullable=True))
        op.create_index('ix_teacher_blocks_dedupe_key', 'teacher_blocks', ['dedupe_key'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('teacher_blocks')}
    indexes = {i['name'] for i in inspector.get_indexes('teacher_blocks')}

    if 'ix_teacher_blocks_dedupe_key' in indexes:
        op.drop_index('ix_teacher_blocks_dedupe_key', table_name='teacher_blocks')

    if 'dedupe_key' in cols:
        op.drop_column('teacher_blocks', 'dedupe_key')
