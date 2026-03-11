"""Prepare seats for identity overhaul target shape

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-10 09:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    if not _column_exists("seats", "class_id"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("class_id", sa.String(length=36), nullable=True))

    if not _column_exists("seats", "role"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=False, server_default="student"))

    if not _column_exists("seats", "block_identifier"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("block_identifier", sa.String(length=10), nullable=True))

    if not _column_exists("seats", "roster_fingerprint"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("roster_fingerprint", sa.String(length=128), nullable=True))

    if not _column_exists("seats", "dedupe_code"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("dedupe_code", sa.String(length=8), nullable=True))

    if not _column_exists("seats", "claimed_at"):
        with op.batch_alter_table("seats") as batch_op:
            batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("""
        UPDATE seats s
        SET class_id = ce.class_id
        FROM class_economies ce
        WHERE s.class_id IS NULL
          AND s.join_code = ce.join_code
    """))

    op.execute(sa.text("""
        UPDATE seats
        SET block_identifier = block
        WHERE block_identifier IS NULL
          AND block IS NOT NULL
    """))

    with op.batch_alter_table("seats") as batch_op:
        if _foreign_key_exists("seats", "seats_class_id_fkey"):
            batch_op.drop_constraint("seats_class_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "seats_class_id_fkey",
            "class_economies",
            ["class_id"],
            ["class_id"],
            ondelete="CASCADE",
        )
        if _unique_exists("seats", "uq_seats_user_join_code"):
            batch_op.drop_constraint("uq_seats_user_join_code", type_="unique")
        if not _unique_exists("seats", "uq_seats_user_class"):
            batch_op.create_unique_constraint("uq_seats_user_class", ["user_id", "class_id"])

    if not _index_exists("seats", "ix_seats_class_id"):
        op.create_index("ix_seats_class_id", "seats", ["class_id"], unique=False)
    if not _index_exists("seats", "ix_seats_roster_fingerprint"):
        op.create_index("ix_seats_roster_fingerprint", "seats", ["roster_fingerprint"], unique=False)


def downgrade() -> None:
    if _index_exists("seats", "ix_seats_roster_fingerprint"):
        op.drop_index("ix_seats_roster_fingerprint", table_name="seats")
    if _index_exists("seats", "ix_seats_class_id"):
        op.drop_index("ix_seats_class_id", table_name="seats")

    with op.batch_alter_table("seats") as batch_op:
        if _unique_exists("seats", "uq_seats_user_class"):
            batch_op.drop_constraint("uq_seats_user_class", type_="unique")
        if not _unique_exists("seats", "uq_seats_user_join_code"):
            batch_op.create_unique_constraint("uq_seats_user_join_code", ["user_id", "join_code"])
        if _foreign_key_exists("seats", "seats_class_id_fkey"):
            batch_op.drop_constraint("seats_class_id_fkey", type_="foreignkey")

        for column_name in ("claimed_at", "dedupe_code", "roster_fingerprint", "block_identifier", "role", "class_id"):
            if _column_exists("seats", column_name):
                batch_op.drop_column(column_name)
