"""Enforce strict class scope for feature and hall-pass settings

Revision ID: l2m3n4o5p6q7
Revises: j0k1l2m3n4o5
Create Date: 2026-03-09 17:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "l2m3n4o5p6q7"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {uc["name"] for uc in inspector.get_unique_constraints(table_name)}


def foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists("feature_settings", "class_id"):
        with op.batch_alter_table("feature_settings") as batch_op:
            batch_op.add_column(sa.Column("class_id", sa.String(length=36), nullable=True))

    bind.execute(sa.text("""
        DELETE FROM feature_settings
        WHERE join_code IS NULL OR block IS NULL
    """))

    bind.execute(sa.text("""
        UPDATE feature_settings fs
        SET class_id = ce.class_id
        FROM class_economies ce
        WHERE fs.join_code = ce.join_code
          AND fs.class_id IS NULL
    """))

    with op.batch_alter_table("feature_settings") as batch_op:
        batch_op.alter_column("join_code", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("block", existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)

        if foreign_key_exists("feature_settings", "fk_feature_settings_class_id_class_economies"):
            batch_op.drop_constraint("fk_feature_settings_class_id_class_economies", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_feature_settings_class_id_class_economies",
            "class_economies",
            ["class_id"],
            ["class_id"],
            ondelete="CASCADE",
        )

        if unique_constraint_exists("feature_settings", "uq_feature_settings_teacher_block"):
            batch_op.drop_constraint("uq_feature_settings_teacher_block", type_="unique")
        if not unique_constraint_exists("feature_settings", "uq_feature_settings_teacher_join_code_block"):
            batch_op.create_unique_constraint(
                "uq_feature_settings_teacher_join_code_block",
                ["teacher_id", "join_code", "block"],
            )
        if not unique_constraint_exists("feature_settings", "uq_feature_settings_class_id"):
            batch_op.create_unique_constraint("uq_feature_settings_class_id", ["class_id"])

    bind.execute(sa.text("""
        DELETE FROM hall_pass_settings
        WHERE join_code IS NULL OR block IS NULL OR class_id IS NULL
    """))

    with op.batch_alter_table("hall_pass_settings") as batch_op:
        batch_op.alter_column("join_code", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("block", existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)
        if not unique_constraint_exists("hall_pass_settings", "uq_hall_pass_settings_class_id"):
            batch_op.create_unique_constraint("uq_hall_pass_settings_class_id", ["class_id"])

    if not index_exists("feature_settings", "ix_feature_settings_class_id"):
        op.create_index("ix_feature_settings_class_id", "feature_settings", ["class_id"], unique=False)


def downgrade() -> None:
    if index_exists("feature_settings", "ix_feature_settings_class_id"):
        op.drop_index("ix_feature_settings_class_id", table_name="feature_settings")

    with op.batch_alter_table("hall_pass_settings") as batch_op:
        if unique_constraint_exists("hall_pass_settings", "uq_hall_pass_settings_class_id"):
            batch_op.drop_constraint("uq_hall_pass_settings_class_id", type_="unique")
        batch_op.alter_column("block", existing_type=sa.String(length=10), nullable=True)
        batch_op.alter_column("join_code", existing_type=sa.String(length=20), nullable=True)
        batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=True)

    with op.batch_alter_table("feature_settings") as batch_op:
        if unique_constraint_exists("feature_settings", "uq_feature_settings_class_id"):
            batch_op.drop_constraint("uq_feature_settings_class_id", type_="unique")
        if unique_constraint_exists("feature_settings", "uq_feature_settings_teacher_join_code_block"):
            batch_op.drop_constraint("uq_feature_settings_teacher_join_code_block", type_="unique")
        if not unique_constraint_exists("feature_settings", "uq_feature_settings_teacher_block"):
            batch_op.create_unique_constraint("uq_feature_settings_teacher_block", ["teacher_id", "block"])
        if foreign_key_exists("feature_settings", "fk_feature_settings_class_id_class_economies"):
            batch_op.drop_constraint("fk_feature_settings_class_id_class_economies", type_="foreignkey")
        batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column("block", existing_type=sa.String(length=10), nullable=True)
        batch_op.alter_column("join_code", existing_type=sa.String(length=20), nullable=True)

    if column_exists("feature_settings", "class_id"):
        with op.batch_alter_table("feature_settings") as batch_op:
            batch_op.drop_column("class_id")
