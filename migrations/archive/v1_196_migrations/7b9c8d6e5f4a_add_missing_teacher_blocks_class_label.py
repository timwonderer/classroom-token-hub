"""add missing teacher_blocks.class_label on fresh rebuilds

Revision ID: 7b9c8d6e5f4a
Revises: f6c7d8e9a0b1
Create Date: 2026-02-14 05:05:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "7b9c8d6e5f4a"
down_revision = "f6c7d8e9a0b1"
branch_labels = None
depends_on = None


def upgrade():
    # Earlier migration 2060c104e884 no-ops this column add.
    # Ensure fresh databases have the model-required column.
    op.execute(
        "ALTER TABLE teacher_blocks "
        "ADD COLUMN IF NOT EXISTS class_label VARCHAR(50)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE teacher_blocks "
        "DROP COLUMN IF EXISTS class_label"
    )

