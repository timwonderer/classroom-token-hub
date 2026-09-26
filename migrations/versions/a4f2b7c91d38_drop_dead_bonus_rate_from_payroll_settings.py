"""Drop the dead bonus_rate column from payroll_settings

`bonus_rate` was a v1 artifact that never became a feature. It carried a form
field labelled "Bonus Rate ($ per minute)" on `PayrollSettingsForm`, a Float
column on `PayrollSettings`, and membership in `_FROZEN_POLICY_FIELDS` — and
nothing else. No template rendered it, no route or service read it, no FEAT
consumed it, no test asserted it, and no normative document under
`docs/INVARIANT/`, `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/SPEC/` or
`docs/STANDARD_OPERATING_PROCEDURES/` has ever required it. A teacher could
type a number into it and the number went nowhere.

That is worse than a missing feature. `payroll_settings` is an append-only
versioned policy table (DOM-POL-001 §VI.1), so every row is a contract the
teacher is told they submitted. A frozen field that silently means nothing puts
a fictional term inside an immutable contract.

Dropping a column from an immutable-policy table destroys what historical rows
asserted, so this was checked against real data before being written: every
existing row holds 0.0, the column default. No policy version loses a term it
actually carried.

`bonus_rate` also leaves `PayrollSettings._FROZEN_POLICY_FIELDS`, which is the
sole source of `_SUBMITTABLE_FIELDS` in `payroll_settings_service`. A caller
passing `bonus_rate` to `upsert_payroll_settings` now raises rather than
writing a column that no longer exists — the enumeration fails loud by design.

The downgrade restores the column as a nullable Float defaulting to 0.0, which
reproduces the prior schema exactly. It cannot restore per-row values, and does
not need to: there were none.

Revision ID: a4f2b7c91d38
Revises: c5e8f1a2b3d4
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4f2b7c91d38'
down_revision = 'c5e8f1a2b3d4'
branch_labels = None
depends_on = None


# --------------------------------------------------------------------------
# Idempotency helpers (see migrations/migration_template.py.mako)
# --------------------------------------------------------------------------

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


def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# --------------------------------------------------------------------------


def upgrade():
    if not table_exists('payroll_settings'):
        print("payroll_settings does not exist, skipping...")
        return

    if column_exists('payroll_settings', 'bonus_rate'):
        op.drop_column('payroll_settings', 'bonus_rate')
        print("Dropped dead column payroll_settings.bonus_rate")
    else:
        print("Column 'bonus_rate' does not exist on 'payroll_settings', skipping...")


def downgrade():
    if not table_exists('payroll_settings'):
        print("payroll_settings does not exist, skipping...")
        return

    if not column_exists('payroll_settings', 'bonus_rate'):
        op.add_column(
            'payroll_settings',
            # No server_default: the original column (i6j7k8l9m0n1) had none, and a
            # downgrade that restores a different column than it removed is not a
            # rollback.
            sa.Column('bonus_rate', sa.Float(), nullable=True),
        )
        print("Restored payroll_settings.bonus_rate")
    else:
        print("Column 'bonus_rate' already exists on 'payroll_settings', skipping...")
