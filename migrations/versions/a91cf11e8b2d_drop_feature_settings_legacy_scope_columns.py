"""drop feature_settings legacy scope columns

Revision ID: a91cf11e8b2d
Revises: f84c7ad2c1aa
Create Date: 2026-05-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a91cf11e8b2d"
down_revision = "f84c7ad2c1aa"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [index["name"] for index in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return constraint_name in fks
    except Exception:
        return False


def upgrade():
    if not table_exists("feature_settings"):
        return

    with op.batch_alter_table("feature_settings", schema=None) as batch_op:
        if index_exists("feature_settings", "ix_feature_settings_teacher_id"):
            batch_op.drop_index("ix_feature_settings_teacher_id")
        if column_exists("feature_settings", "teacher_id"):
            batch_op.drop_column("teacher_id")
        if column_exists("feature_settings", "join_code"):
            batch_op.drop_column("join_code")
        if column_exists("feature_settings", "block"):
            batch_op.drop_column("block")


def downgrade():
    if not table_exists("feature_settings"):
        return

    with op.batch_alter_table("feature_settings", schema=None) as batch_op:
        if not column_exists("feature_settings", "teacher_id"):
            batch_op.add_column(sa.Column("teacher_id", sa.Integer(), nullable=True))
            if not foreign_key_exists("feature_settings", "fk_feature_settings_teacher_id_teachers"):
                batch_op.create_foreign_key(
                    "fk_feature_settings_teacher_id_teachers",
                    "teachers",
                    ["teacher_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
            if not index_exists("feature_settings", "ix_feature_settings_teacher_id"):
                batch_op.create_index("ix_feature_settings_teacher_id", ["teacher_id"], unique=False)
        if not column_exists("feature_settings", "join_code"):
            batch_op.add_column(sa.Column("join_code", sa.String(length=20), nullable=True))
            if not index_exists("feature_settings", "ix_feature_settings_join_code"):
                batch_op.create_index("ix_feature_settings_join_code", ["join_code"], unique=False)
        if not column_exists("feature_settings", "block"):
            batch_op.add_column(sa.Column("block", sa.String(length=10), nullable=True))
