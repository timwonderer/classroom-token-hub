"""Attendance is destroyed with its seat; the delete guard admits seat removal

Revision ID: bb5557cb1609
Revises: f4b8d2a6c1e9
Create Date: 2026-10-01

Live defect since e7a4c2d9f013 (2026-09-20). The ``attendance_sessions_no_delete``
trigger refused every DELETE unless the transaction declared class or account
teardown (``app.attendance_teardown``). Removing part of a roster
(FEAT-IDEN-006) declares neither, so removing any student who had ever clocked
in failed and the route answered "Could not delete the selected students.
Nothing was deleted."

INV-CORE-000 §III.6 requires that a removed seat is erased from its class "as if
they never existed in that class"; DOM-PROD-001 §VII.1.a (v1.4) states that a
seat's attendance is destroyed with the seat and that this is not
correction-in-place. Two changes enforce exactly that and nothing wider.

1. ``prevent_attendance_session_delete()`` additionally admits a DELETE when the
   row's seat — ``target_seat_id``, the seat the attendance fact is about — no
   longer exists in ``seats``. The FK cascade from ``seats`` is the only way that
   condition can be true for a row that still exists: a row cannot reference a
   missing seat outside the cascade that is removing it. Postgres runs the
   referential actions after the parent row is gone, and a BEFORE DELETE trigger
   on the child sees the parent as absent (verified on PG 14 while writing this).
   Deleting rows of a seat that still exists stays refused unless teardown is
   declared; the teardown flag is unchanged.

2. ``attendance_sessions.actor_seat_id`` changes from ``ON DELETE SET NULL`` to
   ``ON DELETE CASCADE``. The column is NOT NULL and the table refuses UPDATE, so
   SET NULL could never succeed: it was a refusal with a misleading error. It
   also broke (1) for every ``mechanism='self'`` row, whose actor IS the removed
   seat: the actor action and the target cascade fire on the same seat delete,
   in an order fixed by internal trigger names (in the migrated schema the actor
   action sorts first), and a SET NULL that runs first aborts the removal.
   CASCADE matches ``ledger_transaction.actor_seat_id`` (DOM-LED-001 §VII.2).
   It does not let an actor's deletion strip a surviving seat's history: the
   cascaded DELETE still passes through the guard, which refuses it while the
   row's target seat exists.

Deploy: production's role carries lock_timeout=10s; re-creating the FK takes
SHARE ROW EXCLUSIVE on attendance_sessions and seats, so run this upgrade with
PGOPTIONS='-c lock_timeout=0'.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'bb5557cb1609'
down_revision = 'f4b8d2a6c1e9'
branch_labels = None
depends_on = None


# --- idempotency helpers (SOP-DB-001) --------------------------------------

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(col['name'] == column_name for col in inspector.get_columns(table_name))
    except sa.exc.NoSuchTableError:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(idx['name'] == index_name for idx in inspector.get_indexes(table_name))
    except sa.exc.NoSuchTableError:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(fk['name'] == fk_name for fk in inspector.get_foreign_keys(table_name))
    except sa.exc.NoSuchTableError:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """FKs on a column, discovered by inspection rather than by name."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk.get('constrained_columns', [])
        ]
    except sa.exc.NoSuchTableError:
        return []


def function_exists(function_name):
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT 1 FROM pg_proc WHERE proname = :name"), {"name": function_name}
    ).scalar()
    return result is not None


TABLE = "attendance_sessions"
ACTOR_COLUMN = "actor_seat_id"
ACTOR_FK = "attendance_sessions_actor_seat_id_fkey"
DELETE_FUNCTION = "prevent_attendance_session_delete"
TEARDOWN_SETTING = "app.attendance_teardown"


