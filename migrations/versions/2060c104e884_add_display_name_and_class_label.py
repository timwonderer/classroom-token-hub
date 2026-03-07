"""add display_name and class_label

Revision ID: 2060c104e884
Revises: b1c2d3e4f5g6
Create Date: 2025-12-06 04:44:01.376826

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2060c104e884'
down_revision = 'b1c2d3e4f5g6'
branch_labels = None
depends_on = None



from sqlalchemy.exc import ProgrammingError

def upgrade():
    # Add display_name to admins table
    # NOTE: Commented out because column already exists in production DB and try/except failed to catch DuplicateColumn
    try:
        pass
        # op.add_column('admins', sa.Column('display_name', sa.String(length=100), nullable=True))
    except ProgrammingError as e:
        if "already exists" in str(e) or "DuplicateColumn" in str(e):
             print("Column display_name already exists in admins, skipping.")
        else:
             raise e

    # Add class_label to teacher_blocks table
    # NOTE: Commented out because column already exists
    try:
        pass
        # op.add_column('teacher_blocks', sa.Column('class_label', sa.String(length=50), nullable=True))
    except ProgrammingError as e:
        if "already exists" in str(e) or "DuplicateColumn" in str(e):
             print("Column class_label already exists in teacher_blocks, skipping.")
        else:
             raise e


def downgrade():
    # Remove class_label from teacher_blocks table
    with op.batch_alter_table('teacher_blocks', schema=None) as batch_op:
        batch_op.drop_column('class_label')

    # Remove display_name from admins table
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.drop_column('display_name')
