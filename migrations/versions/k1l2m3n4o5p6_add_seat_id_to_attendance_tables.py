"""Add seat_id to tap_events and student_blocks with backfill.

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k1l2m3n4o5p6"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("student_blocks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_student_blocks_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_student_blocks_seat_id", ["seat_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE student_blocks
            SET seat_id = (
                SELECT s.id
                FROM seats s
                WHERE s.student_id = student_blocks.student_id
                  AND s.join_code = student_blocks.join_code
                LIMIT 1
            )
            WHERE seat_id IS NULL
              AND join_code IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("student_blocks", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_student_blocks_seat_period", ["seat_id", "period"])

    with op.batch_alter_table("tap_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_tap_events_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_tap_events_seat_id", ["seat_id"], unique=False)
        batch_op.create_index(
            "ix_tap_event_seat_period_timestamp",
            ["seat_id", "period", "timestamp"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE tap_events
            SET seat_id = (
                SELECT s.id
                FROM seats s
                WHERE s.student_id = tap_events.student_id
                  AND s.join_code = tap_events.join_code
                LIMIT 1
            )
            WHERE seat_id IS NULL
              AND join_code IS NOT NULL
            """
        )
    )


def downgrade():
    with op.batch_alter_table("tap_events", schema=None) as batch_op:
        batch_op.drop_index("ix_tap_event_seat_period_timestamp")
        batch_op.drop_index("ix_tap_events_seat_id")
        batch_op.drop_constraint("fk_tap_events_seat_id", type_="foreignkey")
        batch_op.drop_column("seat_id")

    with op.batch_alter_table("student_blocks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_student_blocks_seat_period", type_="unique")
        batch_op.drop_index("ix_student_blocks_seat_id")
        batch_op.drop_constraint("fk_student_blocks_seat_id", type_="foreignkey")
        batch_op.drop_column("seat_id")
