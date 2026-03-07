"""Rename teacher-owned admin_id columns to teacher_id.

Revision ID: c4e1a2b3d4f6
Revises: 8d4f2b7c1a9e
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e1a2b3d4f6"
down_revision = "8d4f2b7c1a9e"
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
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))
    except Exception:
        return False


def index_exists(index_name):
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name LIMIT 1"),
        {"name": index_name},
    ).scalar() is not None


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = :table_name
              AND con.conname = :constraint_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    ).scalar() is not None


def _rename_column_if_needed(table_name, old_col, new_col):
    if table_exists(table_name) and column_exists(table_name, old_col) and not column_exists(table_name, new_col):
        op.execute(sa.text(f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_col}" TO "{new_col}"'))


def _rename_index_if_needed(old_name, new_name):
    if index_exists(old_name) and not index_exists(new_name):
        op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _rename_constraint_if_needed(table_name, old_name, new_name):
    if constraint_exists(table_name, old_name) and not constraint_exists(table_name, new_name):
        op.execute(sa.text(f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'))


def upgrade():
    _rename_column_if_needed("student_teachers", "admin_id", "teacher_id")
    _rename_column_if_needed("deletion_requests", "admin_id", "teacher_id")
    _rename_column_if_needed("recovery_requests", "admin_id", "teacher_id")
    _rename_column_if_needed("teacher_credentials", "admin_id", "teacher_id")
    _rename_column_if_needed("rent_waivers", "created_by_admin_id", "created_by_teacher_id")
    _rename_column_if_needed("insurance_claims", "processed_by_admin_id", "processed_by_teacher_id")
    _rename_column_if_needed("insurance_claims", "admin_notes", "teacher_notes")

    _rename_index_if_needed("ix_student_teachers_admin_id", "ix_student_teachers_teacher_id")
    _rename_index_if_needed("ix_deletion_requests_admin_id", "ix_deletion_requests_teacher_id")
    _rename_index_if_needed("ix_recovery_requests_admin_id", "ix_recovery_requests_teacher_id")

    _rename_constraint_if_needed("student_teachers", "student_teachers_admin_id_fkey", "student_teachers_teacher_id_fkey")
    _rename_constraint_if_needed("student_teachers", "uq_student_teachers_student_admin", "uq_student_teachers_student_teacher")
    _rename_constraint_if_needed("deletion_requests", "deletion_requests_admin_id_fkey", "deletion_requests_teacher_id_fkey")
    _rename_constraint_if_needed("recovery_requests", "recovery_requests_admin_id_fkey", "recovery_requests_teacher_id_fkey")
    _rename_constraint_if_needed("teacher_credentials", "admin_credentials_admin_id_fkey", "teacher_credentials_teacher_id_fkey")
    _rename_constraint_if_needed(
        "rent_waivers",
        "rent_waivers_created_by_admin_id_fkey",
        "rent_waivers_created_by_teacher_id_fkey",
    )
    _rename_constraint_if_needed(
        "insurance_claims",
        "insurance_claims_processed_by_admin_id_fkey",
        "insurance_claims_processed_by_teacher_id_fkey",
    )


def downgrade():
    _rename_constraint_if_needed(
        "insurance_claims",
        "insurance_claims_processed_by_teacher_id_fkey",
        "insurance_claims_processed_by_admin_id_fkey",
    )
    _rename_constraint_if_needed(
        "rent_waivers",
        "rent_waivers_created_by_teacher_id_fkey",
        "rent_waivers_created_by_admin_id_fkey",
    )
    _rename_constraint_if_needed("teacher_credentials", "teacher_credentials_teacher_id_fkey", "admin_credentials_admin_id_fkey")
    _rename_constraint_if_needed("recovery_requests", "recovery_requests_teacher_id_fkey", "recovery_requests_admin_id_fkey")
    _rename_constraint_if_needed("deletion_requests", "deletion_requests_teacher_id_fkey", "deletion_requests_admin_id_fkey")
    _rename_constraint_if_needed("student_teachers", "uq_student_teachers_student_teacher", "uq_student_teachers_student_admin")
    _rename_constraint_if_needed("student_teachers", "student_teachers_teacher_id_fkey", "student_teachers_admin_id_fkey")

    _rename_index_if_needed("ix_recovery_requests_teacher_id", "ix_recovery_requests_admin_id")
    _rename_index_if_needed("ix_deletion_requests_teacher_id", "ix_deletion_requests_admin_id")
    _rename_index_if_needed("ix_student_teachers_teacher_id", "ix_student_teachers_admin_id")

    _rename_column_if_needed("insurance_claims", "processed_by_teacher_id", "processed_by_admin_id")
    _rename_column_if_needed("insurance_claims", "teacher_notes", "admin_notes")
    _rename_column_if_needed("rent_waivers", "created_by_teacher_id", "created_by_admin_id")
    _rename_column_if_needed("teacher_credentials", "teacher_id", "admin_id")
    _rename_column_if_needed("recovery_requests", "teacher_id", "admin_id")
    _rename_column_if_needed("deletion_requests", "teacher_id", "admin_id")
    _rename_column_if_needed("student_teachers", "teacher_id", "admin_id")
