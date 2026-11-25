"""Add audit_events, chain_heads, integrity_status tables

Revision ID: 3447255cb1af
Revises: 0002a
Create Date: 2026-05-11 05:08:15.915207

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3447255cb1af'
down_revision = '0002a'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # ---- audit_events ---------------------------------------------------------
    if not table_exists('audit_events'):
        op.create_table(
            'audit_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('chain_scope', sa.String(length=64), nullable=False),
            sa.Column('sequence_number', sa.Integer(), nullable=False),
            sa.Column('previous_hash', sa.String(length=64), nullable=False),
            sa.Column('event_hash', sa.String(length=64), nullable=False),
            sa.Column('table_name', sa.String(length=64), nullable=False),
            sa.Column('row_pk', sa.String(length=64), nullable=False),
            sa.Column('operation', sa.String(length=16), nullable=False),
            sa.Column('actor_type', sa.String(length=32), nullable=True),
            sa.Column('actor_id_hash', sa.String(length=64), nullable=True),
            sa.Column('class_id', sa.String(length=36), nullable=True),
            sa.Column('seat_id', sa.Integer(), nullable=True),
            sa.Column('teacher_id', sa.Integer(), nullable=True),
            sa.Column('feat_id', sa.String(length=32), nullable=True),
            sa.Column('idempotency_key', sa.String(length=128), nullable=True),
            sa.Column('correlation_id', sa.String(length=64), nullable=True),
            sa.Column('request_id', sa.String(length=64), nullable=True),
            sa.Column('payload_digest', sa.String(length=64), nullable=False),
            sa.Column('context_digest', sa.String(length=64), nullable=False),
            sa.Column('created_at_utc', sa.DateTime(timezone=True), nullable=False),
            sa.Column('signer_key_id', sa.String(length=16), nullable=False),
            sa.Column('signature_version', sa.Integer(), nullable=False),
            sa.Column('hmac_signature', sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('chain_scope', 'sequence_number', name='uq_audit_chain_position'),
            sa.UniqueConstraint('event_hash'),
        )
        print("✅ Created audit_events")
    else:
        print("⚠️  Table 'audit_events' already exists, skipping...")

    for idx_name, cols in [
        ('ix_audit_events_chain_scope', ['chain_scope']),
        ('ix_audit_events_class_id', ['class_id']),
        ('ix_audit_events_correlation_id', ['correlation_id']),
        ('ix_audit_events_table_row', ['table_name', 'row_pk']),
    ]:
        if not index_exists('audit_events', idx_name):
            op.create_index(idx_name, 'audit_events', cols, unique=False)

    # ---- chain_heads ----------------------------------------------------------
    if not table_exists('chain_heads'):
        op.create_table(
            'chain_heads',
            sa.Column('chain_scope', sa.String(length=64), nullable=False),
            sa.Column('latest_hash', sa.String(length=64), nullable=False),
            sa.Column('latest_sequence', sa.Integer(), nullable=False),
            sa.Column('event_count', sa.Integer(), nullable=False),
            sa.Column('last_updated_utc', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('chain_scope'),
        )
        print("✅ Created chain_heads")

        conn = op.get_bind()
        conn.execute(sa.text(
            "INSERT INTO chain_heads (chain_scope, latest_hash, latest_sequence, event_count, last_updated_utc) "
            "VALUES ('system', 'genesis', 0, 0, now() AT TIME ZONE 'UTC') "
            "ON CONFLICT (chain_scope) DO NOTHING"
        ))
        print("✅ Inserted system genesis chain head")
    else:
        print("⚠️  Table 'chain_heads' already exists, skipping...")

    # ---- integrity_status -----------------------------------------------------
    if not table_exists('integrity_status'):
        op.create_table(
            'integrity_status',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('passing', sa.Boolean(), nullable=False),
            sa.Column('last_checked_utc', sa.DateTime(timezone=True), nullable=True),
            sa.Column('failure_detail', sa.Text(), nullable=True),
            sa.Column('degraded_since', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        print("✅ Created integrity_status")

        conn = op.get_bind()
        conn.execute(sa.text(
            "INSERT INTO integrity_status (passing, last_checked_utc) "
            "VALUES (true, now() AT TIME ZONE 'UTC')"
        ))
        print("✅ Seeded integrity_status")
    else:
        print("⚠️  Table 'integrity_status' already exists, skipping...")


def downgrade():
    if table_exists('integrity_status'):
        op.drop_table('integrity_status')
        print("❌ Dropped integrity_status")

    if table_exists('chain_heads'):
        op.drop_table('chain_heads')
        print("❌ Dropped chain_heads")

    for idx_name in (
        'ix_audit_events_table_row',
        'ix_audit_events_correlation_id',
        'ix_audit_events_class_id',
        'ix_audit_events_chain_scope',
    ):
        if index_exists('audit_events', idx_name):
            op.drop_index(idx_name, table_name='audit_events')

    if table_exists('audit_events'):
        op.drop_table('audit_events')
        print("❌ Dropped audit_events")
