"""Drop dead metadata_json and hall pass pass_number columns

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-09 20:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _unique_constraint_names(table_name: str, column_name: str) -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return [
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if column_name in constraint.get("column_names", [])
    ]


def upgrade():
    if _column_exists("class_economies", "metadata_json"):
        with op.batch_alter_table("class_economies", schema=None) as batch_op:
            batch_op.drop_column("metadata_json")

    if _column_exists("hall_pass_logs", "pass_number"):
        for constraint_name in _unique_constraint_names("hall_pass_logs", "pass_number"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.drop_constraint(constraint_name, type_="unique")
        with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
            batch_op.drop_column("pass_number")


def downgrade():
    if not _column_exists("class_economies", "metadata_json"):
        with op.batch_alter_table("class_economies", schema=None) as batch_op:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))

    if not _column_exists("hall_pass_logs", "pass_number"):
        with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("pass_number", sa.String(length=3), nullable=True))
            batch_op.create_unique_constraint("uq_hall_pass_logs_pass_number", ["pass_number"])
