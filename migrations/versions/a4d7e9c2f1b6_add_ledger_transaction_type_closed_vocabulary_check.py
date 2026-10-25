"""Add the closed Transaction.type vocabulary CHECK constraint (DOM-LED-001 INV-LED-017).

Enumerates the full canonical/legacy table from INV-LED-017 as the only lawful
`ledger_transaction.type` values (plus NULL, unchanged). Added NOT VALID so an
unexpected historical value cannot block this migration or take a long lock on
a live table; it still guards every new INSERT/UPDATE from the moment it is
added. Validating it against existing rows (`VALIDATE CONSTRAINT`) is a
deliberate separate step — see this migration's PR description.

This constraint alone does not require canonical spelling on new rows: every
existing writer that still emits a legacy-cased value (e.g. "REVERSAL",
"Interest", "Withdrawal", "Deposit") continues to pass it unchanged. The
write-time casing validator that rejects legacy spelling on new rows is a
separate, later PR (SPEC-ITR-001 §6.6, FEAT-LED-005 §IX) — enforcing it here
would require retiring every one of those writers plus every read-site
comparison that still expects the legacy spelling (NSF/reversal eligibility,
interest idempotency fingerprinting, insurance eligibility, historical
reconstruction) in the same change, which this migration deliberately does
not attempt.

Revision ID: a4d7e9c2f1b6
Revises: f6c8d0e2a4b5
Create Date: 2026-10-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d7e9c2f1b6'
down_revision = 'f6c8d0e2a4b5'
branch_labels = None
depends_on = None

TABLE = 'ledger_transaction'
CHECK = 'ck_ledger_transaction_type_closed_vocabulary'

# The single authoritative enumeration (DOM-LED-001 INV-LED-017's canonical/legacy
# table). A value this list omits is a gap in that contract to amend, not a value
# for this migration to infer or admit on its own.
_ALLOWED_TYPES = (
    'interest', 'Interest',
    'reversal', 'REVERSAL',
    'withdrawal', 'Withdrawal',
    'deposit', 'Deposit',
    'internal_transfer',
    'insurance_reimbursement',
    'insurance_premium',
    'purchase',
    'refund',
    'overdraft_fee',
    'payroll',
    'payroll_correction',
    'manual_payment',
    'bug_reward',
    'issue_reversal',
    'issue_compensation',
    'rent_payment',
    'void_item_removed',
)


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def check_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return constraint_name in {c['name'] for c in inspector.get_check_constraints(table_name)}
    except Exception:
        return False


def _check_sql():
    values = ", ".join(f"'{v}'" for v in _ALLOWED_TYPES)
    return f"type IS NULL OR type IN ({values})"


def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  {TABLE} does not exist, skipping...")
        return
    if check_constraint_exists(TABLE, CHECK):
        print(f"⚠️  {CHECK} already exists, skipping...")
        return
    op.execute(sa.text(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {CHECK} CHECK ({_check_sql()}) NOT VALID"
    ))
    print(f"✅ Added {CHECK} (NOT VALID) to {TABLE}")


def downgrade():
    if not table_exists(TABLE):
        return
    if check_constraint_exists(TABLE, CHECK):
        op.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT {CHECK}"))
        print(f"❌ Dropped {CHECK} from {TABLE}")
    else:
        print(f"⚠️  {CHECK} does not exist on {TABLE}, skipping...")
