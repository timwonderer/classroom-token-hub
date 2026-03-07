"""Create users and seats identity tables with legacy backfill.

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import uuid


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_public_id", "users", ["public_id"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "seats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("join_code", sa.String(length=20), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("block", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("user_id", "join_code", name="uq_seats_user_join_code"),
    )
    op.create_index("ix_seats_public_id", "seats", ["public_id"], unique=True)
    op.create_index("ix_seats_user_id", "seats", ["user_id"], unique=False)
    op.create_index("ix_seats_join_code", "seats", ["join_code"], unique=False)
    op.create_index("ix_seats_student_id", "seats", ["student_id"], unique=False)

    bind = op.get_bind()
    metadata = sa.MetaData()

    students = sa.Table("students", metadata, autoload_with=bind)
    teacher_blocks = sa.Table("teacher_blocks", metadata, autoload_with=bind)
    users = sa.Table("users", metadata, autoload_with=bind)
    seats = sa.Table("seats", metadata, autoload_with=bind)

    now = datetime.now(timezone.utc)

    # Backfill global users from existing students.
    student_to_user = {}
    student_rows = bind.execute(
        sa.select(
            students.c.id,
            students.c.username_lookup_hash,
            students.c.pin_hash,
            students.c.passphrase_hash,
            students.c.first_half_hash,
        )
    ).fetchall()

    for row in student_rows:
        student_id = int(row.id)
        if row.username_lookup_hash:
            username = f"migrated_{row.username_lookup_hash}"
        else:
            username = f"migrated_student_{student_id}"

        password_hash = (
            row.pin_hash
            or row.passphrase_hash
            or row.first_half_hash
            or f"migrated_password_{student_id}"
        )

        result = bind.execute(
            users.insert().values(
                public_id=str(uuid.uuid4()),
                username=username,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
        )
        student_to_user[student_id] = int(result.inserted_primary_key[0])

    # Backfill seats by claimed roster seats (one seat per user+join_code).
    seen_user_join = set()
    seat_rows = bind.execute(
        sa.select(
            teacher_blocks.c.student_id,
            teacher_blocks.c.join_code,
            teacher_blocks.c.block,
            teacher_blocks.c.created_at,
        ).where(
            teacher_blocks.c.student_id.is_not(None),
            teacher_blocks.c.join_code.is_not(None),
            teacher_blocks.c.is_claimed.is_(True),
        )
    ).fetchall()

    for row in seat_rows:
        student_id = int(row.student_id)
        user_id = student_to_user.get(student_id)
        if not user_id:
            continue

        join_code = row.join_code
        dedupe_key = (user_id, join_code)
        if dedupe_key in seen_user_join:
            continue
        seen_user_join.add(dedupe_key)

        bind.execute(
            seats.insert().values(
                public_id=str(uuid.uuid4()),
                user_id=user_id,
                join_code=join_code,
                student_id=student_id,
                block=row.block,
                created_at=row.created_at or now,
                updated_at=now,
            )
        )


def downgrade():
    op.drop_index("ix_seats_student_id", table_name="seats")
    op.drop_index("ix_seats_join_code", table_name="seats")
    op.drop_index("ix_seats_user_id", table_name="seats")
    op.drop_index("ix_seats_public_id", table_name="seats")
    op.drop_table("seats")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_public_id", table_name="users")
    op.drop_table("users")
