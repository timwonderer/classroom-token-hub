"""Create obligation_command_reservation (DOM-OBL-001 v3.1 §V.7 replay identity)

DOM-OBL-001 v3.1 makes bill-cycle succession idempotent on command identity
rather than on the shape of the row it writes. bill_cycles carries no command
identity, so the identity is recorded here: one row per succession command,
scoped by (class_id, command_name, idempotency_key), carrying the request
fingerprint it was accepted under and the bill_cycles row it produced.

The uq_bill_cycles_ref_cycle constraint stays the integrity backstop for two
distinct commands racing for the same derived successor; this table is the
idempotency mechanism.

Revision ID: c4d6e8f0a2b3
Revises: b8e1f4c2a5d9
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d6e8f0a2b3'
down_revision = 'b8e1f4c2a5d9'
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
    if not table_exists('obligation_command_reservation'):
        op.create_table(
            'obligation_command_reservation',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('command_name', sa.String(length=100), nullable=False),
            sa.Column('idempotency_key', sa.String(length=255), nullable=False),
            sa.Column('internal_ref', sa.String(length=200), nullable=False),
            sa.Column('replay_fingerprint', sa.String(length=128), nullable=False),
            sa.Column('fingerprint_version', sa.Integer(), nullable=False),
            sa.Column('bill_cycle_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['bill_cycle_id'], ['bill_cycles.id'], ondelete='CASCADE'),
            sa.UniqueConstraint(
                'class_id', 'command_name', 'idempotency_key',
                name='uq_obligation_command_reservation_identity',
            ),
        )
        print("✅ Created obligation_command_reservation")
    else:
        print("⚠️  obligation_command_reservation already exists, skipping...")

    if not index_exists('obligation_command_reservation', 'ix_obligation_command_reservation_class_id'):
        op.create_index(
            'ix_obligation_command_reservation_class_id',
            'obligation_command_reservation', ['class_id'],
        )
        print("✅ Created ix_obligation_command_reservation_class_id")

    if not index_exists('obligation_command_reservation', 'ix_obligation_command_reservation_bill_cycle_id'):
        op.create_index(
            'ix_obligation_command_reservation_bill_cycle_id',
            'obligation_command_reservation', ['bill_cycle_id'],
        )
        print("✅ Created ix_obligation_command_reservation_bill_cycle_id")


def downgrade():
    if table_exists('obligation_command_reservation'):
        op.drop_table('obligation_command_reservation')
        print("❌ Dropped obligation_command_reservation")
    else:
        print("⚠️  obligation_command_reservation does not exist, skipping...")
