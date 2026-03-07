"""Rename admin tables to teacher tables.

Revision ID: 8d4f2b7c1a9e
Revises: 36c86dfc8650
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8d4f2b7c1a9e"
down_revision = "36c86dfc8650"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists_by_name(index_name):
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            WHERE c.relkind = 'i' AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar()
    return result is not None


def sequence_exists(sequence_name):
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            WHERE c.relkind = 'S' AND c.relname = :sequence_name
            LIMIT 1
            """
        ),
        {"sequence_name": sequence_name},
    ).scalar()
    return result is not None


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    result = conn.execute(
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
    ).scalar()
    return result is not None


def _rename_indexes_to_teacher_names():
    rename_pairs = [
        ("ix_admins_hall_pass_verify_token", "ix_teachers_hall_pass_verify_token"),
        ("ix_admins_teacher_public_id", "ix_teachers_teacher_public_id"),
        ("ix_admins_username_lookup_hash", "ix_teachers_username_lookup_hash"),
    ]
    for old_name, new_name in rename_pairs:
        if index_exists_by_name(old_name) and not index_exists_by_name(new_name):
            op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _rename_indexes_to_admin_names():
    rename_pairs = [
        ("ix_teachers_hall_pass_verify_token", "ix_admins_hall_pass_verify_token"),
        ("ix_teachers_teacher_public_id", "ix_admins_teacher_public_id"),
        ("ix_teachers_username_lookup_hash", "ix_admins_username_lookup_hash"),
    ]
    for old_name, new_name in rename_pairs:
        if index_exists_by_name(old_name) and not index_exists_by_name(new_name):
            op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def upgrade():
    if table_exists("admins") and not table_exists("teachers"):
        op.rename_table("admins", "teachers")

    if table_exists("admin_credentials") and not table_exists("teacher_credentials"):
        op.rename_table("admin_credentials", "teacher_credentials")

    if table_exists("admin_invite_codes") and not table_exists("teacher_invite_codes"):
        op.rename_table("admin_invite_codes", "teacher_invite_codes")

    if sequence_exists("admins_id_seq") and not sequence_exists("teachers_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE admins_id_seq RENAME TO teachers_id_seq"))
    if sequence_exists("admin_credentials_id_seq") and not sequence_exists("teacher_credentials_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE admin_credentials_id_seq RENAME TO teacher_credentials_id_seq"))
    if sequence_exists("admin_invite_codes_id_seq") and not sequence_exists("teacher_invite_codes_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE admin_invite_codes_id_seq RENAME TO teacher_invite_codes_id_seq"))

    _rename_indexes_to_teacher_names()

    if table_exists("teachers"):
        if constraint_exists("teachers", "admins_pkey") and not constraint_exists("teachers", "teachers_pkey"):
            op.execute(sa.text("ALTER TABLE teachers RENAME CONSTRAINT admins_pkey TO teachers_pkey"))
        if constraint_exists("teachers", "admins_username_key") and not constraint_exists("teachers", "teachers_username_key"):
            op.execute(sa.text("ALTER TABLE teachers RENAME CONSTRAINT admins_username_key TO teachers_username_key"))

    if table_exists("teacher_credentials") and constraint_exists("teacher_credentials", "admin_credentials_pkey") and not constraint_exists("teacher_credentials", "teacher_credentials_pkey"):
        op.execute(sa.text("ALTER TABLE teacher_credentials RENAME CONSTRAINT admin_credentials_pkey TO teacher_credentials_pkey"))

    if table_exists("teacher_invite_codes"):
        if constraint_exists("teacher_invite_codes", "admin_invite_codes_pkey") and not constraint_exists("teacher_invite_codes", "teacher_invite_codes_pkey"):
            op.execute(sa.text("ALTER TABLE teacher_invite_codes RENAME CONSTRAINT admin_invite_codes_pkey TO teacher_invite_codes_pkey"))
        if constraint_exists("teacher_invite_codes", "admin_invite_codes_code_key") and not constraint_exists("teacher_invite_codes", "teacher_invite_codes_code_key"):
            op.execute(sa.text("ALTER TABLE teacher_invite_codes RENAME CONSTRAINT admin_invite_codes_code_key TO teacher_invite_codes_code_key"))


def downgrade():
    if table_exists("teacher_invite_codes"):
        if constraint_exists("teacher_invite_codes", "teacher_invite_codes_code_key") and not constraint_exists("teacher_invite_codes", "admin_invite_codes_code_key"):
            op.execute(sa.text("ALTER TABLE teacher_invite_codes RENAME CONSTRAINT teacher_invite_codes_code_key TO admin_invite_codes_code_key"))
        if constraint_exists("teacher_invite_codes", "teacher_invite_codes_pkey") and not constraint_exists("teacher_invite_codes", "admin_invite_codes_pkey"):
            op.execute(sa.text("ALTER TABLE teacher_invite_codes RENAME CONSTRAINT teacher_invite_codes_pkey TO admin_invite_codes_pkey"))

    if table_exists("teacher_credentials") and constraint_exists("teacher_credentials", "teacher_credentials_pkey") and not constraint_exists("teacher_credentials", "admin_credentials_pkey"):
        op.execute(sa.text("ALTER TABLE teacher_credentials RENAME CONSTRAINT teacher_credentials_pkey TO admin_credentials_pkey"))

    if table_exists("teachers"):
        if constraint_exists("teachers", "teachers_username_key") and not constraint_exists("teachers", "admins_username_key"):
            op.execute(sa.text("ALTER TABLE teachers RENAME CONSTRAINT teachers_username_key TO admins_username_key"))
        if constraint_exists("teachers", "teachers_pkey") and not constraint_exists("teachers", "admins_pkey"):
            op.execute(sa.text("ALTER TABLE teachers RENAME CONSTRAINT teachers_pkey TO admins_pkey"))

    _rename_indexes_to_admin_names()

    if sequence_exists("teacher_invite_codes_id_seq") and not sequence_exists("admin_invite_codes_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE teacher_invite_codes_id_seq RENAME TO admin_invite_codes_id_seq"))
    if sequence_exists("teacher_credentials_id_seq") and not sequence_exists("admin_credentials_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE teacher_credentials_id_seq RENAME TO admin_credentials_id_seq"))
    if sequence_exists("teachers_id_seq") and not sequence_exists("admins_id_seq"):
        op.execute(sa.text("ALTER SEQUENCE teachers_id_seq RENAME TO admins_id_seq"))

    if table_exists("teacher_invite_codes") and not table_exists("admin_invite_codes"):
        op.rename_table("teacher_invite_codes", "admin_invite_codes")

    if table_exists("teacher_credentials") and not table_exists("admin_credentials"):
        op.rename_table("teacher_credentials", "admin_credentials")

    if table_exists("teachers") and not table_exists("admins"):
        op.rename_table("teachers", "admins")
