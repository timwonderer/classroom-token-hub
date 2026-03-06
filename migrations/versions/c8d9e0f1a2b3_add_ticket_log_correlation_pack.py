"""add ticket log correlation pack tables

Revision ID: c8d9e0f1a2b3
Revises: 6c7d8e9f0a1b
Create Date: 2026-03-05 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "6c7d8e9f0a1b"
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
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def _create_actor_request_trace():
    if not table_exists("actor_request_trace"):
        op.create_table(
            "actor_request_trace",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_type", sa.String(length=20), nullable=False),
            sa.Column("actor_opaque_id", sa.String(length=64), nullable=False),
            sa.Column("join_code_id", sa.String(length=36), nullable=True),
            sa.Column("request_id", sa.String(length=128), nullable=False),
            sa.Column("method", sa.String(length=10), nullable=False),
            sa.Column("endpoint", sa.String(length=500), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["join_code_id"], ["join_codes.join_code_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_request_trace_actor_opaque_id"):
        op.create_index(
            "ix_actor_request_trace_actor_opaque_id",
            "actor_request_trace",
            ["actor_opaque_id"],
            unique=False,
        )
    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_request_trace_actor_type"):
        op.create_index(
            "ix_actor_request_trace_actor_type",
            "actor_request_trace",
            ["actor_type"],
            unique=False,
        )
    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_request_trace_created_at"):
        op.create_index(
            "ix_actor_request_trace_created_at",
            "actor_request_trace",
            ["created_at"],
            unique=False,
        )
    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_request_trace_join_code_id"):
        op.create_index(
            "ix_actor_request_trace_join_code_id",
            "actor_request_trace",
            ["join_code_id"],
            unique=False,
        )
    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_request_trace_request_id"):
        op.create_index(
            "ix_actor_request_trace_request_id",
            "actor_request_trace",
            ["request_id"],
            unique=False,
        )
    if table_exists("actor_request_trace") and not index_exists("actor_request_trace", "ix_actor_trace_actor_created"):
        op.create_index(
            "ix_actor_trace_actor_created",
            "actor_request_trace",
            ["actor_type", "actor_opaque_id", "created_at"],
            unique=False,
        )


def _create_error_events():
    if not table_exists("error_events"):
        op.create_table(
            "error_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.String(length=128), nullable=True),
            sa.Column("actor_type", sa.String(length=20), nullable=True),
            sa.Column("actor_opaque_id", sa.String(length=64), nullable=True),
            sa.Column("join_code_id", sa.String(length=36), nullable=True),
            sa.Column("endpoint", sa.String(length=500), nullable=True),
            sa.Column("method", sa.String(length=10), nullable=True),
            sa.Column("error_class", sa.String(length=200), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("correlation_version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["join_code_id"], ["join_codes.join_code_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_actor_created"):
        op.create_index(
            "ix_error_events_actor_created",
            "error_events",
            ["actor_type", "actor_opaque_id", "created_at"],
            unique=False,
        )
    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_actor_opaque_id"):
        op.create_index(
            "ix_error_events_actor_opaque_id",
            "error_events",
            ["actor_opaque_id"],
            unique=False,
        )
    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_actor_type"):
        op.create_index(
            "ix_error_events_actor_type",
            "error_events",
            ["actor_type"],
            unique=False,
        )
    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_created_at"):
        op.create_index(
            "ix_error_events_created_at",
            "error_events",
            ["created_at"],
            unique=False,
        )
    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_join_code_id"):
        op.create_index(
            "ix_error_events_join_code_id",
            "error_events",
            ["join_code_id"],
            unique=False,
        )
    if table_exists("error_events") and not index_exists("error_events", "ix_error_events_request_id"):
        op.create_index(
            "ix_error_events_request_id",
            "error_events",
            ["request_id"],
            unique=False,
        )


def _create_ticket_correlation_pack():
    if not table_exists("ticket_correlation_pack"):
        op.create_table(
            "ticket_correlation_pack",
            sa.Column("issue_id", sa.Integer(), nullable=False),
            sa.Column("correlation_version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("actor_type", sa.String(length=20), nullable=False),
            sa.Column("actor_opaque_id", sa.String(length=64), nullable=False),
            sa.Column("join_code_id", sa.String(length=36), nullable=True),
            sa.Column("request_trace_json", sa.JSON(), nullable=False),
            sa.Column("error_refs_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["join_code_id"], ["join_codes.join_code_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("issue_id"),
        )

    if table_exists("ticket_correlation_pack") and not index_exists("ticket_correlation_pack", "ix_ticket_correlation_actor"):
        op.create_index(
            "ix_ticket_correlation_actor",
            "ticket_correlation_pack",
            ["actor_type", "actor_opaque_id"],
            unique=False,
        )


def upgrade():
    _create_actor_request_trace()
    _create_error_events()
    _create_ticket_correlation_pack()


def downgrade():
    if table_exists("ticket_correlation_pack"):
        if index_exists("ticket_correlation_pack", "ix_ticket_correlation_actor"):
            op.drop_index("ix_ticket_correlation_actor", table_name="ticket_correlation_pack")
        for fk in get_foreign_keys_by_column("ticket_correlation_pack", "join_code_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "ticket_correlation_pack", type_="foreignkey")
        for fk in get_foreign_keys_by_column("ticket_correlation_pack", "issue_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "ticket_correlation_pack", type_="foreignkey")
        op.drop_table("ticket_correlation_pack")

    if table_exists("error_events"):
        if index_exists("error_events", "ix_error_events_request_id"):
            op.drop_index("ix_error_events_request_id", table_name="error_events")
        if index_exists("error_events", "ix_error_events_join_code_id"):
            op.drop_index("ix_error_events_join_code_id", table_name="error_events")
        if index_exists("error_events", "ix_error_events_created_at"):
            op.drop_index("ix_error_events_created_at", table_name="error_events")
        if index_exists("error_events", "ix_error_events_actor_type"):
            op.drop_index("ix_error_events_actor_type", table_name="error_events")
        if index_exists("error_events", "ix_error_events_actor_opaque_id"):
            op.drop_index("ix_error_events_actor_opaque_id", table_name="error_events")
        if index_exists("error_events", "ix_error_events_actor_created"):
            op.drop_index("ix_error_events_actor_created", table_name="error_events")
        for fk in get_foreign_keys_by_column("error_events", "join_code_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "error_events", type_="foreignkey")
        op.drop_table("error_events")

    if table_exists("actor_request_trace"):
        if index_exists("actor_request_trace", "ix_actor_trace_actor_created"):
            op.drop_index("ix_actor_trace_actor_created", table_name="actor_request_trace")
        if index_exists("actor_request_trace", "ix_actor_request_trace_request_id"):
            op.drop_index("ix_actor_request_trace_request_id", table_name="actor_request_trace")
        if index_exists("actor_request_trace", "ix_actor_request_trace_join_code_id"):
            op.drop_index("ix_actor_request_trace_join_code_id", table_name="actor_request_trace")
        if index_exists("actor_request_trace", "ix_actor_request_trace_created_at"):
            op.drop_index("ix_actor_request_trace_created_at", table_name="actor_request_trace")
        if index_exists("actor_request_trace", "ix_actor_request_trace_actor_type"):
            op.drop_index("ix_actor_request_trace_actor_type", table_name="actor_request_trace")
        if index_exists("actor_request_trace", "ix_actor_request_trace_actor_opaque_id"):
            op.drop_index("ix_actor_request_trace_actor_opaque_id", table_name="actor_request_trace")
        for fk in get_foreign_keys_by_column("actor_request_trace", "join_code_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "actor_request_trace", type_="foreignkey")
        op.drop_table("actor_request_trace")
