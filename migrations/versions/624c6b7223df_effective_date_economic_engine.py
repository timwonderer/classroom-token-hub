"""Give economic_engine versions an effective date

Operator ruling 2026-09-30 (DOM-CLASS-003 §VII): a change to a class's economy
is an appended row in its own table, effective at a stated instant, never a
queued transition. ``economic_engine`` already appends one immutable version
per change, but recorded only ``created_at``, so a version dated for later was
in force the moment it was saved. This revision adds ``effective_at``: the
version in force at an instant is the one with the greatest ``effective_at`` at
or before it, the latest ``created_at`` breaking a tie.

Data mapping: ``effective_at := created_at`` for every existing version. Every
version written so far took effect when it was saved (no caller has passed a
later ``effective_at``; on production 2026-09-30 every class_features link row
that differs from its engine's ``created_at`` is a later feature enablement,
not a later engine version), so this reproduces the version each class had in
force at every past instant.

``economic_engine`` refuses UPDATE by trigger (``ae6b7c8d9e0f``). The backfill
disables the table's enabled user triggers for its one statement and re-enables
exactly those, inside this migration's transaction.

An insert that names no ``effective_at`` is in force from its ``created_at``: a
BEFORE INSERT trigger fills it, so a writer that predates the column (or raw
SQL) still records a lawful row rather than failing NOT NULL.

Downgrade drops the trigger, the column, its check and its index. A version
dated for later becomes in force at once on the downgraded schema, as it was
before.

Revision ID: 624c6b7223df
Revises: dd52b19d48d8
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = '624c6b7223df'
down_revision = 'dd52b19d48d8'
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


def enabled_user_triggers(table_name):
    conn = op.get_bind()
    return [
        name for (name,) in conn.execute(text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid = to_regclass(:t) "
            "AND NOT tgisinternal AND tgenabled <> 'D' ORDER BY tgname"
        ), {"t": table_name}).fetchall()
    ]


# ============================================================================
# CONSTANTS
# ============================================================================

TABLE = 'economic_engine'
CHECK_NAME = 'ck_economic_engine_not_retroactive'
INDEX_NAME = 'ix_economic_engine_class_effective'
DEFAULT_FUNCTION = 'economic_engine_default_effective_at'
DEFAULT_TRIGGER = 'economic_engine_default_effective_at'


# ============================================================================
# UPGRADE
# ============================================================================

def _backfill(conn):
    missing = conn.execute(text(
        f"SELECT count(*) FROM {TABLE} WHERE effective_at IS NULL"
    )).scalar()
    if not missing:
        print("⚠️  economic_engine.effective_at already populated, skipping backfill...")
        return
    triggers = enabled_user_triggers(TABLE)
    for trigger in triggers:
        conn.execute(text(f'ALTER TABLE {TABLE} DISABLE TRIGGER "{trigger}"'))
    try:
        conn.execute(text(
            f"UPDATE {TABLE} SET effective_at = created_at WHERE effective_at IS NULL"
        ))
    finally:
        for trigger in triggers:
            conn.execute(text(f'ALTER TABLE {TABLE} ENABLE TRIGGER "{trigger}"'))
    print(f"✅ Set effective_at = created_at on {missing} economic_engine version(s)")


def upgrade():
    conn = op.get_bind()
    if not table_exists(TABLE):
        print("⚠️  economic_engine does not exist, skipping...")
        return
    if not column_exists(TABLE, 'effective_at'):
        op.add_column(TABLE, sa.Column('effective_at', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added economic_engine.effective_at")
    _backfill(conn)
    op.alter_column(TABLE, 'effective_at', existing_type=sa.DateTime(timezone=True), nullable=False)
    if not any('effective_at' in definition for definition in check_constraints_on(TABLE).values()):
        op.create_check_constraint(CHECK_NAME, TABLE, 'effective_at >= created_at')
        print(f"✅ Created check constraint {CHECK_NAME}")
    if not index_exists(TABLE, INDEX_NAME):
        op.create_index(INDEX_NAME, TABLE, ['class_id', 'effective_at'])
        print(f"✅ Created index {INDEX_NAME}")
    conn.execute(text(f"""
        CREATE OR REPLACE FUNCTION {DEFAULT_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF NEW.effective_at IS NULL THEN
                NEW.effective_at := NEW.created_at;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    if not trigger_exists(DEFAULT_TRIGGER):
        conn.execute(text(
            f"CREATE TRIGGER {DEFAULT_TRIGGER} BEFORE INSERT ON {TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION {DEFAULT_FUNCTION}()"
        ))
        print(f"✅ Created trigger {DEFAULT_TRIGGER}")


# ============================================================================
# DOWNGRADE
# ============================================================================

def downgrade():
    conn = op.get_bind()
    if trigger_exists(DEFAULT_TRIGGER):
        conn.execute(text(f"DROP TRIGGER {DEFAULT_TRIGGER} ON {TABLE}"))
    if function_exists(DEFAULT_FUNCTION):
        conn.execute(text(f"DROP FUNCTION {DEFAULT_FUNCTION}()"))
    if not column_exists(TABLE, 'effective_at'):
        print("⚠️  economic_engine.effective_at already absent, skipping...")
        return
    if index_exists(TABLE, INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name=TABLE)
    for name, definition in check_constraints_on(TABLE).items():
        if 'effective_at' in definition:
            op.drop_constraint(name, TABLE, type_='check')
            print(f"❌ Dropped check constraint {name}")
    op.drop_column(TABLE, 'effective_at')
    print("❌ Dropped economic_engine.effective_at")
