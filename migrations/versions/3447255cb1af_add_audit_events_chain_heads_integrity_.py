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


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


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

        # Genesis row for the system chain
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

        # Seed the single-row status record
        conn = op.get_bind()
        conn.execute(sa.text(
            "INSERT INTO integrity_status (passing, last_checked_utc) "
            "VALUES (true, now() AT TIME ZONE 'UTC')"
        ))
        print("✅ Seeded integrity_status")
    else:
        print("⚠️  Table 'integrity_status' already exists, skipping...")

    # ---- classes index / constraint -------------------------------------------
    if index_exists('classes', 'ix_classes_created_by'):
        op.drop_index('ix_classes_created_by', table_name='classes')
    if constraint_exists('classes', 'uq_classes_class_id'):
        op.drop_constraint('uq_classes_class_id', 'classes', type_='unique')
    if not index_exists('classes', 'ix_classes_created_by_admin_id'):
        op.create_index('ix_classes_created_by_admin_id', 'classes', ['created_by_admin_id'], unique=False)

    # ---- rent_payments columns ------------------------------------------------
    if not column_exists('rent_payments', 'coverage_start_time'):
        with op.batch_alter_table('rent_payments') as batch_op:
            batch_op.add_column(sa.Column('coverage_start_time', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('rent_payments', 'coverage_end_time'):
        with op.batch_alter_table('rent_payments') as batch_op:
            batch_op.add_column(sa.Column('coverage_end_time', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('rent_payments', 'cycle_idempotency_key'):
        with op.batch_alter_table('rent_payments') as batch_op:
            batch_op.add_column(sa.Column('cycle_idempotency_key', sa.String(length=160), nullable=True))

    for idx_name, cols in [
        ('ix_rent_payments_coverage_end_time', ['coverage_end_time']),
        ('ix_rent_payments_coverage_start_time', ['coverage_start_time']),
        ('ix_rent_payments_cycle_idempotency_key', ['cycle_idempotency_key']),
    ]:
        if not index_exists('rent_payments', idx_name):
            op.create_index(idx_name, 'rent_payments', cols, unique=False)

    if not constraint_exists('rent_payments', 'uq_rent_payment_cycle_seat_class'):
        op.create_unique_constraint(
            'uq_rent_payment_cycle_seat_class',
            'rent_payments',
            ['seat_id', 'class_id', 'cycle_idempotency_key'],
        )

    # ---- rent_settings columns ------------------------------------------------
    if not column_exists('rent_settings', 'rent_configured_at'):
        with op.batch_alter_table('rent_settings') as batch_op:
            batch_op.add_column(sa.Column('rent_configured_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('rent_settings', 'rent_effective_at'):
        with op.batch_alter_table('rent_settings') as batch_op:
            batch_op.add_column(sa.Column('rent_effective_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('rent_settings', 'cycle_length_days'):
        with op.batch_alter_table('rent_settings') as batch_op:
            batch_op.add_column(sa.Column('cycle_length_days', sa.Integer(), nullable=True))
        # Backfill default (7 days) before enforcing NOT NULL
        conn = op.get_bind()
        conn.execute(sa.text("UPDATE rent_settings SET cycle_length_days = 7 WHERE cycle_length_days IS NULL"))

    for idx_name, cols in [
        ('ix_rent_settings_rent_configured_at', ['rent_configured_at']),
        ('ix_rent_settings_rent_effective_at', ['rent_effective_at']),
    ]:
        if not index_exists('rent_settings', idx_name):
            op.create_index(idx_name, 'rent_settings', cols, unique=False)

    # ---- seats column ---------------------------------------------------------
    if not column_exists('seats', 'has_received_rent_exemption'):
        with op.batch_alter_table('seats') as batch_op:
            batch_op.add_column(sa.Column('has_received_rent_exemption', sa.Boolean(), nullable=True))
        conn = op.get_bind()
        conn.execute(sa.text("UPDATE seats SET has_received_rent_exemption = false WHERE has_received_rent_exemption IS NULL"))


def downgrade():
    # ---- seats column ---------------------------------------------------------
    if column_exists('seats', 'has_received_rent_exemption'):
        with op.batch_alter_table('seats') as batch_op:
            batch_op.drop_column('has_received_rent_exemption')

    # ---- rent_settings columns ------------------------------------------------
    if index_exists('rent_settings', 'ix_rent_settings_rent_effective_at'):
        op.drop_index('ix_rent_settings_rent_effective_at', table_name='rent_settings')
    if index_exists('rent_settings', 'ix_rent_settings_rent_configured_at'):
        op.drop_index('ix_rent_settings_rent_configured_at', table_name='rent_settings')
    for col in ('cycle_length_days', 'rent_effective_at', 'rent_configured_at'):
        if column_exists('rent_settings', col):
            with op.batch_alter_table('rent_settings') as batch_op:
                batch_op.drop_column(col)

    # ---- rent_payments columns ------------------------------------------------
    if constraint_exists('rent_payments', 'uq_rent_payment_cycle_seat_class'):
        op.drop_constraint('uq_rent_payment_cycle_seat_class', 'rent_payments', type_='unique')
    for idx_name in (
        'ix_rent_payments_cycle_idempotency_key',
        'ix_rent_payments_coverage_start_time',
        'ix_rent_payments_coverage_end_time',
    ):
        if index_exists('rent_payments', idx_name):
            op.drop_index(idx_name, table_name='rent_payments')
    for col in ('cycle_idempotency_key', 'coverage_end_time', 'coverage_start_time'):
        if column_exists('rent_payments', col):
            with op.batch_alter_table('rent_payments') as batch_op:
                batch_op.drop_column(col)

    # ---- classes index / constraint -------------------------------------------
    if index_exists('classes', 'ix_classes_created_by_admin_id'):
        op.drop_index('ix_classes_created_by_admin_id', table_name='classes')

    # ---- audit lineage tables -------------------------------------------------
    if table_exists('integrity_status'):
        op.drop_table('integrity_status')
    if table_exists('chain_heads'):
        op.drop_table('chain_heads')
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
