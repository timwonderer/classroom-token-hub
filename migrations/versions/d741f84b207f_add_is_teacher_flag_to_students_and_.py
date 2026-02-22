"""Add is_teacher flag to students and teacher_blocks

Revision ID: d741f84b207f
Revises: 6d78309c34c1
Create Date: 2026-02-20 08:12:31.142127

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd741f84b207f'
down_revision = '6d78309c34c1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_teacher', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    with op.batch_alter_table('teacher_blocks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_teacher', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade():
    with op.batch_alter_table('teacher_blocks', schema=None) as batch_op:
        batch_op.drop_column('is_teacher')

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('is_teacher')
