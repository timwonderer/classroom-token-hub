"""Create operational_events table (DOM-OPS-001 SS5 Derived Schema)

A prior migration (7c3d4e5f6a7b_drop_all_unauthorized_tables) dropped the
legacy error_logs/error_events tables on the stated rationale that they were
"absorbed into operational_events (DOM-OPS-001)" -- but no migration ever
created that replacement table. operational_event_service.get_recent_error_events()
/ get_error_events() have been querying it ever since; every hit 500s with
UndefinedTable. Confirmed live: GET /sysadmin/dashboard -> 500,
psycopg2.errors.UndefinedTable: relation "operational_events" does not exist,
at app/routes/system_admin.py's dashboard() -> get_recent_error_events().

Schema matches DOM-OPS-001 SS5 exactly (UUID id and correlation_id represented
as String(36), matching this codebase's existing convention for UUID columns
rather than a native Postgres UUID type introduced for the first time here).

Revision ID: b8e1f4c2a5d9
Revises: a3c7d9e1b204
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8e1f4c2a5d9'
down_revision = 'a3c7d9e1b204'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    if not table_exists(table_name):
        return False
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(idx['name'] == index_name for idx in inspector.get_indexes(table_name))


def upgrade():
    if not table_exists('operational_events'):
        op.create_table(
            'operational_events',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('correlation_id', sa.String(length=64), nullable=True),
            sa.Column('domain', sa.String(length=100), nullable=False),
            sa.Column('level', sa.String(length=20), nullable=False),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True),
        )
        print("✅ Created operational_events")
    else:
        print("⚠️  operational_events already exists, skipping...")

    if not index_exists('operational_events', 'ix_operational_events_created_at'):
        op.create_index(
            'ix_operational_events_created_at', 'operational_events', ['created_at'],
        )
        print("✅ Created ix_operational_events_created_at")

    if not index_exists('operational_events', 'ix_operational_events_level'):
        op.create_index(
            'ix_operational_events_level', 'operational_events', ['level'],
        )
        print("✅ Created ix_operational_events_level")

    if not index_exists('operational_events', 'ix_operational_events_domain'):
        op.create_index(
            'ix_operational_events_domain', 'operational_events', ['domain'],
        )
        print("✅ Created ix_operational_events_domain")

    if not index_exists('operational_events', 'ix_operational_events_correlation_id'):
        op.create_index(
            'ix_operational_events_correlation_id', 'operational_events', ['correlation_id'],
        )
        print("✅ Created ix_operational_events_correlation_id")


def downgrade():
    if table_exists('operational_events'):
        op.drop_table('operational_events')
        print("❌ Dropped operational_events")
    else:
        print("⚠️  operational_events does not exist, skipping...")
