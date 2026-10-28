"""Remove bug_reward from the closed Transaction.type vocabulary (DOM-LED-001 v2.18).

The sysadmin bug reward is retired until badges are formally implemented (owner
ruling 2026-10-27; DOM-SUP-001 v1.10). Nothing writes `bug_reward` any more and
no row has ever carried it, so INV-LED-017 drops it and this migration re-creates
`ck_ledger_transaction_type_closed_vocabulary` from the amended enumeration.

Pre-check: the constraint is NOT VALID (as migration a4d7e9c2f1b6 added it), so
existing rows are not scanned when it is re-created. Upgrade therefore counts
`bug_reward` rows itself and refuses to run while any exist: a row the new
vocabulary excludes must be dealt with deliberately, never left behind a
constraint that would reject it on its next UPDATE.

Downgrade re-creates the constraint with `bug_reward` admitted. It only widens
the vocabulary, so it is exact: no row changes and nothing is lost.

Revision ID: e3b7c1d9a2f4
Revises: c8f1a2b3d490
Create Date: 2026-10-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3b7c1d9a2f4'
down_revision = 'c8f1a2b3d490'
branch_labels = None
depends_on = None

TABLE = 'ledger_transaction'
# The constraint's own name, created by a4d7e9c2f1b6; not an auto-generated one.
CHECK = 'ck_ledger_transaction_type_closed_vocabulary'
RETIRED = 'bug_reward'

# DOM-LED-001 v2.18 INV-LED-017's canonical/legacy table, the single
# authoritative enumeration.
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
    'issue_reversal',
    'issue_compensation',
    'rent_payment',
    'void_item_removed',
)
# The DOM-LED-001 v2.17 enumeration this revision replaces.
_after = _ALLOWED_TYPES.index('manual_payment') + 1
_PREVIOUS_ALLOWED_TYPES = _ALLOWED_TYPES[:_after] + (RETIRED,) + _ALLOWED_TYPES[_after:]


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
    if current is not None and f"'{RETIRED}'" not in current:
        print(f"⚠️  {CHECK} already excludes {RETIRED}, skipping...")
        return

    remaining = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {TABLE} WHERE type = :retired"), {"retired": RETIRED}
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"{remaining} {TABLE} row(s) carry type '{RETIRED}'. DOM-LED-001 v2.18 removes it "
            "from the closed vocabulary; resolve those rows before this migration runs."
        )

    _replace_constraint(_ALLOWED_TYPES)
    print(f"✅ Re-created {CHECK} (NOT VALID) without {RETIRED}")


def downgrade():
    if not table_exists(TABLE):
        return
    current = check_constraint_sql(TABLE, CHECK)
    if current is not None and f"'{RETIRED}'" in current:
        print(f"⚠️  {CHECK} already admits {RETIRED}, skipping...")
        return
    _replace_constraint(_PREVIOUS_ALLOWED_TYPES)
    print(f"❌ Re-created {CHECK} (NOT VALID) admitting {RETIRED}")
