"""Derive posting from scoped reconciliation, freeze creation sequence and origin.

DOM-LED-001 VI/VII.4/7/8, FEAT-LED-001 and DOM-OPS-002 v2 field coverage.
No historical sequence or signature is invented. Preflight requires existing
admission evidence; unresolved old monetary state aborts before destructive DDL.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e7c2a9d4f610'
down_revision = 'd6b1e0c4a825'
branch_labels = None
depends_on = None

def table_exists(table_name):
    return sa.inspect(op.get_bind()).has_table(table_name)


def column_exists(table_name, column_name):
    return any(c['name'] == column_name for c in sa.inspect(op.get_bind()).get_columns(table_name))


def index_exists(table_name, index_name):
    return any(i['name'] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def check_constraint_exists(table_name, constraint_name):
    return any(c['name'] == constraint_name for c in sa.inspect(op.get_bind()).get_check_constraints(table_name))


IMMUTABLE = (
    'seat_id', 'target_seat_id', 'actor_seat_id', 'class_id', 'join_code',
    'mechanism', 'amount', 'amount_cents', 'timestamp', 'account_type', 'effective_at',
    'date_funds_available', 'description', 'correlation_id', 'original_transaction_id',
    'policy_id', 'type', 'compensation_subtype', 'command_reservation_id',
    'posting_sequence', 'idempotency_key', 'feat_code',
)
WRITE_ONCE = ('posted_at', 'reversal_transaction_id', 'lineage_event_id', 'lineage_token', 'lineage_version')


def _install_guard():
    immutable = IMMUTABLE + tuple(field for field in ('compensation_origin_locator', 'compensation_amount_cents', 'correction_intent_locator') if column_exists('ledger_transaction', field))
    checks = '\n'.join(f"IF OLD.{field} IS DISTINCT FROM NEW.{field} THEN RAISE EXCEPTION 'Immutable Ledger field: {field}'; END IF;" for field in immutable)
    checks += '\n' + '\n'.join(f"IF OLD.{field} IS NOT NULL AND OLD.{field} IS DISTINCT FROM NEW.{field} THEN RAISE EXCEPTION 'Write-once Ledger field: {field}'; END IF;" for field in WRITE_ONCE)
    op.execute(sa.text(f"""CREATE OR REPLACE FUNCTION prevent_ledger_transaction_rewrite()
        RETURNS TRIGGER AS $$ BEGIN {checks} RETURN NEW; END; $$ LANGUAGE plpgsql;"""))
    op.execute(sa.text("""CREATE OR REPLACE FUNCTION require_ledger_creation_sequence()
        RETURNS TRIGGER AS $$ BEGIN
        IF NEW.posting_sequence IS NULL OR NEW.posting_sequence <= 0 THEN
            RAISE EXCEPTION 'New Ledger effects require immutable creation sequence';
        END IF; RETURN NEW; END; $$ LANGUAGE plpgsql;"""))
    op.execute(sa.text("""DROP TRIGGER IF EXISTS ledger_creation_sequence_required ON ledger_transaction; CREATE TRIGGER ledger_creation_sequence_required BEFORE INSERT ON ledger_transaction
        FOR EACH ROW EXECUTE FUNCTION require_ledger_creation_sequence();"""))


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        # Hold admission and monetary evidence fixed throughout preflight and DDL.
        op.execute(sa.text('LOCK TABLE ledger_transaction, ledger_balance_snapshot IN ACCESS EXCLUSIVE MODE'))
        if column_exists('ledger_transaction', 'status'):
            invalid = conn.execute(sa.text("""SELECT count(*) FROM ledger_transaction t
            LEFT JOIN ledger_balance_snapshot s ON s.class_id=t.class_id AND s.seat_id=t.seat_id AND s.account_type=t.account_type
            WHERE t.posting_sequence IS NULL OR t.posting_sequence <= 0 OR t.status::text='VOID'
            OR (t.status::text='POSTED' AND (s.reconciled_through_posting_sequence IS NULL OR t.posting_sequence>s.reconciled_through_posting_sequence))
            OR (t.status::text='PENDING' AND t.posting_sequence<=s.reconciled_through_posting_sequence)""")).scalar()
        else:
            invalid = conn.execute(sa.text('SELECT count(*) FROM ledger_transaction WHERE posting_sequence IS NULL OR posting_sequence <= 0')).scalar()
        if invalid:
            raise RuntimeError('Ledger posting migration blocked: historical sequence/admission evidence requires separate reviewed disposition; no backfill authorized.')
    if column_exists('ledger_transaction', 'status'):
        for name in ('ix_transaction_seat_ledger', 'ix_ledger_transaction_reconstruction_scope'):
            if index_exists('ledger_transaction', name):
                op.drop_index(name, table_name='ledger_transaction')
        op.drop_column('ledger_transaction', 'status')
    if not index_exists('ledger_transaction', 'ix_transaction_seat_ledger'):
        op.create_index('ix_transaction_seat_ledger','ledger_transaction',['join_code','seat_id','account_type'])
    if not index_exists('ledger_transaction', 'ix_ledger_transaction_reconstruction_scope'):
        op.create_index('ix_ledger_transaction_reconstruction_scope','ledger_transaction',['class_id','seat_id','account_type','posting_sequence'])
    if conn.dialect.name == 'postgresql':
        _install_guard()


def downgrade():
    raise RuntimeError('Ledger posting-state migration cannot be downgraded: restoring mutable status would weaken immutable v2 audit evidence. A separately reviewed forward migration is required.')
