"""Add seat_id to hall_pass_logs, rent_payments, and rent_waivers.

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "l1m2n3o4p5q6"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name: str, fk_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def _add_and_backfill(table_name: str):
    if not column_exists(table_name, "seat_id"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))

    fk_name = f"fk_{table_name}_seat_id"
    if not foreign_key_exists(table_name, fk_name):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_foreign_key(
                fk_name,
                "seats",
                ["seat_id"],
                ["id"],
                ondelete="SET NULL",
            )

    idx_name = f"ix_{table_name}_seat_id"
    if not index_exists(table_name, idx_name):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_index(idx_name, ["seat_id"], unique=False)

    op.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET seat_id = (
                SELECT s.id
                FROM seats s
                WHERE s.student_id = {table_name}.student_id
                  AND s.join_code = {table_name}.join_code
                LIMIT 1
            )
            WHERE seat_id IS NULL
              AND join_code IS NOT NULL
            """
        )
    )


def _drop(table_name: str):
    idx_name = f"ix_{table_name}_seat_id"
    fk_name = f"fk_{table_name}_seat_id"
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if index_exists(table_name, idx_name):
            batch_op.drop_index(idx_name)
        if foreign_key_exists(table_name, fk_name):
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        if column_exists(table_name, "seat_id"):
            batch_op.drop_column("seat_id")


def upgrade():
    _add_and_backfill("hall_pass_logs")
    _add_and_backfill("rent_payments")
    _add_and_backfill("rent_waivers")


def downgrade():
    _drop("rent_waivers")
    _drop("rent_payments")
    _drop("hall_pass_logs")
