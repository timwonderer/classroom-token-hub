"""Add seat_id to transaction and balance_cache with legacy backfill.

Revision ID: j1k2l3m4n5o6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j1k2l3m4n5o6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transaction", schema=None) as batch_op:
        batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_transaction_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_transaction_seat_id", ["seat_id"], unique=False)
        batch_op.create_index(
            "ix_transaction_seat_ledger",
            ["join_code", "seat_id", "status", "account_type"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE "transaction"
            SET seat_id = (
                SELECT s.id
                FROM seats s
                WHERE s.student_id = "transaction".student_id
                  AND s.join_code = "transaction".join_code
                LIMIT 1
            )
            WHERE seat_id IS NULL
              AND join_code IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_balance_cache_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_balance_cache_seat_id", ["seat_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE balance_cache
            SET seat_id = (
                SELECT s.id
                FROM seats s
                WHERE s.student_id = balance_cache.student_id
                  AND s.join_code = balance_cache.join_code
                LIMIT 1
            )
            WHERE seat_id IS NULL
            """
        )
    )

    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_balance_cache_seat_scope", ["join_code", "seat_id"])


def downgrade():
    with op.batch_alter_table("balance_cache", schema=None) as batch_op:
        batch_op.drop_constraint("uq_balance_cache_seat_scope", type_="unique")
        batch_op.drop_index("ix_balance_cache_seat_id")
        batch_op.drop_constraint("fk_balance_cache_seat_id", type_="foreignkey")
        batch_op.drop_column("seat_id")

    with op.batch_alter_table("transaction", schema=None) as batch_op:
        batch_op.drop_index("ix_transaction_seat_ledger")
        batch_op.drop_index("ix_transaction_seat_id")
        batch_op.drop_constraint("fk_transaction_seat_id", type_="foreignkey")
        batch_op.drop_column("seat_id")
