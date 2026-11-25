"""Rename TLCP actor identity columns to actor_public_id.

Revision ID: f6a7b8c9d0e1
Revises: ebb7b66b2176
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "ebb7b66b2176"
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
        columns = [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False
    return column_name in columns


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [index["name"] for index in inspector.get_indexes(table_name)]
    except Exception:
        return False
    return index_name in indexes


def _drop_index_if_exists(table_name, index_name):
    if table_exists(table_name) and index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _rename_or_converge_column(table_name, old_name, new_name, column_type, nullable):
    if not table_exists(table_name):
        return

    old_exists = column_exists(table_name, old_name)
    new_exists = column_exists(table_name, new_name)

    if old_exists and not new_exists:
        op.alter_column(
            table_name,
            old_name,
            new_column_name=new_name,
            existing_type=column_type,
            existing_nullable=nullable,
        )
        return

    if old_exists and new_exists:
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET {new_name} = {old_name}
                WHERE {new_name} IS NULL
                  AND {old_name} IS NOT NULL
                """
            )
        )
        op.drop_column(table_name, old_name)


def _create_index_if_missing(table_name, index_name, columns):
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _rename_tlcp_columns(old_name, new_name, *, old_indexes, new_indexes):
    for table_name, index_name in old_indexes:
        _drop_index_if_exists(table_name, index_name)

    _rename_or_converge_column(
        "actor_request_trace",
        old_name,
        new_name,
        sa.String(length=64),
        False,
    )
    _rename_or_converge_column(
        "error_events",
        old_name,
        new_name,
        sa.String(length=64),
        True,
    )
    _rename_or_converge_column(
        "ticket_correlation_pack",
        old_name,
        new_name,
        sa.String(length=64),
        False,
    )

    for table_name, index_name, columns in new_indexes:
        if column_exists(table_name, new_name):
            _create_index_if_missing(table_name, index_name, columns)


def upgrade():
    _rename_tlcp_columns(
        "actor_opaque_id",
        "actor_public_id",
        old_indexes=(
            ("actor_request_trace", "ix_actor_request_trace_actor_opaque_id"),
            ("actor_request_trace", "ix_actor_trace_actor_created"),
            ("error_events", "ix_error_events_actor_opaque_id"),
            ("error_events", "ix_error_events_actor_created"),
            ("ticket_correlation_pack", "ix_ticket_correlation_actor"),
        ),
        new_indexes=(
            ("actor_request_trace", "ix_actor_request_trace_actor_public_id", ["actor_public_id"]),
            (
                "actor_request_trace",
                "ix_actor_trace_actor_public_created",
                ["actor_type", "actor_public_id", "created_at"],
            ),
            ("error_events", "ix_error_events_actor_public_id", ["actor_public_id"]),
            (
                "error_events",
                "ix_error_events_actor_public_created",
                ["actor_type", "actor_public_id", "created_at"],
            ),
            (
                "ticket_correlation_pack",
                "ix_ticket_correlation_actor_public",
                ["actor_type", "actor_public_id"],
            ),
        ),
    )


def downgrade():
    _rename_tlcp_columns(
        "actor_public_id",
        "actor_opaque_id",
        old_indexes=(
            ("actor_request_trace", "ix_actor_request_trace_actor_public_id"),
            ("actor_request_trace", "ix_actor_trace_actor_public_created"),
            ("error_events", "ix_error_events_actor_public_id"),
            ("error_events", "ix_error_events_actor_public_created"),
            ("ticket_correlation_pack", "ix_ticket_correlation_actor_public"),
        ),
        new_indexes=(
            ("actor_request_trace", "ix_actor_request_trace_actor_opaque_id", ["actor_opaque_id"]),
            (
                "actor_request_trace",
                "ix_actor_trace_actor_created",
                ["actor_type", "actor_opaque_id", "created_at"],
            ),
            ("error_events", "ix_error_events_actor_opaque_id", ["actor_opaque_id"]),
            (
                "error_events",
                "ix_error_events_actor_created",
                ["actor_type", "actor_opaque_id", "created_at"],
            ),
            (
                "ticket_correlation_pack",
                "ix_ticket_correlation_actor",
                ["actor_type", "actor_opaque_id"],
            ),
        ),
    )
