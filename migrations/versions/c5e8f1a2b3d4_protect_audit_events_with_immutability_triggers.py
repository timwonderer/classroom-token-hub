"""Protect audit_events with database-level immutability triggers

INV-ARC-016 §VIII: "`UPDATE` and `DELETE` on `audit_events` are prohibited in
all environments."

The prohibition was enforced only by convention. `prevent_immutable_update()`
and `prevent_immutable_delete()` existed and demonstrably fired, but they were
attached only to `economic_engine` and `class_features`; a plain `UPDATE
audit_events SET ...` succeeded. The hash chain (`previous_hash` /
`event_hash` / `hmac_signature` plus `chain_heads`) makes tampering
*detectable* after the fact — it did not make it *impossible*.

The audit table gets its own pair of trigger functions rather than reusing the
shared ones. `prevent_immutable_delete()` yields to the sanctioned session flag
`cth.class_universe_destroying` so that class deletion can cascade a class's
history away; §VIII admits no such exemption, and no code path deletes audit
rows during class or teacher destruction, so binding audit_events to a function
carrying that escape hatch would grant an exemption nothing asks for.

Revision ID: c5e8f1a2b3d4
Revises: d03dafc9b9c9
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c5e8f1a2b3d4'
down_revision = 'd03dafc9b9c9'
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


def trigger_exists(table_name, trigger_name):
    """Check whether a trigger exists ON THIS TABLE.

    Scoped by table on purpose: Postgres enforces trigger-name uniqueness per
    relation, not per database, so a name-only match could report a same-named
    trigger on another table as this one and skip installing the protection
    here.
    """
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgrelid = to_regclass(:table_name) "
                "AND tgname = :trigger_name "
                "AND NOT tgisinternal"
            ),
            {"table_name": table_name, "trigger_name": trigger_name},
        ).fetchone()
        return result is not None
    except Exception:
        return False


def function_exists(function_name):
    """Check whether the zero-argument trigger function of this name exists.

    Matched by exact identity via `to_regprocedure` rather than by name;
    `pg_proc.proname` repeats across schemas and overloads.
    """
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM pg_proc p "
                "WHERE p.oid = to_regprocedure(:signature) "
                "AND p.prorettype = 'trigger'::regtype"
            ),
            {"signature": f"{function_name}()"},
        ).fetchone()
        return result is not None
    except Exception:
        return False


UPDATE_TRIGGER = "audit_events_no_update"
DELETE_TRIGGER = "audit_events_no_delete"


def upgrade():
    """Attach unconditional UPDATE/DELETE guards to audit_events."""
    conn = op.get_bind()

    if not function_exists("prevent_audit_event_update"):
        conn.execute(text("""
            CREATE FUNCTION prevent_audit_event_update()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only (INV-ARC-016 VIII). Updates are not permitted in any environment.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("✅ Created function prevent_audit_event_update()")
    else:
        print("ℹ️  Function prevent_audit_event_update() already exists, leaving as-is...")

    if not function_exists("prevent_audit_event_delete"):
        conn.execute(text("""
            CREATE FUNCTION prevent_audit_event_delete()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only (INV-ARC-016 VIII). Deletions are not permitted in any environment.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("✅ Created function prevent_audit_event_delete()")
    else:
        print("ℹ️  Function prevent_audit_event_delete() already exists, leaving as-is...")

    if not table_exists("audit_events"):
        print("⚠️  audit_events not found; skipping trigger creation")
        return

    if not trigger_exists("audit_events", UPDATE_TRIGGER):
        conn.execute(text(
            f"CREATE TRIGGER {UPDATE_TRIGGER} "
            "BEFORE UPDATE ON audit_events "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_update();"
        ))
        print(f"✅ Created TRIGGER {UPDATE_TRIGGER}")
    else:
        print(f"ℹ️  TRIGGER {UPDATE_TRIGGER} already exists, skipping...")

    if not trigger_exists("audit_events", DELETE_TRIGGER):
        conn.execute(text(
            f"CREATE TRIGGER {DELETE_TRIGGER} "
            "BEFORE DELETE ON audit_events "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_delete();"
        ))
        print(f"✅ Created TRIGGER {DELETE_TRIGGER}")
    else:
        print(f"ℹ️  TRIGGER {DELETE_TRIGGER} already exists, skipping...")


def downgrade():
    """Drop only what this migration created.

    Unlike the shared Phase 2d functions, these two are introduced here and
    used by nothing else, so removing them is a truthful inverse.
    """
    conn = op.get_bind()

    if table_exists("audit_events"):
        conn.execute(text(f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER} ON audit_events;"))
        conn.execute(text(f"DROP TRIGGER IF EXISTS {DELETE_TRIGGER} ON audit_events;"))
        print("❌ Dropped audit_events immutability triggers")

    conn.execute(text("DROP FUNCTION IF EXISTS prevent_audit_event_update();"))
    conn.execute(text("DROP FUNCTION IF EXISTS prevent_audit_event_delete();"))
