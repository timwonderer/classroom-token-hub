"""Make payroll_settings the effective-dated sole payroll authority

Operator ruling 2026-09-30 (DOM-CLASS-003 §VII, DOM-POL-001 §VI.2,
DOM-POL-001A §V.F, DOM-PROD-001 §XI.3/§XV):

* ``payroll_settings`` is append-only with an ``effective_date``. Its legal
  columns are exactly policy_uuid, class_id, pay_rate, effective_date, created_at, overtime_threshold, overtime_threshold_unit,
  max_time_per_day, max_time_per_day_unit, pay_schedule_type, rounding_mode and
  first_pay_date. Every other column is dropped and ``policy_uuid`` becomes the
  primary key. Nothing references ``payroll_settings.id``: no foreign key
  targets the table (checked on production 2026-09-29) and no model or
  migration declares one.
* ``payroll_event.policy_version_id`` (a foreign key into the legacy
  ``policy_versions`` table, never an authority for payroll) is dropped, and
  ``payroll_event.policy_uuid`` is remapped from the PolicyVersion uuid it held
  to the ``payroll_settings.policy_uuid`` of the event's class.
* ``pay_schedule_type`` is limited to ``weekly``, ``biweekly`` and ``monthly``
  (owner ruling 2026-09-30: no daily or custom schedules; the cadence is the
  anchored recurrence of SPEC-TIME-001 §IX.12, so no day count is involved), and
  ``first_pay_date`` becomes NOT NULL (every setting anchors a schedule). The
  migration refuses a row with any other schedule type or no first pay date.
  ``payroll_frequency_days`` is dropped: pay frequency is always derived from
  ``pay_schedule_type`` through the anchored recurrence, never stored (operator
  ruling 2026-09-30; production's 7 rows are all ``biweekly`` / 14, so nothing
  is lost there).
* ``rounding_mode`` is RETIRED (operator ruling 2026-09-30): it was never defined
  or applied to pay. It is kept, as nullable historical data, rather than
  dropped; production's values (``up`` on 7 rows) stay. Nothing writes it.
* UPDATE is refused on both tables, and DELETE is refused except while a class
  universe is being destroyed (``cth.class_universe_destroying``, the flag
  ``ledger_transaction`` already honours).

Data mapping for existing ``payroll_settings`` rows:

* ``effective_date := created_at`` — each row was in force from its creation
  until the next row superseded it, which is exactly what "greatest
  effective_date <= t, latest created_at on a tie" answers. RETIRED rows keep
  their history on that same rule.
* A ``simple``-mode row enforced ``daily_limit_hours``, not
  ``max_time_per_day``; its limit is carried into ``max_time_per_day`` in hours
  so the enforced daily limit is unchanged.
* A row with overtime disabled keeps no overtime threshold, so a dormant
  threshold does not read as configured once ``overtime_enabled`` is gone.

Remap of ``payroll_event.policy_uuid`` (refuses, never guesses):

* every event carrying a ``policy_version_id`` must name a PolicyVersion of its
  own class, and that class must hold exactly one ``payroll_settings`` row;
* an event carrying a ``policy_uuid`` but no ``policy_version_id`` must already
  name a ``payroll_settings`` row of its own class;
* ``payroll_settings`` must have no NULL ``created_at`` and no two rows of one
  class sharing a ``created_at`` (the new ordering key).

Any violation raises before anything is changed. Production on 2026-09-29: 7
classes, one ``payroll_settings`` row and one payroll PolicyVersion each; 367
events, every one mapping by that 1:1 rule.

Downgrade restores the previous shape with best-effort values and is lossy:
``id`` is renumbered by ``created_at``; the row in force now becomes ``IN_USE``
and every other row, including any pending (future-effective) row, becomes
``RETIRED`` (a pending change is lost); ``next_payroll_date`` is re-derived
(last SYSTEM payroll occurrence + frequency in whole UTC days, else
``first_pay_date``, else ``created_at`` as the previous writer did); ``settings_mode`` becomes ``advanced``, ``time_unit``
``minutes``, ``overtime_multiplier`` 1.0, ``overtime_threshold_period`` ``day``
where a threshold exists, ``block``/``daily_limit_hours`` NULL, ``updated_at``
= ``created_at``, and a ``custom`` schedule's value/unit become the frequency in
days; ``payroll_frequency_days`` is recreated and backfilled with the old form's count for the schedule type (weekly 7, biweekly 14, monthly 30 — lossy for monthly). ``payroll_event.policy_version_id``/``policy_uuid`` are restored to the
class's payroll PolicyVersion active at the event's ``recorded_at`` (else the
class's earliest one); downgrade refuses if an event that needs one has none,
which is the case for any class first configured after this upgrade.

Revision ID: a7e3c9d1f5b2
Revises: bb5557cb1609
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'a7e3c9d1f5b2'
down_revision = 'bb5557cb1609'
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


def check_constraints_on(table_name):
    """Check constraints on a table, discovered rather than named (SOP-DB-001 Rule 7)."""
    conn = op.get_bind()
    return {
        name: definition
        for name, definition in conn.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = to_regclass(:t) AND contype = 'c'"
        ), {"t": table_name}).fetchall()
    }


def unique_constraint_on(table_name, columns):
    """Name of the unique constraint over exactly ``columns``, or None."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for uc in inspector.get_unique_constraints(table_name):
        if list(uc['column_names']) == list(columns):
            return uc['name']
    return None


