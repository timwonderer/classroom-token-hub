"""Rename issue public actor reference to actor_public_id.

Revision ID: f7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa


revision = "f7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
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
        columns = [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False
    return column_name in columns


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [index["name"] for index in inspector.get_indexes(table_name)]
    except Exception:
        return False
    return index_name in indexes


def _drop_index_if_exists(index_name):
    if table_exists("issues") and index_exists("issues", index_name):
        op.drop_index(index_name, table_name="issues")


def _create_index_if_missing(index_name, columns):
    if table_exists("issues") and not index_exists("issues", index_name):
        op.create_index(index_name, "issues", columns)


def _rename_or_converge_column(old_name, new_name):
    if not table_exists("issues"):
        return

    old_exists = column_exists("issues", old_name)
    new_exists = column_exists("issues", new_name)

    if old_exists and not new_exists:
        op.alter_column(
            "issues",
            old_name,
            new_column_name=new_name,
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        return

    if old_exists and new_exists:
        op.execute(
            sa.text(
                f"""
                UPDATE issues
                SET {new_name} = {old_name}
                WHERE {new_name} IS NULL
                  AND {old_name} IS NOT NULL
                """
            )
        )
        op.drop_column("issues", old_name)


def upgrade():
    _drop_index_if_exists("ix_issues_opaque_student_reference")
    _rename_or_converge_column("opaque_student_reference", "actor_public_id")
    if column_exists("issues", "actor_public_id"):
        _create_index_if_missing("ix_issues_actor_public_id", ["actor_public_id"])


def downgrade():
    _drop_index_if_exists("ix_issues_actor_public_id")
    _rename_or_converge_column("actor_public_id", "opaque_student_reference")
    if column_exists("issues", "opaque_student_reference"):
        _create_index_if_missing("ix_issues_opaque_student_reference", ["opaque_student_reference"])
