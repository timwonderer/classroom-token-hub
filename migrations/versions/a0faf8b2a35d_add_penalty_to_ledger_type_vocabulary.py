"""Add penalty to the closed Transaction.type vocabulary (DOM-LED-001 v2.19).

A teacher-applied fine is a Ledger penalty (owner ruling 2026-11-04, issue #1701;
SPEC-ECON-003 §4.5.1.1): a direct debit posted by FEAT-LED-006, never an
obligation. INV-LED-017 gains `penalty`, and this migration re-creates
`ck_ledger_transaction_type_closed_vocabulary` from the amended enumeration.

Upgrade only widens the vocabulary, so it changes no row. The constraint stays
NOT VALID, as a4d7e9c2f1b6 and e3b7c1d9a2f4 left it.

Downgrade narrows it again and so refuses to run while any `penalty` row exists:
a row the narrower vocabulary excludes must be dealt with deliberately, never
left behind a constraint that would reject it on its next UPDATE.

Revision ID: a0faf8b2a35d
Revises: a91c3d7e5f20
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0faf8b2a35d'
down_revision = 'a91c3d7e5f20'
branch_labels = None
depends_on = None

TABLE = 'ledger_transaction'
# The constraint's own name, created by a4d7e9c2f1b6; not an auto-generated one.
CHECK = 'ck_ledger_transaction_type_closed_vocabulary'
ADDED = 'penalty'

# DOM-LED-001 v2.18 INV-LED-017's canonical/legacy table, which this revision extends.
_PREVIOUS_ALLOWED_TYPES = (
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
    'issue_reversal',
    'issue_compensation',
    'rent_payment',
    'void_item_removed',
)
# DOM-LED-001 v2.19: the single authoritative enumeration.
_after = _PREVIOUS_ALLOWED_TYPES.index('manual_payment') + 1
_ALLOWED_TYPES = _PREVIOUS_ALLOWED_TYPES[:_after] + (ADDED,) + _PREVIOUS_ALLOWED_TYPES[_after:]


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def check_constraint_sql(table_name, constraint_name):
    """The constraint's current definition, or None when it does not exist."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for constraint in inspector.get_check_constraints(table_name):
            if constraint['name'] == constraint_name:
                return constraint['sqltext']
    except Exception:
        return None
    return None


def _check_sql(values):
    listed = ", ".join(f"'{v}'" for v in values)
    return f"type IS NULL OR type IN ({listed})"


def _replace_constraint(values):
    if check_constraint_sql(TABLE, CHECK) is not None:
        op.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT {CHECK}"))
    op.execute(sa.text(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {CHECK} CHECK ({_check_sql(values)}) NOT VALID"
    ))


def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  {TABLE} does not exist, skipping...")
        return
    current = check_constraint_sql(TABLE, CHECK)
    if current is not None and f"'{ADDED}'" in current:
        print(f"⚠️  {CHECK} already admits {ADDED}, skipping...")
        return
    _replace_constraint(_ALLOWED_TYPES)
    print(f"✅ Re-created {CHECK} (NOT VALID) admitting {ADDED}")


def downgrade():
    if not table_exists(TABLE):
        return
    current = check_constraint_sql(TABLE, CHECK)
    if current is not None and f"'{ADDED}'" not in current:
        print(f"⚠️  {CHECK} already excludes {ADDED}, skipping...")
        return

    remaining = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {TABLE} WHERE type = :added"), {"added": ADDED}
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"{remaining} {TABLE} row(s) carry type '{ADDED}'. Downgrading below "
            "DOM-LED-001 v2.19 removes it from the closed vocabulary; resolve those "
            "rows before this downgrade runs."
        )

    _replace_constraint(_PREVIOUS_ALLOWED_TYPES)
    print(f"❌ Re-created {CHECK} (NOT VALID) without {ADDED}")