def primary_key_on(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    pk = inspector.get_pk_constraint(table_name)
    return pk.get('name'), list(pk.get('constrained_columns') or [])


def function_exists(function_name):
    conn = op.get_bind()
    return conn.execute(
        text("SELECT 1 FROM pg_proc WHERE proname = :name"), {"name": function_name}
    ).scalar() is not None


def trigger_exists(trigger_name):
    conn = op.get_bind()
    return conn.execute(
        text("SELECT 1 FROM pg_trigger WHERE tgname = :name AND NOT tgisinternal"),
        {"name": trigger_name},
    ).scalar() is not None


# ============================================================================
# CONSTANTS
# ============================================================================

LEGAL_SETTINGS_COLUMNS = (
    'policy_uuid', 'class_id', 'pay_rate',
    'effective_date', 'created_at', 'overtime_threshold',
    'overtime_threshold_unit', 'max_time_per_day', 'max_time_per_day_unit',
    'pay_schedule_type', 'rounding_mode', 'first_pay_date',
)

# Class-universe destruction declares itself with this transaction-local flag
# (app/services/teacher_destruction.py); the ledger's immutability trigger
# already honours it.
TEARDOWN_SETTING = "cth.class_universe_destroying"

APPEND_ONLY_TABLES = {
    # table: (update fn, delete fn, update trigger, delete trigger, citation)
    "payroll_settings": (
        "prevent_payroll_settings_update", "prevent_payroll_settings_delete",
        "payroll_settings_no_update", "payroll_settings_no_delete",
        "payroll_settings is append-only (DOM-POL-001 §VI.2). A payroll change is a new row effective at the next payroll date.",
    ),
    "payroll_event": (
        "prevent_payroll_event_update", "prevent_payroll_event_delete",
        "payroll_event_no_update", "payroll_event_no_delete",
        "payroll_event is append-only (DOM-PROD-001 §XI.3). Correct a payroll outcome with a reversal through FEAT-PROD-003.",
    ),
}

PAYROLL_EVENT_CHECK = "ck_payroll_event_payroll_policy"
SETTINGS_ORDER_UNIQUE = "uq_payroll_settings_class_effective_created"
PAY_SCHEDULE_TYPES = ("weekly", "biweekly", "monthly")
SCHEDULE_TYPE_CHECK = "pay_schedule_type IN ('weekly','biweekly','monthly')"


class PayrollSettingsMigrationRefused(RuntimeError):
    """The data cannot be mapped without guessing; nothing was changed."""


# ============================================================================
# UPGRADE
# ============================================================================

def _preflight(conn):
    """Refuse, before any change, whenever the mapping would have to guess."""
    problems = []

    if column_exists('payroll_settings', 'created_at'):
        missing = conn.execute(text(
            "SELECT count(*) FROM payroll_settings WHERE created_at IS NULL"
        )).scalar()
        if missing:
            problems.append(f"{missing} payroll_settings row(s) have no created_at")
        dupes = conn.execute(text(
            "SELECT count(*) FROM (SELECT class_id, created_at FROM payroll_settings "
            "GROUP BY class_id, created_at HAVING count(*) > 1) d"
        )).scalar()
        if dupes:
            problems.append(f"{dupes} class/created_at pair(s) are shared by several payroll_settings rows")
    if column_exists('payroll_settings', 'pay_schedule_type'):
        unsupported = conn.execute(text(
            "SELECT count(*) FROM payroll_settings "
            "WHERE pay_schedule_type IS NULL OR pay_schedule_type NOT IN ('weekly','biweekly','monthly')"
        )).scalar()
        if unsupported:
            problems.append(
                f"{unsupported} payroll_settings row(s) have a pay schedule other than "
                "weekly, biweekly or monthly"
            )
    if column_exists('payroll_settings', 'first_pay_date'):
        unanchored = conn.execute(text(
            "SELECT count(*) FROM payroll_settings WHERE first_pay_date IS NULL"
        )).scalar()
        if unanchored:
            problems.append(f"{unanchored} payroll_settings row(s) have no first_pay_date")

    if column_exists('payroll_event', 'policy_version_id'):
        foreign = conn.execute(text("""
            SELECT count(*) FROM payroll_event e
            LEFT JOIN policy_versions pv ON pv.id = e.policy_version_id
            WHERE e.policy_version_id IS NOT NULL
              AND (pv.id IS NULL OR pv.class_id <> e.class_id)
        """)).scalar()
        if foreign:
            problems.append(f"{foreign} payroll_event row(s) name a policy version outside their class")
        ambiguous = conn.execute(text("""
            SELECT count(*) FROM payroll_event e
            WHERE e.policy_version_id IS NOT NULL
              AND (SELECT count(*) FROM payroll_settings ps WHERE ps.class_id = e.class_id) <> 1
        """)).scalar()
        if ambiguous:
            problems.append(
                f"{ambiguous} payroll_event row(s) belong to a class without exactly one "
                "payroll_settings row, so their setting cannot be identified"
            )
        unmapped = conn.execute(text("""
            SELECT count(*) FROM payroll_event e
            WHERE e.policy_version_id IS NULL AND e.policy_uuid IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM payroll_settings ps
                WHERE ps.class_id = e.class_id AND ps.policy_uuid = e.policy_uuid
              )
        """)).scalar()
        if unmapped:
            problems.append(
                f"{unmapped} payroll_event row(s) carry a policy_uuid with no policy version "
                "and no matching payroll_settings row"
            )

    if problems:
        raise PayrollSettingsMigrationRefused(
            "Refusing to migrate payroll_settings/payroll_event: " + "; ".join(problems)
            + ". Nothing was changed."
        )


def _remap_payroll_event(conn):
    if not column_exists('payroll_event', 'policy_version_id'):
        print("⚠️  payroll_event.policy_version_id already dropped, skipping remap...")
        return
    remapped = conn.execute(text("""
        UPDATE payroll_event e
        SET policy_uuid = ps.policy_uuid
        FROM payroll_settings ps
        WHERE e.policy_version_id IS NOT NULL
          AND ps.class_id = e.class_id
    """)).rowcount
    print(f"✅ Remapped policy_uuid on {remapped} payroll_event row(s) to payroll_settings")

    for name, definition in check_constraints_on('payroll_event').items():
        if 'policy_version_id' in definition:
            op.drop_constraint(name, 'payroll_event', type_='check')
            print(f"❌ Dropped check constraint {name}")
    for fk in get_foreign_keys_by_column('payroll_event', 'policy_version_id'):
        op.drop_constraint(fk['name'], 'payroll_event', type_='foreignkey')
        print(f"❌ Dropped foreign key {fk['name']}")
    if index_exists('payroll_event', 'ix_payroll_event_policy_version_id'):
        op.drop_index('ix_payroll_event_policy_version_id', table_name='payroll_event')
    op.drop_column('payroll_event', 'policy_version_id')
    print("❌ Dropped payroll_event.policy_version_id")


def _ensure_payroll_event_check(conn):
    wanted = "payroll_event_type <> 'payroll' OR policy_uuid IS NOT NULL"
    present = check_constraints_on('payroll_event')
    if any(
        'policy_uuid' in definition and 'policy_version_id' not in definition
        for definition in present.values()
    ):
        print("⚠️  payroll_event policy check already present, skipping...")
        return
    op.create_check_constraint(PAYROLL_EVENT_CHECK, 'payroll_event', wanted)
    print(f"✅ Created check constraint {PAYROLL_EVENT_CHECK}")


def _reshape_payroll_settings(conn):
    if not column_exists('payroll_settings', 'effective_date'):
        op.add_column('payroll_settings', sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added payroll_settings.effective_date")
    conn.execute(text(
        "UPDATE payroll_settings SET effective_date = created_at WHERE effective_date IS NULL"
    ))

    # A simple-mode row enforced daily_limit_hours; carry it into the legal
    # column so the enforced limit is unchanged once settings_mode is gone.
    if column_exists('payroll_settings', 'settings_mode') and column_exists('payroll_settings', 'daily_limit_hours'):
        carried = conn.execute(text("""
            UPDATE payroll_settings
            SET max_time_per_day = daily_limit_hours,
                max_time_per_day_unit = CASE WHEN daily_limit_hours IS NULL THEN NULL ELSE 'hours' END
            WHERE settings_mode = 'simple'
        """)).rowcount
        print(f"✅ Carried the daily limit of {carried} simple-mode row(s) into max_time_per_day")
    if column_exists('payroll_settings', 'overtime_enabled'):
        conn.execute(text("""
            UPDATE payroll_settings
            SET overtime_threshold = NULL, overtime_threshold_unit = NULL
            WHERE overtime_enabled IS NOT TRUE
        """))

    op.alter_column('payroll_settings', 'effective_date', existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column('payroll_settings', 'created_at', existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column('payroll_settings', 'first_pay_date', existing_type=sa.DateTime(timezone=True), nullable=False)
    # rounding_mode is RETIRED (operator ruling 2026-09-30): kept as historical
    # data rather than dropped, but no longer required or written.
    op.alter_column('payroll_settings', 'rounding_mode', existing_type=sa.String(20), nullable=True)

    # Indexes and constraints over columns that are going away.
    for index_name in (
        'uq_payroll_settings_active_scope',
        'ix_payroll_settings_class_availability',
        'ix_payroll_settings_policy_uuid',
    ):
        if index_exists('payroll_settings', index_name):
            op.drop_index(index_name, table_name='payroll_settings')
            print(f"❌ Dropped index {index_name}")
    for name, definition in check_constraints_on('payroll_settings').items():
        if 'availability_state' in definition:
            op.drop_constraint(name, 'payroll_settings', type_='check')
            print(f"❌ Dropped check constraint {name}")

    pk_name, pk_columns = primary_key_on('payroll_settings')
    if pk_columns != ['policy_uuid']:
        if pk_name:
            op.drop_constraint(pk_name, 'payroll_settings', type_='primary')
            print(f"❌ Dropped primary key {pk_name} on {pk_columns}")
        op.create_primary_key('payroll_settings_pkey', 'payroll_settings', ['policy_uuid'])
        print("✅ policy_uuid is now the payroll_settings primary key")

    inspector = sa.inspect(conn)
    for column in [c['name'] for c in inspector.get_columns('payroll_settings')]:
        if column not in LEGAL_SETTINGS_COLUMNS:
            op.drop_column('payroll_settings', column)
            print(f"❌ Dropped payroll_settings.{column}")

    if unique_constraint_on('payroll_settings', ['class_id', 'effective_date', 'created_at']) is None:
        op.create_unique_constraint(
            SETTINGS_ORDER_UNIQUE, 'payroll_settings', ['class_id', 'effective_date', 'created_at']
        )
        print(f"✅ Created {SETTINGS_ORDER_UNIQUE}")
    checks = check_constraints_on('payroll_settings')
    if not any("'biweekly'" in d for d in checks.values()):
        op.create_check_constraint('ck_payroll_settings_schedule_type', 'payroll_settings', SCHEDULE_TYPE_CHECK)
        print("✅ Created ck_payroll_settings_schedule_type")
    if not any('effective_date >= created_at' in d for d in checks.values()):
        op.create_check_constraint(
            'ck_payroll_settings_not_retroactive', 'payroll_settings', 'effective_date >= created_at'
        )


def _install_append_only_triggers(conn):
    for table, (update_fn, delete_fn, update_trg, delete_trg, message) in APPEND_ONLY_TABLES.items():
        if not function_exists(update_fn):
            conn.execute(text(f"""
                CREATE FUNCTION {update_fn}()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION '{message}';
                END;
                $$ LANGUAGE plpgsql;
            """))
            print(f"✅ Created {update_fn}()")
        if not function_exists(delete_fn):
            conn.execute(text(f"""
                CREATE FUNCTION {delete_fn}()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF coalesce(current_setting('{TEARDOWN_SETTING}', true), 'off') <> 'on' THEN
                        RAISE EXCEPTION '{message} Rows are removed only when the class universe is destroyed.';
                    END IF;
                    RETURN OLD;
                END;
                $$ LANGUAGE plpgsql;
            """))
            print(f"✅ Created {delete_fn}()")
        if not trigger_exists(update_trg):
            conn.execute(text(
                f"CREATE TRIGGER {update_trg} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {update_fn}();"
            ))
            print(f"✅ Created trigger {update_trg}")
        if not trigger_exists(delete_trg):
            conn.execute(text(
                f"CREATE TRIGGER {delete_trg} BEFORE DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {delete_fn}();"
            ))
            print(f"✅ Created trigger {delete_trg}")


def upgrade():
    if not table_exists('payroll_settings') or not table_exists('payroll_event'):
        print("⚠️  payroll_settings/payroll_event missing, skipping...")
        return
    conn = op.get_bind()
    _preflight(conn)
    _remap_payroll_event(conn)
    _ensure_payroll_event_check(conn)
    _reshape_payroll_settings(conn)
    _install_append_only_triggers(conn)


# ============================================================================
# DOWNGRADE (best effort, lossy — see module docstring)
# ============================================================================

def _drop_append_only_triggers(conn):
    for table, (update_fn, delete_fn, update_trg, delete_trg, _message) in APPEND_ONLY_TABLES.items():
        for trigger in (update_trg, delete_trg):
            if trigger_exists(trigger):
                conn.execute(text(f"DROP TRIGGER {trigger} ON {table};"))
                print(f"❌ Dropped trigger {trigger}")
        for function in (update_fn, delete_fn):
            if function_exists(function):
                conn.execute(text(f"DROP FUNCTION {function}();"))
                print(f"❌ Dropped {function}()")


def _restore_payroll_event(conn):
    if column_exists('payroll_event', 'policy_version_id'):
        print("⚠️  payroll_event.policy_version_id already present, skipping...")
        return
    op.add_column('payroll_event', sa.Column('policy_version_id', sa.Integer(), nullable=True))
    conn.execute(text("""
        UPDATE payroll_event e
        SET policy_version_id = pv.id, policy_uuid = pv.policy_uuid
        FROM policy_versions pv
        WHERE e.policy_uuid IS NOT NULL
          AND pv.id = COALESCE(
            (SELECT p.id FROM policy_versions p
             WHERE p.class_id = e.class_id AND p.domain = 'payroll'
               AND p.activated_at IS NOT NULL AND p.activated_at <= e.recorded_at
             ORDER BY p.activated_at DESC, p.id DESC LIMIT 1),
            (SELECT p.id FROM policy_versions p
             WHERE p.class_id = e.class_id AND p.domain = 'payroll'
             ORDER BY p.version_number ASC, p.id ASC LIMIT 1)
          )
    """))
    unmapped = conn.execute(text(
        "SELECT count(*) FROM payroll_event WHERE policy_uuid IS NOT NULL AND policy_version_id IS NULL"
    )).scalar()
    if unmapped:
        raise PayrollSettingsMigrationRefused(
            f"Refusing to downgrade: {unmapped} payroll_event row(s) belong to a class with no "
            "payroll policy version to restore. The previous schema requires one."
        )
    for name, definition in check_constraints_on('payroll_event').items():
        if 'policy_uuid' in definition:
            op.drop_constraint(name, 'payroll_event', type_='check')
    op.create_check_constraint(
        PAYROLL_EVENT_CHECK, 'payroll_event',
        "payroll_event_type <> 'payroll' OR (policy_version_id IS NOT NULL AND policy_uuid IS NOT NULL)",
    )
    if not foreign_key_exists('payroll_event', 'fk_payroll_event_policy_version_id'):
        op.create_foreign_key(
            'fk_payroll_event_policy_version_id', 'payroll_event', 'policy_versions',
            ['policy_version_id'], ['id'], ondelete='RESTRICT',
        )
    if not index_exists('payroll_event', 'ix_payroll_event_policy_version_id'):
        op.create_index('ix_payroll_event_policy_version_id', 'payroll_event', ['policy_version_id'])


def _restore_payroll_settings(conn):
    if column_exists('payroll_settings', 'id'):
        print("⚠️  payroll_settings.id already present, skipping...")
        return
    restored = [
        sa.Column('availability_state', sa.String(16), nullable=False, server_default='RETIRED'),
        sa.Column('block', sa.String(10), nullable=True),
        sa.Column('next_payroll_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('overtime_multiplier', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('settings_mode', sa.String(20), nullable=False, server_default='advanced'),
        sa.Column('daily_limit_hours', sa.Float(), nullable=True),
        sa.Column('time_unit', sa.String(20), nullable=False, server_default='minutes'),
        sa.Column('overtime_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('overtime_threshold_period', sa.String(20), nullable=True),
        sa.Column('pay_schedule_custom_value', sa.Integer(), nullable=True),
        sa.Column('pay_schedule_custom_unit', sa.String(20), nullable=True),
    ]
    for column in restored:
        if not column_exists('payroll_settings', column.name):
            op.add_column('payroll_settings', column)

    # The previous schema stores a day count per row and requires one. The
    # downgrade backfills the count the old settings form wrote for each schedule
    # type (lossy for monthly: the old code treated it as 30 days); nothing else
    # ever writes it.
    if not column_exists('payroll_settings', 'payroll_frequency_days'):
        op.add_column('payroll_settings', sa.Column('payroll_frequency_days', sa.Integer(), nullable=True))
    conn.execute(text("""
        UPDATE payroll_settings SET payroll_frequency_days = CASE pay_schedule_type
            WHEN 'weekly' THEN 7 WHEN 'biweekly' THEN 14 WHEN 'monthly' THEN 30 END
        WHERE payroll_frequency_days IS NULL
    """))
    op.alter_column('payroll_settings', 'payroll_frequency_days', existing_type=sa.Integer(), nullable=False)
    op.alter_column('payroll_settings', 'first_pay_date', existing_type=sa.DateTime(timezone=True), nullable=True)
    # The previous schema requires rounding_mode; rows written after the upgrade
    # have none, and 'down' was the old default (it was never applied either way).
    conn.execute(text("UPDATE payroll_settings SET rounding_mode = 'down' WHERE rounding_mode IS NULL"))
    op.alter_column('payroll_settings', 'rounding_mode', existing_type=sa.String(20), nullable=False)

    conn.execute(text("""
        UPDATE payroll_settings SET
            updated_at = created_at,
            overtime_enabled = (overtime_threshold IS NOT NULL),
            overtime_threshold_period = CASE WHEN overtime_threshold IS NOT NULL THEN 'day' END,
            pay_schedule_custom_value = CASE WHEN pay_schedule_type = 'custom' THEN payroll_frequency_days END,
            pay_schedule_custom_unit = CASE WHEN pay_schedule_type = 'custom' THEN 'days' END
    """))
    # The row in force now is the single IN_USE row; every other row, including
    # a pending one, is RETIRED (lossy: a pending change is dropped).
    conn.execute(text("""
        UPDATE payroll_settings ps SET availability_state = 'IN_USE'
        FROM (
            SELECT DISTINCT ON (class_id) policy_uuid
            FROM payroll_settings
            WHERE effective_date <= now()
            ORDER BY class_id, effective_date DESC, created_at DESC
        ) cur
        WHERE ps.policy_uuid = cur.policy_uuid
    """))
    conn.execute(text("""
        UPDATE payroll_settings ps SET next_payroll_date = COALESCE(
            (SELECT COALESCE((e.summary_json ->> 'scheduled_occurrence')::timestamptz, e.recorded_at)
             FROM payroll_event e
             WHERE e.class_id = ps.class_id AND e.payroll_event_type = 'payroll'
               AND e.mechanism = 'SYSTEM'
             ORDER BY e.recorded_at DESC, e.id DESC LIMIT 1)
              + make_interval(days => ps.payroll_frequency_days),
            ps.first_pay_date,
            ps.created_at
        )
        WHERE ps.availability_state = 'IN_USE'
    """))

    for name in (
        unique_constraint_on('payroll_settings', ['class_id', 'effective_date', 'created_at']),
    ):
        if name:
            op.drop_constraint(name, 'payroll_settings', type_='unique')
    for name, definition in check_constraints_on('payroll_settings').items():
        if 'effective_date' in definition or "'biweekly'" in definition:
            op.drop_constraint(name, 'payroll_settings', type_='check')
    op.drop_column('payroll_settings', 'effective_date')
    op.alter_column('payroll_settings', 'created_at', existing_type=sa.DateTime(timezone=True), nullable=True)

    pk_name, _pk_columns = primary_key_on('payroll_settings')
    if pk_name:
        op.drop_constraint(pk_name, 'payroll_settings', type_='primary')
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS payroll_settings_id_seq"))
    if not column_exists('payroll_settings', 'id'):
        op.add_column('payroll_settings', sa.Column('id', sa.Integer(), nullable=True))
    conn.execute(text("""
        UPDATE payroll_settings ps SET id = ordered.n
        FROM (
            SELECT policy_uuid, row_number() OVER (ORDER BY created_at, policy_uuid) AS n
            FROM payroll_settings
        ) ordered
        WHERE ps.policy_uuid = ordered.policy_uuid
    """))
    conn.execute(text(
        "SELECT setval('payroll_settings_id_seq', COALESCE((SELECT max(id) FROM payroll_settings), 0) + 1, false)"
    ))
    conn.execute(text("ALTER TABLE payroll_settings ALTER COLUMN id SET DEFAULT nextval('payroll_settings_id_seq')"))
    conn.execute(text("ALTER SEQUENCE payroll_settings_id_seq OWNED BY payroll_settings.id"))
    op.alter_column('payroll_settings', 'id', existing_type=sa.Integer(), nullable=False)
    op.create_primary_key('payroll_settings_pkey', 'payroll_settings', ['id'])

    op.alter_column('payroll_settings', 'availability_state', server_default='IN_USE')
    for name in ('overtime_multiplier', 'settings_mode', 'time_unit', 'overtime_enabled'):
        op.alter_column('payroll_settings', name, server_default=None)
    op.create_check_constraint(
        'ck_payroll_settings_availability', 'payroll_settings',
        "availability_state IN ('IN_USE','HIDDEN','RETIRED')",
    )
    if not index_exists('payroll_settings', 'ix_payroll_settings_policy_uuid'):
        op.create_index('ix_payroll_settings_policy_uuid', 'payroll_settings', ['policy_uuid'], unique=True)
    if not index_exists('payroll_settings', 'ix_payroll_settings_class_availability'):
        op.create_index(
            'ix_payroll_settings_class_availability', 'payroll_settings', ['class_id', 'availability_state']
        )
    if not index_exists('payroll_settings', 'uq_payroll_settings_active_scope'):
        op.create_index(
            'uq_payroll_settings_active_scope', 'payroll_settings', ['class_id'], unique=True,
            postgresql_where=sa.text("availability_state = 'IN_USE'"),
        )


def downgrade():
    if not table_exists('payroll_settings') or not table_exists('payroll_event'):
        print("⚠️  payroll_settings/payroll_event missing, skipping...")
        return
    conn = op.get_bind()
    _drop_append_only_triggers(conn)
    _restore_payroll_event(conn)
    _restore_payroll_settings(conn)
