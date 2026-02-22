"""Make TeacherBlock dob_sum and last_name_hash_by_part nullable for post-claim cleanup

Revision ID: b7c8d9e0f1a2
Revises: z2a3b4c5d6e7
Create Date: 2026-02-22 00:00:00.000000

After a student successfully claims their account and completes setup, dob_sum and
last_name_hash_by_part are no longer needed on either the TeacherBlock seat or the
Student record. This migration makes those two columns on teacher_blocks nullable so
that the application can null them out as part of post-claim PII cleanup.

Student.dob_sum and Student.last_name_hash_by_part are already nullable (no migration
needed there).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    # Make dob_sum nullable on teacher_blocks
    op.alter_column(
        'teacher_blocks', 'dob_sum',
        existing_type=sa.Integer(),
        nullable=True
    )

    # Make last_name_hash_by_part nullable on teacher_blocks
    op.alter_column(
        'teacher_blocks', 'last_name_hash_by_part',
        existing_type=sa.JSON(),
        nullable=True
    )


def downgrade():
    # Restore dob_sum to NOT NULL, backfill with 0 for any NULLs
    op.execute("UPDATE teacher_blocks SET dob_sum = 0 WHERE dob_sum IS NULL")
    op.alter_column(
        'teacher_blocks', 'dob_sum',
        existing_type=sa.Integer(),
        nullable=False
    )

    # Restore last_name_hash_by_part to NOT NULL, backfill with empty JSON array
    op.execute(
        "UPDATE teacher_blocks SET last_name_hash_by_part = '[]'::json "
        "WHERE last_name_hash_by_part IS NULL"
    )
    op.alter_column(
        'teacher_blocks', 'last_name_hash_by_part',
        existing_type=sa.JSON(),
        nullable=False
    )
