"""Add reason_code enum to TapEvent

Revision ID: 3d54e2e343df
Revises: d2e4f6a8b0c1
Create Date: 2026-02-26 08:00:00.000000

Adds a reason_code enum column to tap_events to programmatically identify
different types of tap events without relying on string matching.
"""
from alembic import op
import sqlalchemy as sa


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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


# revision identifiers, used by Alembic.
revision = '3d54e2e343df'
down_revision = 'b6c7d8e9f0a1'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('tap_events'):
        if not column_exists('tap_events', 'reason_code'):
            op.add_column(
                'tap_events',
                sa.Column(
                    'reason_code',
                    sa.Enum('daily_limit', 'auto_switch', name='tapeventreasoncode'),
                    nullable=True
                )
            )

        if not index_exists('tap_events', 'ix_tap_events_reason_code'):
            op.create_index('ix_tap_events_reason_code', 'tap_events', ['reason_code'], unique=False)

        # Backfill reason_code for existing tap_events so historical data
        # continues to work with reason_code-based filtering and deduplication.
        op.execute(
            sa.text(
                "UPDATE tap_events "
                "SET reason_code = 'daily_limit' "
                "WHERE reason_code IS NULL AND reason LIKE 'Daily limit%'"
            )
        )
        op.execute(
            sa.text(
                "UPDATE tap_events "
                "SET reason_code = 'auto_switch' "
                "WHERE reason_code IS NULL AND reason = 'auto_switch'"
            )
        )


def downgrade():
    if table_exists('tap_events'):
        if index_exists('tap_events', 'ix_tap_events_reason_code'):
            op.drop_index('ix_tap_events_reason_code', table_name='tap_events')

        if column_exists('tap_events', 'reason_code'):
            op.drop_column('tap_events', 'reason_code')

    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        conn.execute(sa.text("DROP TYPE IF EXISTS tapeventreasoncode"))
