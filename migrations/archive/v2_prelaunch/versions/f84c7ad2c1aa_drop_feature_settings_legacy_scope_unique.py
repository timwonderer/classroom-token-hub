"""drop feature_settings legacy scope unique

Revision ID: f84c7ad2c1aa
Revises: d2f9f1d9be2e
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f84c7ad2c1aa"
down_revision = "d2f9f1d9be2e"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def unique_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [constraint["name"] for constraint in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def upgrade():
    if table_exists("feature_settings") and unique_constraint_exists(
        "feature_settings",
        "uq_feature_settings_teacher_join_code_block",
    ):
        with op.batch_alter_table("feature_settings", schema=None) as batch_op:
            batch_op.drop_constraint("uq_feature_settings_teacher_join_code_block", type_="unique")


def downgrade():
    if table_exists("feature_settings") and not unique_constraint_exists(
        "feature_settings",
        "uq_feature_settings_teacher_join_code_block",
    ):
        with op.batch_alter_table("feature_settings", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_feature_settings_teacher_join_code_block",
                ["teacher_id", "join_code", "block"],
            )
