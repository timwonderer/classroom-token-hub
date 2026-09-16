"""Remove authentication principals from classroom records (INV-ARC-019).

No financial facts or accepted replay digests are rewritten. Legacy bulk-command
reservations cannot be replayed without principal material, so their presence
blocks this pre-launch migration pending an explicit data disposition decision.
"""
import hashlib
import json
import importlib.util
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = 'c7a7b8c9d0e1'
down_revision = 'b6f6a7b8c9d0'
branch_labels = None
depends_on = None

_path = Path(__file__).with_name('f1a9c3e60b72_enforce_ledger_immutability_in_database.py')
_spec = importlib.util.spec_from_file_location('_original_ledger_guard', _path)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)
_IMMUTABLE_COLUMNS = tuple(c for c in _guard._IMMUTABLE_COLUMNS if c != 'user_id')
_WRITE_ONCE_COLUMNS = _guard._WRITE_ONCE_COLUMNS


def _columns(conn, table):
    return {c['name'] for c in sa.inspect(conn).get_columns(table)}


def _assert_replay_history_supported(conn):
    unsupported = conn.execute(sa.text(
        "SELECT id FROM ledger_command_reservation WHERE fingerprint_version NOT IN (1,2,3) "
        "OR fingerprint_version IS NULL LIMIT 1"
    )).first()
    if unsupported:
        raise RuntimeError('Seat-ownership migration found an unsupported replay fingerprint version')
    # Prove legacy two-effect commands use the principal-free transfer serializer.
    # Type labels alone cannot distinguish a transfer from a generic effect plan.
    legacy = conn.execute(sa.text("""
        SELECT r.id, r.replay_fingerprint FROM ledger_command_reservation r
        JOIN ledger_transaction t ON t.command_reservation_id = r.id
        WHERE r.fingerprint_version < 3
        GROUP BY r.id HAVING COUNT(*) > 1
    """)).mappings().all()
    for reservation in legacy:
        effects = conn.execute(sa.text("""SELECT seat_id, target_seat_id, actor_seat_id,
            amount, account_type, type FROM ledger_transaction
            WHERE command_reservation_id=:id ORDER BY id"""), {'id': reservation['id']}).mappings().all()
        is_transfer = len(effects) == 2 and [row['type'] for row in effects] == ['Withdrawal', 'Deposit']
        if is_transfer:
            debit, credit = effects
            seat_id = debit['seat_id']
            is_transfer = (debit['amount'] < 0 and credit['amount'] == -debit['amount']
                and debit['account_type'] != credit['account_type']
                and all(row[key] == seat_id for row in effects
                        for key in ('seat_id', 'target_seat_id', 'actor_seat_id')))
        if is_transfer:
            representation = {
                'account_type': f"{debit['account_type']}->{credit['account_type']}",
                'actor_seat_id': seat_id, 'target_seat_id': seat_id,
                'amount': str(credit['amount']), 'type': 'internal_transfer',
                'original_transaction_id': None, 'policy_id': None,
            }
            digest = hashlib.sha256(json.dumps(representation, sort_keys=True,
                separators=(',', ':'), default=str).encode()).hexdigest()
            is_transfer = digest == reservation['replay_fingerprint']
        if not is_transfer:
            raise RuntimeError('Seat-ownership migration blocked by legacy multi-effect replay history; '
                               'an explicit pre-launch data disposition is required. No history was rewritten.')


def _replace_author(conn, table, old, new, *, nullable):
    columns = _columns(conn, table)
    if new not in columns:
        op.add_column(table, sa.Column(new, sa.Integer(), nullable=True))
        op.create_foreign_key(f'fk_{table}_{new}_seats', table, 'seats', [new], ['id'], ondelete='CASCADE')
    if old in columns:
        # A unique teacher binding is the only lawful mapping; never guess.
        invalid = conn.execute(sa.text(f'''
            SELECT 1 FROM {table} t WHERE t.{old} IS NOT NULL AND
            (SELECT COUNT(*) FROM seats s WHERE s.user_id=t.{old}
             AND s.class_id=t.class_id AND s.role='teacher') <> 1 LIMIT 1
        ''')).first()
        if invalid:
            raise RuntimeError(f'{table} has an author without exactly one teacher seat in its class')
        conn.execute(sa.text(f'''UPDATE {table} t SET {new}=s.id FROM seats s
            WHERE s.user_id=t.{old} AND s.class_id=t.class_id AND s.role='teacher' AND t.{new} IS NULL '''))
        op.drop_column(table, old)
    mismatched = conn.execute(sa.text(f"""SELECT 1 FROM {table} t
        WHERE t.{new} IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM seats s WHERE s.id=t.{new}
            AND s.class_id=t.class_id AND s.role='teacher') LIMIT 1""")).first()
    if mismatched:
        raise RuntimeError(f'{table} has an author seat outside its teacher class scope')
    if not nullable:
        op.alter_column(table, new, nullable=False)


def upgrade():
    conn = op.get_bind()
    _assert_replay_history_supported(conn)
    for fk in sa.inspect(conn).get_foreign_keys('seats'):
        if fk['constrained_columns'] == ['user_id']:
            op.drop_constraint(fk['name'], 'seats', type_='foreignkey')
    op.create_foreign_key('fk_seats_user_id_users', 'seats', 'users', ['user_id'], ['id'], ondelete='RESTRICT')
    _replace_author(conn, 'announcements', 'user_id', 'created_by_seat_id', nullable=False)
    _replace_author(conn, 'policy_transitions', 'created_by', 'created_by_seat_id', nullable=True)
    _replace_author(conn, 'store_products', 'user_id', 'created_by_seat_id', nullable=True)
    for table, column in (
        ('ledger_transaction', 'user_id'), ('attendance_sessions', 'target_user_id'),
        ('payroll_event', 'target_user_id'),
        ('issues', 'sysadmin_id'), ('audit_events', 'teacher_id'),
    ):
        if column in _columns(conn, table):
            op.drop_column(table, column)
    # Preserve every other immutable/write-once/status guard.
    _guard._IMMUTABLE_COLUMNS = _IMMUTABLE_COLUMNS
    conn.execute(sa.text(_guard._guard_body().replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', 1)))


def downgrade():
    raise RuntimeError('Irreversible schema cleanup: principal references cannot be reconstructed after seat rebinding.')
