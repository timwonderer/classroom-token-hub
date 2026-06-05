"""Drop payroll legacy scope columns

Revision ID: 2a4f6c8d0e21
Revises: 1f6c2b8d4e90
Create Date: 2026-06-05 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


# revision identifiers, used by Alembic.
revision = "2a4f6c8d0e21"
down_revision = "1f6c2b8d4e90"
branch_labels = None
depends_on = None


def upgrade():
    if table_exists("payroll_settings"):
        op.execute("DROP POLICY IF EXISTS payroll_settings_tenant_isolation_select ON payroll_settings")
        op.execute("DROP POLICY IF EXISTS payroll_settings_tenant_isolation_insert ON payroll_settings")
        op.execute("DROP POLICY IF EXISTS payroll_settings_tenant_isolation_update ON payroll_settings")
        op.execute("DROP POLICY IF EXISTS payroll_settings_tenant_isolation_delete ON payroll_settings")

        if column_exists("payroll_settings", "class_id"):
            op.alter_column("payroll_settings", "class_id", existing_type=sa.String(length=36), nullable=False)

        if index_exists("payroll_settings", "ix_payroll_settings_join_code"):
            op.drop_index(op.f("ix_payroll_settings_join_code"), table_name="payroll_settings")
        if index_exists("payroll_settings", "ix_payroll_settings_teacher_id"):
            op.drop_index(op.f("ix_payroll_settings_teacher_id"), table_name="payroll_settings")

        for fk in get_foreign_keys_by_column("payroll_settings", "teacher_id"):
            op.drop_constraint(fk["name"], "payroll_settings", type_="foreignkey")

        if column_exists("payroll_settings", "join_code"):
            op.drop_column("payroll_settings", "join_code")
        if column_exists("payroll_settings", "teacher_id"):
            op.drop_column("payroll_settings", "teacher_id")

    if table_exists("payroll_cache"):
        if index_exists("payroll_cache", "ix_payroll_cache_join_code"):
            op.drop_index(op.f("ix_payroll_cache_join_code"), table_name="payroll_cache")
        if index_exists("payroll_cache", "ix_payroll_cache_teacher_id"):
            op.drop_index(op.f("ix_payroll_cache_teacher_id"), table_name="payroll_cache")

        for fk in get_foreign_keys_by_column("payroll_cache", "teacher_id"):
            op.drop_constraint(fk["name"], "payroll_cache", type_="foreignkey")

        if column_exists("payroll_cache", "join_code"):
            op.drop_column("payroll_cache", "join_code")
        if column_exists("payroll_cache", "teacher_id"):
            op.drop_column("payroll_cache", "teacher_id")


def downgrade():
    if table_exists("payroll_settings"):
        if not column_exists("payroll_settings", "teacher_id"):
            op.add_column(
                "payroll_settings",
                sa.Column("teacher_id", sa.INTEGER(), autoincrement=False, nullable=True),
            )
        if not column_exists("payroll_settings", "join_code"):
            op.add_column(
                "payroll_settings",
                sa.Column("join_code", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
            )
        if column_exists("payroll_settings", "class_id"):
            op.alter_column("payroll_settings", "class_id", existing_type=sa.String(length=36), nullable=True)

        if not index_exists("payroll_settings", "ix_payroll_settings_teacher_id"):
            op.create_index(op.f("ix_payroll_settings_teacher_id"), "payroll_settings", ["teacher_id"], unique=False)
        if not index_exists("payroll_settings", "ix_payroll_settings_join_code"):
            op.create_index(op.f("ix_payroll_settings_join_code"), "payroll_settings", ["join_code"], unique=False)

        op.create_foreign_key(
            op.f("fk_payroll_settings_teacher_id_teachers"),
            "payroll_settings",
            "teachers",
            ["teacher_id"],
            ["id"],
        )

    if table_exists("payroll_cache"):
        if not column_exists("payroll_cache", "teacher_id"):
            op.add_column(
                "payroll_cache",
                sa.Column("teacher_id", sa.INTEGER(), autoincrement=False, nullable=True),
            )
        if not column_exists("payroll_cache", "join_code"):
            op.add_column(
                "payroll_cache",
                sa.Column("join_code", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
            )

        if not index_exists("payroll_cache", "ix_payroll_cache_teacher_id"):
            op.create_index(op.f("ix_payroll_cache_teacher_id"), "payroll_cache", ["teacher_id"], unique=False)
        if not index_exists("payroll_cache", "ix_payroll_cache_join_code"):
            op.create_index(op.f("ix_payroll_cache_join_code"), "payroll_cache", ["join_code"], unique=False)

        op.create_foreign_key(
            op.f("fk_payroll_cache_teacher_id_teachers"),
            "payroll_cache",
            "teachers",
            ["teacher_id"],
            ["id"],
            ondelete="CASCADE",
        )
