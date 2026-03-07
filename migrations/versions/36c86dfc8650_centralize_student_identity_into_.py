"""Centralize student identity into identity_profiles with non-sequential references.

Revision ID: 36c86dfc8650
Revises: 3d3898de8611
Create Date: 2026-03-07 22:08:39.893574
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "36c86dfc8650"
down_revision = "3d3898de8611"
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


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk
            for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def _create_identity_profiles_table():
    if table_exists("identity_profiles"):
        return

    op.create_table(
        "identity_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_type", sa.String(length=32), nullable=False),
        # PIIEncryptedType persists to bytea at the DB level.
        sa.Column("first_name", sa.LargeBinary(), nullable=False),
        sa.Column("last_initial", sa.String(length=1), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    if not index_exists("identity_profiles", "ix_identity_profiles_profile_type"):
        op.create_index("ix_identity_profiles_profile_type", "identity_profiles", ["profile_type"], unique=False)
    if not index_exists("identity_profiles", "ix_identity_profiles_type_name"):
        op.create_index("ix_identity_profiles_type_name", "identity_profiles", ["profile_type", "last_initial"], unique=False)


def _ensure_student_columns():
    if not table_exists("students"):
        return

    if not column_exists("students", "identity_id"):
        op.add_column("students", sa.Column("identity_id", sa.Integer(), nullable=True))
    if not column_exists("students", "internal_reference"):
        op.add_column("students", sa.Column("internal_reference", sa.String(length=64), nullable=True))
    if not column_exists("students", "opaque_reference"):
        op.add_column("students", sa.Column("opaque_reference", sa.String(length=64), nullable=True))

    if not index_exists("students", "ix_students_identity_id"):
        op.create_index("ix_students_identity_id", "students", ["identity_id"], unique=False)


def _ensure_teacher_block_columns():
    if not table_exists("teacher_blocks"):
        return

    if not column_exists("teacher_blocks", "identity_id"):
        op.add_column("teacher_blocks", sa.Column("identity_id", sa.Integer(), nullable=True))

    if not index_exists("teacher_blocks", "ix_teacher_blocks_identity_id"):
        op.create_index("ix_teacher_blocks_identity_id", "teacher_blocks", ["identity_id"], unique=False)


def _backfill_student_identities_and_refs():
    if not table_exists("students") or not table_exists("identity_profiles"):
        return

    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            WITH ins AS (
                INSERT INTO identity_profiles (profile_type, first_name, last_initial, created_at, updated_at)
                SELECT 'student', s.first_name, s.last_initial, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM students s
                WHERE s.identity_id IS NULL
                RETURNING id
            ), numbered AS (
                SELECT id, row_number() OVER (ORDER BY id) AS rn
                FROM ins
            ), targets AS (
                SELECT s.id AS student_id, row_number() OVER (ORDER BY s.id) AS rn
                FROM students s
                WHERE s.identity_id IS NULL
            )
            UPDATE students s
            SET identity_id = n.id
            FROM targets t
            JOIN numbered n ON n.rn = t.rn
            WHERE s.id = t.student_id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE students
            SET internal_reference = 'sint_' || md5(random()::text || clock_timestamp()::text || id::text)
            WHERE internal_reference IS NULL
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE students
            SET opaque_reference = 'stu_' || md5(random()::text || clock_timestamp()::text || id::text)
            WHERE opaque_reference IS NULL
            """
        )
    )


def _backfill_teacher_block_identities():
    if not table_exists("teacher_blocks") or not table_exists("identity_profiles"):
        return

    conn = op.get_bind()

    # Reuse student-linked identity where available.
    if table_exists("students") and column_exists("students", "identity_id"):
        conn.execute(
            sa.text(
                """
                UPDATE teacher_blocks tb
                SET identity_id = s.identity_id
                FROM students s
                WHERE tb.identity_id IS NULL
                  AND tb.student_id = s.id
                  AND s.identity_id IS NOT NULL
                """
            )
        )

    # For remaining unclaimed/standalone roster seats, create teacher_block profiles.
    conn.execute(
        sa.text(
            """
            WITH ins AS (
                INSERT INTO identity_profiles (profile_type, first_name, last_initial, created_at, updated_at)
                SELECT 'teacher_block', tb.first_name, tb.last_initial, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM teacher_blocks tb
                WHERE tb.identity_id IS NULL
                RETURNING id
            ), numbered AS (
                SELECT id, row_number() OVER (ORDER BY id) AS rn
                FROM ins
            ), targets AS (
                SELECT tb.id AS teacher_block_id, row_number() OVER (ORDER BY tb.id) AS rn
                FROM teacher_blocks tb
                WHERE tb.identity_id IS NULL
            )
            UPDATE teacher_blocks tb
            SET identity_id = n.id
            FROM targets t
            JOIN numbered n ON n.rn = t.rn
            WHERE tb.id = t.teacher_block_id
            """
        )
    )


