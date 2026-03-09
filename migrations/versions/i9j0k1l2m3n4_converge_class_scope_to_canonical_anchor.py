"""Converge class scope to canonical class_economies anchor

Revision ID: i9j0k1l2m3n4
Revises: h9i0j1k2l3m4
Create Date: 2026-03-09 13:30:00.000000

"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i9j0k1l2m3n4"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


CLASS_ID_TABLES = (
    ("actor_request_trace", "SET NULL"),
    ("banking_settings", "CASCADE"),
    ("error_events", "SET NULL"),
    ("hall_pass_settings", "CASCADE"),
    ("insurance_policies", "CASCADE"),
    ("payroll_cache", "CASCADE"),
    ("payroll_settings", "CASCADE"),
    ("rent_items", "CASCADE"),
    ("rent_settings", "CASCADE"),
    ("store_items", "CASCADE"),
    ("students", "CASCADE"),
    ("teacher_blocks", "CASCADE"),
    ("ticket_correlation_pack", "SET NULL"),
)


STRICT_CLASS_SCOPE_TABLES = (
    "banking_settings",
    "hall_pass_settings",
    "insurance_policies",
    "payroll_cache",
    "payroll_settings",
    "rent_items",
    "rent_settings",
    "store_items",
    "students",
    "teacher_blocks",
)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def foreign_keys_for_column(table_name: str, column_name: str) -> list[str]:
    inspector = sa.inspect(op.get_bind())
    names: list[str] = []
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in (fk.get("constrained_columns") or []):
            names.append(fk["name"])
    return names


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {uc["name"] for uc in inspector.get_unique_constraints(table_name)}


def _rename_index(table_name: str, old_name: str, new_name: str) -> None:
    if not index_exists(table_name, old_name) or index_exists(table_name, new_name):
        return
    op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _ensure_class_economies_columns() -> None:
    if not column_exists("class_economies", "class_id"):
        op.add_column("class_economies", sa.Column("class_id", sa.String(length=36), nullable=True))
    if not column_exists("class_economies", "teacher_id"):
        op.add_column("class_economies", sa.Column("teacher_id", sa.Integer(), nullable=True))
    if not column_exists("class_economies", "is_active"):
        op.add_column(
            "class_economies",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    if not column_exists("class_economies", "metadata_json"):
        op.add_column("class_economies", sa.Column("metadata_json", sa.JSON(), nullable=True))

    if not index_exists("class_economies", "ix_class_economies_teacher_id"):
        op.create_index("ix_class_economies_teacher_id", "class_economies", ["teacher_id"], unique=False)
    if not unique_constraint_exists("class_economies", "uq_class_economies_class_id"):
        with op.batch_alter_table("class_economies") as batch_op:
            batch_op.create_unique_constraint("uq_class_economies_class_id", ["class_id"])


def _backfill_class_economies() -> None:
    conn = op.get_bind()

    if table_exists("join_codes"):
        conn.execute(
            sa.text(
                """
                UPDATE class_economies AS ce
                SET class_id = jc.join_code_id,
                    teacher_id = jc.teacher_id,
                    is_active = COALESCE(jc.is_active, TRUE),
                    metadata_json = jc.metadata_json
                FROM join_codes AS jc
                WHERE ce.join_code = jc.join_code_token
                """
            )
        )

    conn.execute(
        sa.text(
            """
            UPDATE class_economies
            SET teacher_id = created_by_admin_id
            WHERE teacher_id IS NULL AND created_by_admin_id IS NOT NULL
            """
        )
    )

    if table_exists("class_memberships"):
        conn.execute(
            sa.text(
                """
                UPDATE class_economies AS ce
                SET teacher_id = cm.admin_id
                FROM class_memberships AS cm
                WHERE ce.join_code = cm.join_code
                  AND ce.teacher_id IS NULL
                  AND cm.admin_id IS NOT NULL
                """
            )
        )

    if table_exists("teacher_blocks"):
        conn.execute(
            sa.text(
                """
                UPDATE class_economies AS ce
                SET teacher_id = tb.teacher_id
                FROM teacher_blocks AS tb
                WHERE ce.join_code = tb.join_code
                  AND ce.teacher_id IS NULL
                  AND tb.teacher_id IS NOT NULL
                """
            )
        )

    missing_ids = conn.execute(
        sa.text("SELECT join_code FROM class_economies WHERE class_id IS NULL ORDER BY join_code")
    ).fetchall()
    for (join_code,) in missing_ids:
        conn.execute(
            sa.text("UPDATE class_economies SET class_id = :class_id WHERE join_code = :join_code"),
            {"class_id": str(uuid.uuid4()), "join_code": join_code},
        )

    remaining_null_teacher = conn.execute(
        sa.text("SELECT count(*) FROM class_economies WHERE teacher_id IS NULL")
    ).scalar_one()
    if remaining_null_teacher:
        raise RuntimeError("class_economies.teacher_id still has NULL rows after backfill")

    with op.batch_alter_table("class_economies") as batch_op:
        batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("teacher_id", existing_type=sa.Integer(), nullable=False)

    fk_names = set(foreign_keys_for_column("class_economies", "teacher_id"))
    if "class_economies_teacher_id_fkey" not in fk_names:
        with op.batch_alter_table("class_economies") as batch_op:
            batch_op.create_foreign_key(
                "class_economies_teacher_id_fkey",
                "teachers",
                ["teacher_id"],
                ["id"],
                ondelete="CASCADE",
            )


def _rename_join_code_id_columns() -> None:
    conn = op.get_bind()

    for table_name, ondelete in CLASS_ID_TABLES:
        has_join_code_id = column_exists(table_name, "join_code_id")
        has_class_id = column_exists(table_name, "class_id")

        if has_join_code_id:
            for fk_name in foreign_keys_for_column(table_name, "join_code_id"):
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_constraint(fk_name, type_="foreignkey")

            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    "join_code_id",
                    new_column_name="class_id",
                    existing_type=sa.String(length=36),
                    existing_nullable=True,
                )
            has_class_id = True

        if not has_class_id:
            continue

        if column_exists(table_name, "join_code"):
            conn.execute(
                sa.text(
                    f"""
                    UPDATE {table_name} AS tgt
                    SET class_id = ce.class_id
                    FROM class_economies AS ce
                    WHERE tgt.class_id IS NULL
                      AND tgt.join_code IS NOT NULL
                      AND ce.join_code = tgt.join_code
                    """
                )
            )

        old_index = f"ix_{table_name}_join_code_id"
        new_index = f"ix_{table_name}_class_id"
        _rename_index(table_name, old_index, new_index)
        if not index_exists(table_name, new_index):
            op.create_index(new_index, table_name, ["class_id"], unique=False)

        fk_name = f"fk_{table_name}_class_id_class_economies"
        existing_fk_names = set(foreign_keys_for_column(table_name, "class_id"))
        if fk_name not in existing_fk_names:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.create_foreign_key(
                    fk_name,
                    "class_economies",
                    ["class_id"],
                    ["class_id"],
                    ondelete=ondelete,
                )


def _drop_forbidden_null_scope_rows() -> None:
    conn = op.get_bind()
    if table_exists("hall_pass_settings") and column_exists("hall_pass_settings", "class_id"):
        conn.execute(
            sa.text(
                "DELETE FROM hall_pass_settings WHERE join_code IS NULL AND class_id IS NULL"
            )
        )
    if table_exists("payroll_cache") and column_exists("payroll_cache", "class_id"):
        conn.execute(
            sa.text(
                "DELETE FROM payroll_cache WHERE join_code IS NULL AND class_id IS NULL"
            )
        )


def _enforce_strict_scope_where_clean() -> None:
    conn = op.get_bind()
    for table_name in STRICT_CLASS_SCOPE_TABLES:
        if not column_exists(table_name, "class_id"):
            continue
        remaining_nulls = conn.execute(
            sa.text(f"SELECT count(*) FROM {table_name} WHERE class_id IS NULL")
        ).scalar_one()
        if remaining_nulls:
            raise RuntimeError(f"{table_name}.class_id still has NULL rows after backfill")
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)


def _drop_legacy_tables() -> None:
    if table_exists("class_join_code_aliases"):
        op.drop_table("class_join_code_aliases")
    if table_exists("join_codes"):
        op.drop_table("join_codes")


def upgrade() -> None:
    if not table_exists("class_economies"):
        raise RuntimeError("class_economies must exist before converging class scope")

    _ensure_class_economies_columns()
    _backfill_class_economies()
    _rename_join_code_id_columns()
    _drop_forbidden_null_scope_rows()
    _enforce_strict_scope_where_clean()
    _drop_legacy_tables()


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for canonical class scope contraction")
