"""Drop the prohibited policy_version_id pointer from payroll_settings

`payroll_settings.policy_version_id` — with its index
`ix_payroll_settings_policy_version_id` and its FK
`fk_payroll_settings_policy_version_id` -> `policy_versions.id ON DELETE SET
NULL` — is an alternative version pointer on a Policies repository table.
DOM-POL-001 §VI.0 prohibits exactly that construct:

    Any schema element that attempts to create an alternative "current version"
    or "next version" pointer alongside `policy_uuid` — whether a
    self-referential FK on a Policies table or an external version-tracking
    table — is redundant and prohibited. `DOM-CLASS-003` (`policy_versions` /
    `policy_transitions`) records economic-policy evolution only and is not a
    domain-policy versioning mechanism.

History of the drift. The column arrived 2026-07-19 in
`c3d4e5f8a9b_align_prod_domain_schema_contract_v2` (and its predecessor
`b2c3d4e5f8a`), when payroll settings tracked lineage by pointing at
`policy_versions`. On 2026-09-04,
`3bb29ef4e874_payroll_hall_pass_settings_append_only` converted the table to the
append-only discipline in which `policy_uuid` IS the version, and dropped
`is_active` for precisely this reason — item 3 of that migration's own docstring
reads "Two current-policy projections on one table would be exactly the
alternative version pointer DOM-POL-001 §VI.0 prohibits." That conversion
removed one competing pointer and walked past the other. This migration finishes
the job.

The column was never mapped. `PayrollSettings` has never declared it, so no
route, service, FEAT, test, or template has ever read or written it, and the ORM
could not have populated it even by accident. All six existing rows hold NULL.

The two sibling Policies tables that went through the same 2026-09-04
conversion, `rent_settings` and `hall_pass_settings`, carry `policy_uuid` and no
version pointer. They are the correct end state; `payroll_settings` is the
outlier this brings back into line.

Deliberately untouched: `payroll_event.policy_version_id`. `PayrollEvent` is an
operational fact in the Productivity domain, not a Policies repository row.
Freezing lineage on a historical fact is the contract, not a violation — FEAT-
PROD-003 fails closed without it (`app/feats/prod.py` raises "FEAT-PROD-003
requires a payroll policy_version_id"). Only the Policies-side pointer is
prohibited.

The FK is discovered by column rather than by hardcoded name, so a database
whose constraint was created under a different naming convention still drops
cleanly. The downgrade restores column, index and FK as they were; since every
value is NULL there is nothing to restore beyond the shape.

Revision ID: b7d3e2064c15
Revises: a4f2b7c91d38
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d3e2064c15'
down_revision = 'a4f2b7c91d38'
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

    if not column_exists('payroll_settings', 'policy_version_id'):
        print(
            "Column 'policy_version_id' does not exist on 'payroll_settings', "
            "skipping..."
        )
        return

    # Discover the FK by column so a differently-named constraint still drops.
    for fk in get_foreign_keys_by_column('payroll_settings', 'policy_version_id'):
        if fk.get('name'):
            op.drop_constraint(fk['name'], 'payroll_settings', type_='foreignkey')
            print(f"Dropped foreign key {fk['name']} on payroll_settings")

    if index_exists('payroll_settings', 'ix_payroll_settings_policy_version_id'):
        op.drop_index(
            'ix_payroll_settings_policy_version_id',
            table_name='payroll_settings',
        )
        print("Dropped index ix_payroll_settings_policy_version_id")

    op.drop_column('payroll_settings', 'policy_version_id')
    print(
        "Dropped prohibited version pointer payroll_settings.policy_version_id "
        "(DOM-POL-001 §VI.0)"
    )


def downgrade():
    if not table_exists('payroll_settings'):
        print("payroll_settings does not exist, skipping...")
        return

    if not column_exists('payroll_settings', 'policy_version_id'):
        op.add_column(
            'payroll_settings',
            sa.Column('policy_version_id', sa.Integer(), nullable=True),
        )
        print("Restored payroll_settings.policy_version_id")
    else:
        print(
            "Column 'policy_version_id' already exists on 'payroll_settings', "
            "skipping..."
        )

    if not index_exists('payroll_settings', 'ix_payroll_settings_policy_version_id'):
        op.create_index(
            'ix_payroll_settings_policy_version_id',
            'payroll_settings',
            ['policy_version_id'],
            unique=False,
        )
        print("Restored index ix_payroll_settings_policy_version_id")

    if not foreign_key_exists(
        'payroll_settings', 'fk_payroll_settings_policy_version_id'
    ):
        op.create_foreign_key(
            'fk_payroll_settings_policy_version_id',
            'payroll_settings',
            'policy_versions',
            ['policy_version_id'],
            ['id'],
            ondelete='SET NULL',
        )
        print("Restored foreign key fk_payroll_settings_policy_version_id")