def _add_foreign_keys_and_student_uniques():
    if table_exists("students") and column_exists("students", "identity_id"):
        if not foreign_key_exists("students", "fk_students_identity_id"):
            op.create_foreign_key(
                "fk_students_identity_id",
                "students",
                "identity_profiles",
                ["identity_id"],
                ["id"],
                ondelete="RESTRICT",
            )

    if table_exists("teacher_blocks") and column_exists("teacher_blocks", "identity_id"):
        if not foreign_key_exists("teacher_blocks", "fk_teacher_blocks_identity_id"):
            op.create_foreign_key(
                "fk_teacher_blocks_identity_id",
                "teacher_blocks",
                "identity_profiles",
                ["identity_id"],
                ["id"],
                ondelete="RESTRICT",
            )

    if table_exists("students"):
        if column_exists("students", "internal_reference") and not index_exists("students", "ix_students_internal_reference"):
            op.create_index("ix_students_internal_reference", "students", ["internal_reference"], unique=True)
        if column_exists("students", "opaque_reference") and not index_exists("students", "ix_students_opaque_reference"):
            op.create_index("ix_students_opaque_reference", "students", ["opaque_reference"], unique=True)

        # Enforce non-null after backfill so ORM defaults remain the source for future writes.
        if column_exists("students", "internal_reference"):
            op.execute(
                sa.text("""
                    UPDATE students
                    SET internal_reference = 'sint_' || md5(random()::text || clock_timestamp()::text || id::text)
                    WHERE internal_reference IS NULL
                """)
            )
            op.alter_column("students", "internal_reference", existing_type=sa.String(length=64), nullable=False)

        if column_exists("students", "opaque_reference"):
            op.execute(
                sa.text("""
                    UPDATE students
                    SET opaque_reference = 'stu_' || md5(random()::text || clock_timestamp()::text || id::text)
                    WHERE opaque_reference IS NULL
                """)
            )
            op.alter_column("students", "opaque_reference", existing_type=sa.String(length=64), nullable=False)

        if column_exists("students", "identity_id"):
            op.alter_column("students", "identity_id", existing_type=sa.Integer(), nullable=False)

    if table_exists("teacher_blocks") and column_exists("teacher_blocks", "identity_id"):
        op.alter_column("teacher_blocks", "identity_id", existing_type=sa.Integer(), nullable=False)


def upgrade():
    _create_identity_profiles_table()
    _ensure_student_columns()
    _ensure_teacher_block_columns()
    _backfill_student_identities_and_refs()
    _backfill_teacher_block_identities()
    _add_foreign_keys_and_student_uniques()


def downgrade():
    if table_exists("teacher_blocks") and column_exists("teacher_blocks", "identity_id"):
        for fk in get_foreign_keys_by_column("teacher_blocks", "identity_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "teacher_blocks", type_="foreignkey")
        if index_exists("teacher_blocks", "ix_teacher_blocks_identity_id"):
            op.drop_index("ix_teacher_blocks_identity_id", table_name="teacher_blocks")
        op.drop_column("teacher_blocks", "identity_id")

    if table_exists("students"):
        for fk in get_foreign_keys_by_column("students", "identity_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "students", type_="foreignkey")
        if index_exists("students", "ix_students_opaque_reference"):
            op.drop_index("ix_students_opaque_reference", table_name="students")
        if index_exists("students", "ix_students_internal_reference"):
            op.drop_index("ix_students_internal_reference", table_name="students")
        if index_exists("students", "ix_students_identity_id"):
            op.drop_index("ix_students_identity_id", table_name="students")

        if column_exists("students", "opaque_reference"):
            op.drop_column("students", "opaque_reference")
        if column_exists("students", "internal_reference"):
            op.drop_column("students", "internal_reference")
        if column_exists("students", "identity_id"):
            op.drop_column("students", "identity_id")

    if table_exists("identity_profiles"):
        if index_exists("identity_profiles", "ix_identity_profiles_type_name"):
            op.drop_index("ix_identity_profiles_type_name", table_name="identity_profiles")
        if index_exists("identity_profiles", "ix_identity_profiles_profile_type"):
            op.drop_index("ix_identity_profiles_profile_type", table_name="identity_profiles")
        op.drop_table("identity_profiles")
