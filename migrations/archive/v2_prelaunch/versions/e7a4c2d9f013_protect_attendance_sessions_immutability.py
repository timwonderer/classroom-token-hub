"""Protect attendance_sessions with immutability triggers

DOM-PROD-001 states this four times — §108 "Once written, an
``attendance_sessions`` row is permanent. It SHALL NOT be edited, deleted,
soft-deleted, marked as deleted, hidden from payroll, or corrected in place";
§176-177 append-only and immutable; §184 no delete/edit/correction-in-place
behaviour; §185 no correcting payroll by mutating attendance history.

The database enforced none of it. `attendance_sessions` carried no triggers and
no chain columns, and a direct UPDATE succeeded silently. Four other tables were
already protected — audit_events, ledger_transaction, economic_engine,
class_features — and the asymmetry is the point: ledger_transaction, the OUTPUT,
could not be rewritten, while attendance_sessions, the input that justifies every
dollar that output contains, could be. Payroll reads attendance and nothing else
determines what a student is paid. The money was defended; the evidence for it
was not.

DELETE is gated rather than forbidden. Unlike audit_events, attendance rows are
legitimately removed when a class or a teacher account is destroyed
(app/utils/deletion.py, app/services/teacher_destruction.py) — teardown, not
correction-in-place, and consistent with the rule's intent. A blanket DELETE
guard would break account destruction. The guard therefore refuses unless the
transaction has explicitly declared teardown, which those two paths do and
nothing else may.

Revision ID: e7a4c2d9f013
Revises: d9e1f3a5b7c9
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'e7a4c2d9f013'
down_revision = 'd9e1f3a5b7c9'
branch_labels = None
depends_on = None


# --- idempotency helpers (SOP-DB-001) --------------------------------------

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def function_exists(function_name):
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT 1 FROM pg_proc WHERE proname = :name"), {"name": function_name}
    ).scalar()
    return result is not None


def trigger_exists(trigger_name):
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT 1 FROM pg_trigger WHERE tgname = :name AND NOT tgisinternal"),
        {"name": trigger_name},
    ).scalar()
    return result is not None


UPDATE_FUNCTION = "prevent_attendance_session_update"
DELETE_FUNCTION = "prevent_attendance_session_delete"
UPDATE_TRIGGER = "attendance_sessions_no_update"
DELETE_TRIGGER = "attendance_sessions_no_delete"

# Transaction-local flag a teardown path sets with SET LOCAL, so it expires with
# the transaction and cannot leak into an unrelated one on a pooled connection.
TEARDOWN_SETTING = "app.attendance_teardown"


def upgrade():
    if not table_exists("attendance_sessions"):
        print("⚠️  attendance_sessions does not exist, skipping...")
        return

    conn = op.get_bind()

    if not function_exists(UPDATE_FUNCTION):
        conn.execute(text(f"""
            CREATE FUNCTION {UPDATE_FUNCTION}()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION
                    'attendance_sessions is append-only (DOM-PROD-001 §108). '
                    'An attendance row is never edited or corrected in place. '
                    'To remedy an incorrect payroll outcome, reverse the payroll '
                    'through FEAT-PROD-003.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print(f"✅ Created {UPDATE_FUNCTION}()")
    else:
        print(f"ℹ️  {UPDATE_FUNCTION}() already exists, leaving as-is...")

    if not function_exists(DELETE_FUNCTION):
        conn.execute(text(f"""
            CREATE FUNCTION {DELETE_FUNCTION}()
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
        """))
        print(f"✅ Created {DELETE_FUNCTION}()")
    else:
        print(f"ℹ️  {DELETE_FUNCTION}() already exists, leaving as-is...")

    if not trigger_exists(UPDATE_TRIGGER):
        conn.execute(text(f"""
            CREATE TRIGGER {UPDATE_TRIGGER}
            BEFORE UPDATE ON attendance_sessions
            FOR EACH ROW EXECUTE FUNCTION {UPDATE_FUNCTION}();
        """))
        print(f"✅ Created trigger {UPDATE_TRIGGER}")
    else:
        print(f"ℹ️  Trigger {UPDATE_TRIGGER} already exists, leaving as-is...")

    if not trigger_exists(DELETE_TRIGGER):
        conn.execute(text(f"""
            CREATE TRIGGER {DELETE_TRIGGER}
            BEFORE DELETE ON attendance_sessions
            FOR EACH ROW EXECUTE FUNCTION {DELETE_FUNCTION}();
        """))
        print(f"✅ Created trigger {DELETE_TRIGGER}")
    else:
        print(f"ℹ️  Trigger {DELETE_TRIGGER} already exists, leaving as-is...")


def downgrade():
    conn = op.get_bind()

    if trigger_exists(UPDATE_TRIGGER):
        conn.execute(text(f"DROP TRIGGER {UPDATE_TRIGGER} ON attendance_sessions;"))
        print(f"❌ Dropped trigger {UPDATE_TRIGGER}")
    if trigger_exists(DELETE_TRIGGER):
        conn.execute(text(f"DROP TRIGGER {DELETE_TRIGGER} ON attendance_sessions;"))
        print(f"❌ Dropped trigger {DELETE_TRIGGER}")
    if function_exists(UPDATE_FUNCTION):
        conn.execute(text(f"DROP FUNCTION {UPDATE_FUNCTION}();"))
        print(f"❌ Dropped {UPDATE_FUNCTION}()")
    if function_exists(DELETE_FUNCTION):
        conn.execute(text(f"DROP FUNCTION {DELETE_FUNCTION}();"))
        print(f"❌ Dropped {DELETE_FUNCTION}()")
