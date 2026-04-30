"""Add immutable class timezone to class economies

Revision ID: t1u2v3w4x5y6
Revises: 982dca62e8b2
Create Date: 2026-04-21 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "t1u2v3w4x5y6"
down_revision = "982dca62e8b2"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    if not _column_exists("class_economies", "class_timezone"):
        with op.batch_alter_table("class_economies", schema=None) as batch_op:
            batch_op.add_column(sa.Column("class_timezone", sa.String(length=64), nullable=True))


def downgrade():
    if _column_exists("class_economies", "class_timezone"):
        with op.batch_alter_table("class_economies", schema=None) as batch_op:
            batch_op.drop_column("class_timezone")
