"""Retire policy_versions and policy_transitions

Operator ruling 2026-09-30: ``policy_versions`` and ``policy_transitions`` were
never authorized as canonical tables. The owner removed them from the Policies
domain on 2026-08-03 (``184910af8``, PR #1293); they were recreated in
DOM-CLASS-003 on 2026-08-08 (``abb49d75e``, PR #1321) and given a carve-out in
DOM-POL-001 §VI.0 on 2026-08-15 (``e6f10734e``). Each domain's own append-only,
effective-dated table is its policy history (DOM-POL-001 §VI.0, DOM-CLASS-003
§V): ``payroll_settings``, ``rent_settings``, ``insurance_policies``,
``store_products``, ``economic_engine``. Bill cycles and assessments freeze the
owning row's ``policy_uuid`` (DOM-OBL-001).

This revision:

* drops ``assessment_events.policy_version_id`` with its foreign key and index;
* drops ``assessment_events.rent_policy_version_id`` and its index — the
  pointer into the rent policy-version table ``7c3d4e5f6a7b`` dropped. The ORM
  has not declared it since ``a1b2c3d4e5f6``, which renames it only where
  ``policy_version_id`` is absent. It is present, all NULL, on production and on
  any chain started from the frozen baseline (which carries both columns);
* drops ``policy_transitions`` and ``policy_versions``.

It refuses, changing nothing, if any row would carry meaning the owning tables do
not already hold. It never guesses a mapping:

* any ``policy_versions`` row whose domain is not ``payroll`` (payroll rows are
  mirrors of ``payroll_settings``, which ``a7e3c9d1f5b2`` made the sole payroll
  authority and stopped reading them);
* any ``policy_transitions`` row;
* any ``assessment_events`` row with a non-NULL ``policy_version_id`` or
  ``rent_policy_version_id``;
* any foreign key into either table from a table other than the two themselves
  and ``assessment_events`` (``a7e3c9d1f5b2`` already removed
  ``payroll_event.policy_version_id``).

Production on 2026-09-30: 7 ``policy_versions`` rows, all ``payroll``; 0
``policy_transitions`` rows; 144 ``assessment_events`` rows, none with a
``policy_version_id`` or a ``rent_policy_version_id``.

Downgrade recreates both tables and the column **empty**. The dropped rows are
not restored: they held only the 7 payroll mirror rows, which nothing reads.
Because ``a7e3c9d1f5b2``'s own downgrade maps each payroll event back to a
payroll ``policy_versions`` row, downgrading past it after this revision refuses
on any database that holds payroll events; that is the same refusal it already
gives for a class first configured after it.

Revision ID: dd52b19d48d8
Revises: a7e3c9d1f5b2
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'dd52b19d48d8'
down_revision = 'a7e3c9d1f5b2'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED — SOP-DB-001)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx['name'] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return fk_name in [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
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


def foreign_keys_into(referred_tables):
    """Every foreign key whose target is one of ``referred_tables``, discovered."""
    conn = op.get_bind()
    return conn.execute(text("""
        SELECT conrelid::regclass::text AS source_table,
               conname,
               confrelid::regclass::text AS referred_table
        FROM pg_constraint
        WHERE contype = 'f'
          AND confrelid::regclass::text = ANY(:tables)
        ORDER BY 1, 2
    """), {"tables": list(referred_tables)}).fetchall()


# ============================================================================
# CONSTANTS
# ============================================================================

RETIRED_TABLES = ('policy_versions', 'policy_transitions')
# Tables allowed to reference the retired pair: the pair itself (it references
# its own rows) and assessment_events, whose column this revision drops.
EXPECTED_REFERRERS = {'policy_versions', 'policy_transitions', 'assessment_events'}
# The only domain whose policy_versions rows may be dropped: payroll rows mirror
# payroll_settings, the sole payroll authority since a7e3c9d1f5b2.
DROPPABLE_DOMAIN = 'payroll'
ASSESSMENT_INDEX = 'ix_assessment_events_policy_version_id'
# (column, index) pairs on assessment_events that pointed at a retired
# policy-version table.
ASSESSMENT_COLUMNS = (
    ('policy_version_id', ASSESSMENT_INDEX),
    ('rent_policy_version_id', 'ix_assessment_events_rent_policy_version_id'),
)


class PolicyLineageRetirementRefused(RuntimeError):
    """A retired row still carries meaning; nothing was changed."""


# ============================================================================
# UPGRADE
# ============================================================================

def _preflight(conn):
    """Refuse, before any change, whenever dropping would lose meaning."""
    problems = []

    if table_exists('policy_versions'):
        foreign_domains = conn.execute(text(
            "SELECT domain, count(*) FROM policy_versions WHERE domain <> :payroll "
            "GROUP BY domain ORDER BY domain"
        ), {"payroll": DROPPABLE_DOMAIN}).fetchall()
        for domain, count in foreign_domains:
            problems.append(f"{count} policy_versions row(s) in domain {domain!r}")

    if table_exists('policy_transitions'):
        transitions = conn.execute(text("SELECT count(*) FROM policy_transitions")).scalar()
        if transitions:
            problems.append(f"{transitions} policy_transitions row(s)")

    for column, _index in ASSESSMENT_COLUMNS:
        if column_exists('assessment_events', column):
            referenced = conn.execute(text(
                f"SELECT count(*) FROM assessment_events WHERE {column} IS NOT NULL"
            )).scalar()
            if referenced:
                problems.append(f"{referenced} assessment_events row(s) with a {column}")

    present = [name for name in RETIRED_TABLES if table_exists(name)]
    if present:
        for source_table, conname, referred in foreign_keys_into(present):
            if source_table not in EXPECTED_REFERRERS:
                problems.append(f"foreign key {conname} on {source_table} references {referred}")

    if problems:
        raise PolicyLineageRetirementRefused(
            "Refusing to retire policy_versions/policy_transitions: " + "; ".join(problems)
            + ". No mapping to the owning tables is guessed. Nothing was changed."
        )


def _drop_assessment_columns():
    for column, index in ASSESSMENT_COLUMNS:
        if not column_exists('assessment_events', column):
            print(f"⚠️  assessment_events.{column} already dropped, skipping...")
            continue
        for fk in get_foreign_keys_by_column('assessment_events', column):
            op.drop_constraint(fk['name'], 'assessment_events', type_='foreignkey')
            print(f"❌ Dropped foreign key {fk['name']}")
        if index_exists('assessment_events', index):
            op.drop_index(index, table_name='assessment_events')
            print(f"❌ Dropped index {index}")
        op.drop_column('assessment_events', column)
        print(f"❌ Dropped assessment_events.{column}")


def _drop_retired_tables(conn):
    present = [name for name in RETIRED_TABLES if table_exists(name)]
    if not present:
        print("⚠️  policy_versions/policy_transitions already dropped, skipping...")
        return
    # The two tables reference each other; drop those constraints first so each
    # table drops on its own, with no CASCADE reaching anything else.
    for source_table, conname, _referred in foreign_keys_into(present):
        if source_table in present:
            op.drop_constraint(conname, source_table, type_='foreignkey')
            print(f"❌ Dropped foreign key {conname}")
    for name in ('policy_transitions', 'policy_versions'):
        if table_exists(name):
            rows = conn.execute(text(f"SELECT count(*) FROM {name}")).scalar()
            op.drop_table(name)
            print(f"❌ Dropped {name} ({rows} row(s))")


def upgrade():
    conn = op.get_bind()
    _preflight(conn)
    _drop_assessment_columns()
    _drop_retired_tables(conn)


# ============================================================================
# DOWNGRADE — recreates the empty shape; no row is restored
# ============================================================================

def _create_policy_versions():
    if table_exists('policy_versions'):
        print("⚠️  policy_versions already exists, skipping...")
        return
    op.create_table(
        'policy_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_uuid', sa.String(36), nullable=False),
        sa.Column('class_id', sa.String(36), nullable=False),
        sa.Column('domain', sa.String(32), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('policy_payload_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_transition_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('class_id', 'domain', 'version_number', name='uq_policy_versions_class_domain_version'),
    )
    print("✅ Recreated empty policy_versions")


def _create_policy_transitions():
    if table_exists('policy_transitions'):
        print("⚠️  policy_transitions already exists, skipping...")
        return
    op.create_table(
        'policy_transitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_id', sa.String(36), nullable=False),
        sa.Column('domain', sa.String(32), nullable=False),
        sa.Column('source_policy_version_id', sa.Integer(), nullable=True),
        sa.Column('target_policy_version_id', sa.Integer(), nullable=False),
        sa.Column('activation_mode', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_seat_id', sa.Integer(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('correlation_id', sa.String(64), nullable=True),
        sa.Column('superseded_by_transition_id', sa.Integer(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_seat_id'], ['seats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_policy_version_id'], ['policy_versions.id']),
        sa.ForeignKeyConstraint(['target_policy_version_id'], ['policy_versions.id']),
        sa.ForeignKeyConstraint(['superseded_by_transition_id'], ['policy_transitions.id']),
    )
    print("✅ Recreated empty policy_transitions")


INDEXES = (
    ('policy_versions', 'ix_policy_versions_policy_uuid', ['policy_uuid'], True),
    ('policy_versions', 'ix_policy_versions_class_id', ['class_id'], False),
    ('policy_versions', 'ix_policy_versions_class_domain_active', ['class_id', 'domain', 'is_active'], False),
    ('policy_transitions', 'ix_policy_transitions_class_id', ['class_id'], False),
    ('policy_transitions', 'ix_policy_transitions_correlation_id', ['correlation_id'], False),
    ('policy_transitions', 'ix_policy_transitions_class_domain_status', ['class_id', 'domain', 'status'], False),
)


def _created_by_transition_fks():
    return [
        fk for fk in get_foreign_keys_by_column('policy_versions', 'created_by_transition_id')
        if fk['referred_table'] == 'policy_transitions'
    ]


def downgrade():
    print("⚠️  Recreating policy_versions/policy_transitions EMPTY: their rows are not restored.")
    _create_policy_versions()
    _create_policy_transitions()
    if not foreign_key_exists('policy_versions', 'policy_versions_created_by_transition_id_fkey') \
            and not _created_by_transition_fks():
        op.create_foreign_key(
            'policy_versions_created_by_transition_id_fkey', 'policy_versions', 'policy_transitions',
            ['created_by_transition_id'], ['id'],
        )
    for table, name, columns, unique in INDEXES:
        if not index_exists(table, name):
            op.create_index(name, table, columns, unique=unique)

    if not column_exists('assessment_events', 'policy_version_id'):
        op.add_column('assessment_events', sa.Column('policy_version_id', sa.Integer(), nullable=True))
        print("✅ Recreated assessment_events.policy_version_id (all NULL)")
    if not foreign_key_exists('assessment_events', 'assessment_events_policy_version_id_fkey') \
            and not get_foreign_keys_by_column('assessment_events', 'policy_version_id'):
        op.create_foreign_key(
            'assessment_events_policy_version_id_fkey', 'assessment_events', 'policy_versions',
            ['policy_version_id'], ['id'],
        )
    if not index_exists('assessment_events', ASSESSMENT_INDEX):
        op.create_index(ASSESSMENT_INDEX, 'assessment_events', ['policy_version_id'])

    # The orphan pointer comes back as it was on a baseline-started chain:
    # nullable, indexed, no foreign key (its target table is long gone).
    if not column_exists('assessment_events', 'rent_policy_version_id'):
        op.add_column('assessment_events', sa.Column('rent_policy_version_id', sa.Integer(), nullable=True))
        print("✅ Recreated assessment_events.rent_policy_version_id (all NULL)")
    if not index_exists('assessment_events', 'ix_assessment_events_rent_policy_version_id'):
        op.create_index('ix_assessment_events_rent_policy_version_id', 'assessment_events', ['rent_policy_version_id'])