# The rule after this revision: teardown, or the row's seat is already gone.
NEW_DELETE_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {DELETE_FUNCTION}()
RETURNS TRIGGER AS $$
BEGIN
    -- Class or teacher-account destruction declares itself (SET LOCAL).
    IF coalesce(current_setting('{TEARDOWN_SETTING}', true), 'off') = 'on' THEN
        RETURN OLD;
    END IF;
    -- Lawful seat removal: the row's seat is already deleted and this DELETE is
    -- the FK cascade destroying the seat's attendance with it
    -- (INV-CORE-000 §III.6, DOM-PROD-001 §VII.1.a).
    IF NOT EXISTS (SELECT 1 FROM seats WHERE id = OLD.target_seat_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION
        'attendance_sessions is append-only (DOM-PROD-001 §184). '
        'A seat''s attendance is removed only with the seat itself, or when the '
        'class or teacher account is destroyed. To remedy an incorrect payroll '
        'outcome, reverse the payroll through FEAT-PROD-003.';
END;
$$ LANGUAGE plpgsql;
"""

# Exactly the text e7a4c2d9f013 installed, indentation included, so that
# downgrade leaves pg_proc.prosrc byte-identical to the previous revision.
PREVIOUS_DELETE_FUNCTION_SQL = f"""
            CREATE OR REPLACE FUNCTION {DELETE_FUNCTION}()
            RETURNS TRIGGER AS $$
            BEGIN
                IF coalesce(current_setting('{TEARDOWN_SETTING}', true), 'off') <> 'on' THEN
                    RAISE EXCEPTION
                        'attendance_sessions is append-only (DOM-PROD-001 §184). '
                        'Rows are removed only when the class or teacher account is '
                        'destroyed, and that path declares itself. To remedy an '
                        'incorrect payroll outcome, reverse the payroll through '
                        'FEAT-PROD-003.';
                END IF;
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql;
        """


def _set_actor_fk_ondelete(ondelete):
    """Re-point actor_seat_id's FK at seats with ``ondelete``; no-op if already so."""
    existing = get_foreign_keys_by_column(TABLE, ACTOR_COLUMN)
    if any(
        (fk.get('options') or {}).get('ondelete', '').upper() == ondelete
        and fk.get('referred_table') == 'seats'
        for fk in existing
    ) and len(existing) == 1:
        print(f"ℹ️  {TABLE}.{ACTOR_COLUMN} FK is already ON DELETE {ondelete}, skipping...")
        return

    for fk in existing:
        op.drop_constraint(fk['name'], TABLE, type_='foreignkey')
        print(f"❌ Dropped FK {fk['name']} on {TABLE}.{ACTOR_COLUMN}")

    if not foreign_key_exists(TABLE, ACTOR_FK):
        op.create_foreign_key(
            ACTOR_FK, TABLE, 'seats', [ACTOR_COLUMN], ['id'], ondelete=ondelete,
        )
        print(f"✅ Created FK {ACTOR_FK} ON DELETE {ondelete}")


def upgrade():
    if not (table_exists(TABLE) and table_exists("seats") and column_exists(TABLE, ACTOR_COLUMN)):
        print(f"⚠️  {TABLE} or seats does not exist, skipping...")
        return

    conn = op.get_bind()

    if not function_exists(DELETE_FUNCTION):
        # e7a4c2d9f013 owns creating the trigger; this revision only amends the
        # rule. Without the function there is no guard to amend.
        print(f"⚠️  {DELETE_FUNCTION}() does not exist, leaving the guard to e7a4c2d9f013...")
    else:
        conn.execute(text(NEW_DELETE_FUNCTION_SQL))
        print(f"✅ Replaced {DELETE_FUNCTION}(): seat removal now admitted")

    _set_actor_fk_ondelete('CASCADE')


def downgrade():
    if not (table_exists(TABLE) and table_exists("seats") and column_exists(TABLE, ACTOR_COLUMN)):
        print(f"⚠️  {TABLE} or seats does not exist, skipping...")
        return

    conn = op.get_bind()

    _set_actor_fk_ondelete('SET NULL')

    if function_exists(DELETE_FUNCTION):
        conn.execute(text(PREVIOUS_DELETE_FUNCTION_SQL))
        print(f"❌ Restored the teardown-only {DELETE_FUNCTION}()")
