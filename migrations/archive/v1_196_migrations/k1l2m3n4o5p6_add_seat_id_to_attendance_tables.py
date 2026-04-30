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

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def unique_constraint_exists(table_name, uq_name):
    """Check if a unique constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        uqs = [uq['name'] for uq in inspector.get_unique_constraints(table_name)]
        return uq_name in uqs
    except Exception:
        return False

def upgrade():
    with op.batch_alter_table("student_blocks", schema=None) as batch_op:
        if not column_exists("student_blocks", "seat_id"):
            batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        if not foreign_key_exists("student_blocks", "fk_student_blocks_seat_id"):
            try:
                batch_op.create_foreign_key("fk_student_blocks_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
            except Exception:
                pass
        if not index_exists("student_blocks", "ix_student_blocks_seat_id"):
            batch_op.create_index("ix_student_blocks_seat_id", ["seat_id"], unique=False)

    if column_exists("student_blocks", "seat_id") and table_exists("seats"):
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
        if not unique_constraint_exists("student_blocks", "uq_student_blocks_seat_period"):
            try:
                batch_op.create_unique_constraint("uq_student_blocks_seat_period", ["seat_id", "period"])
            except Exception:
                pass

    with op.batch_alter_table("tap_events", schema=None) as batch_op:
        if not column_exists("tap_events", "seat_id"):
            batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
        if not foreign_key_exists("tap_events", "fk_tap_events_seat_id"):
            try:
                batch_op.create_foreign_key("fk_tap_events_seat_id", "seats", ["seat_id"], ["id"], ondelete="SET NULL")
            except Exception:
                pass
        if not index_exists("tap_events", "ix_tap_events_seat_id"):
            batch_op.create_index("ix_tap_events_seat_id", ["seat_id"], unique=False)
        if not index_exists("tap_events", "ix_tap_event_seat_period_timestamp"):
            batch_op.create_index(
                "ix_tap_event_seat_period_timestamp",
                ["seat_id", "period", "timestamp"],
                unique=False,
            )

    if column_exists("tap_events", "seat_id") and table_exists("seats"):
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
        if index_exists("tap_events", "ix_tap_event_seat_period_timestamp"):
            batch_op.drop_index("ix_tap_event_seat_period_timestamp")
        if index_exists("tap_events", "ix_tap_events_seat_id"):
            batch_op.drop_index("ix_tap_events_seat_id")
        if foreign_key_exists("tap_events", "fk_tap_events_seat_id"):
            batch_op.drop_constraint("fk_tap_events_seat_id", type_="foreignkey")
        if column_exists("tap_events", "seat_id"):
            batch_op.drop_column("seat_id")

    with op.batch_alter_table("student_blocks", schema=None) as batch_op:
        if unique_constraint_exists("student_blocks", "uq_student_blocks_seat_period"):
            batch_op.drop_constraint("uq_student_blocks_seat_period", type_="unique")
        if index_exists("student_blocks", "ix_student_blocks_seat_id"):
            batch_op.drop_index("ix_student_blocks_seat_id")
        if foreign_key_exists("student_blocks", "fk_student_blocks_seat_id"):
            batch_op.drop_constraint("fk_student_blocks_seat_id", type_="foreignkey")
        if column_exists("student_blocks", "seat_id"):
            batch_op.drop_column("seat_id")
