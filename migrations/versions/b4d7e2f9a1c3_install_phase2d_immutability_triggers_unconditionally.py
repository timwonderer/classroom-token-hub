"""Install the Phase 2d immutability triggers unconditionally

Corrective migration for issue #1357.

`ae6b7c8d9e0f_phase_2d_add_database_immutability_triggers` skips trigger
creation when the migration connection URL contains 'test_db', 'testing', or
'classroom_test_db'. CI's database is named `classroom_test_db`, so the four
immutability triggers were never installed there and the Phase 2d tests that
assert their existence and enforcement failed on every run.

The exception is documented in that migration as:

    Reason: Test helpers (e.g., disable_class_feature) need to delete records

That reason has expired. `tests/helpers/class_domain.py` was rewritten to
append a disablement row with economic_version_id=None rather than delete,
preserving the append-only timeline contract. The only remaining UPDATE and
DELETE statements against these tables anywhere in tests/ are the deliberate
violations inside tests/test_class_phase2_persistence.py, which exist
precisely to prove the triggers raise.

That bypass predicate also disagrees with the test-database safety guard in
app/__init__.py, which requires only the substring 'test'. The two sets differ,
so whether constitutional protections exist during a test run depended on what
the database happened to be named.

Per .claude/rules/database-migrations.md, a migration already merged to main is
never edited; a defective one is corrected by a new migration. This migration
therefore installs what the earlier one skipped. It is idempotent and no-ops on
any database that already has the triggers, production included.

Revision ID: b4d7e2f9a1c3
Revises: 97e131ddb211
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b4d7e2f9a1c3'
down_revision = '97e131ddb211'
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


def trigger_exists(trigger_name):
    """Check if a trigger exists, by name, in the current database."""
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.triggers "
                "WHERE trigger_name = :trigger_name"
            ),
            {"trigger_name": trigger_name},
        ).fetchone()
        return result is not None
    except Exception:
        return False


def function_exists(function_name):
    """Check if a plpgsql function exists in the current database."""
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE p.proname = :function_name"
            ),
            {"function_name": function_name},
        ).fetchone()
        return result is not None
    except Exception:
        return False


# Table -> (update trigger name, delete trigger name)
IMMUTABLE_TABLES = {
    "economic_engine": ("economic_engine_no_update", "economic_engine_no_delete"),
    "class_features": ("class_features_no_update", "class_features_no_delete"),
}


def upgrade():
    """Ensure the Phase 2d immutability triggers exist, in every environment."""
    conn = op.get_bind()

    # Define the trigger functions only if they are absent.
    #
    # These are deliberately NOT re-issued with CREATE OR REPLACE. The delete
    # function's current authority is db2c3d4e5f6a_allow_universe_destruction,
    # which redefined it to yield to the sanctioned session flag
    # `cth.class_universe_destroying` so that the canonical hard-deletion path
    # in app/routes/admin.py can cascade a class away. Re-issuing the older
    # unconditional body from ae6b7c8d9e0f would silently revoke that exemption
    # and break class deletion.
    if not function_exists("prevent_immutable_update"):
        conn.execute(text("""
            CREATE FUNCTION prevent_immutable_update()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'This table is immutable (append-only). Updates are not permitted.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("✅ Created function prevent_immutable_update()")
    else:
        print("ℹ️  Function prevent_immutable_update() already exists, leaving as-is...")

    if not function_exists("prevent_immutable_delete"):
        # Create the current (universe-destruction aware) definition, matching
        # db2c3d4e5f6a rather than the superseded ae6b7c8d9e0f body.
        conn.execute(text("""
            CREATE FUNCTION prevent_immutable_delete()
            RETURNS TRIGGER AS $$
            BEGIN
                IF current_setting('cth.class_universe_destroying', true) = 'on' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'This table is immutable. Deletions are not permitted. These are permanent historical records.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("✅ Created function prevent_immutable_delete()")
    else:
        print("ℹ️  Function prevent_immutable_delete() already exists, leaving as-is...")

    for table_name, (update_trigger, delete_trigger) in IMMUTABLE_TABLES.items():
        if not table_exists(table_name):
            print(f"⚠️  {table_name} not found; skipping trigger creation")
            continue

        if not trigger_exists(update_trigger):
            conn.execute(text(
                f"CREATE TRIGGER {update_trigger} "
                f"BEFORE UPDATE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION prevent_immutable_update();"
            ))
            print(f"✅ Created TRIGGER {update_trigger}")
        else:
            print(f"ℹ️  TRIGGER {update_trigger} already exists, skipping...")

        if not trigger_exists(delete_trigger):
            conn.execute(text(
                f"CREATE TRIGGER {delete_trigger} "
                f"BEFORE DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION prevent_immutable_delete();"
            ))
            print(f"✅ Created TRIGGER {delete_trigger}")
        else:
            print(f"ℹ️  TRIGGER {delete_trigger} already exists, skipping...")


def downgrade():
    """Deliberate no-op.

    This migration's semantic is "ensure the Phase 2d triggers are present",
    and that has no truthful inverse. Dropping the triggers would not restore
    the prior state: on production they were installed by ae6b7c8d9e0f, not by
    this migration, so removing them here would revoke a constitutional
    protection this change never granted.

    A no-op is therefore the honest reversal, and it keeps the downgrade path
    executable rather than adding another raising downgrade (see #1356).
    """
    print("ℹ️  Phase 2d trigger installation is not reversed on downgrade; see docstring.")
