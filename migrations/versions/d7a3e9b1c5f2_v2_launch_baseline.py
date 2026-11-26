"""v2 schema era baseline: the v2.0.0 public launch schema

Revision ID: d7a3e9b1c5f2
Revises: None
Create Date: 2026-11-24

SOP-DB-001 §V.C. The supported v2 lineage begins at the v2.0.0 public launch
(commit 26d1792b5, 2026-09-26), whose head revision this file keeps, so no
installation at or after launch changes revision. It replaces the 171
developmental revisions that led to launch, now provenance under
``migrations/archive/v2_prelaunch/`` (historical preservation is not
operational support).

``upgrade()`` executes ``migrations/baseline/d7a3e9b1c5f2_v2_launch_schema.sql``
after checking its SHA-256, and only against a database holding no
application-owned object. ``downgrade()`` refuses: there is nothing before the
era baseline to return to.
"""
import hashlib
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d7a3e9b1c5f2"
down_revision = None
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


BASELINE_SCHEMA = (
    Path(__file__).resolve().parent.parent / "baseline" / "d7a3e9b1c5f2_v2_launch_schema.sql"
)
BASELINE_SHA256 = "3ee2db4aca20f39ac00ea8e8aa982e3e66c635590692bd5326381b585813528f"

# The only objects a database may hold when the baseline runs (SOP-DB-001 §V.C.2):
# Alembic's own version table (empty), its primary key and row types, the
# ``public`` schema, and the ``plpgsql`` extension PostgreSQL installs by default.
# Everything else is application-owned or unknown, and the baseline refuses it.
UNEXPECTED_OBJECTS_SQL = """
SELECT 'schema ' || nspname FROM pg_namespace
 WHERE nspname NOT IN ('public', 'information_schema')
   AND nspname NOT LIKE 'pg\\_%'
UNION ALL
SELECT 'extension ' || extname FROM pg_extension WHERE extname <> 'plpgsql'
UNION ALL
SELECT 'event trigger ' || evtname FROM pg_event_trigger
UNION ALL
SELECT 'relation ' || relname FROM pg_class
 WHERE relnamespace = 'public'::regnamespace
   AND relname NOT IN ('alembic_version', 'alembic_version_pkc')
UNION ALL
SELECT 'type ' || t.typname FROM pg_type t
 WHERE t.typnamespace = 'public'::regnamespace
   AND NOT EXISTS (
       SELECT 1 FROM pg_class c
        WHERE c.relname = 'alembic_version' AND c.relnamespace = 'public'::regnamespace
          AND (t.typrelid = c.oid OR t.oid = (SELECT typarray FROM pg_type WHERE typrelid = c.oid))
   )
UNION ALL
SELECT 'function ' || proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
UNION ALL
SELECT 'operator ' || oprname FROM pg_operator WHERE oprnamespace = 'public'::regnamespace
UNION ALL
SELECT 'collation ' || collname FROM pg_collation WHERE collnamespace = 'public'::regnamespace
UNION ALL
SELECT 'operator family ' || opfname FROM pg_opfamily WHERE opfnamespace = 'public'::regnamespace
UNION ALL
SELECT 'conversion ' || conname FROM pg_conversion WHERE connamespace = 'public'::regnamespace
UNION ALL
SELECT 'text search configuration ' || cfgname FROM pg_ts_config WHERE cfgnamespace = 'public'::regnamespace
UNION ALL
SELECT 'text search dictionary ' || dictname FROM pg_ts_dict WHERE dictnamespace = 'public'::regnamespace
UNION ALL
SELECT 'text search template ' || tmplname FROM pg_ts_template WHERE tmplnamespace = 'public'::regnamespace
UNION ALL
SELECT 'text search parser ' || prsname FROM pg_ts_parser WHERE prsnamespace = 'public'::regnamespace
UNION ALL
SELECT 'operator class ' || opcname FROM pg_opclass WHERE opcnamespace = 'public'::regnamespace
UNION ALL
SELECT 'statistics object ' || stxname FROM pg_statistic_ext WHERE stxnamespace = 'public'::regnamespace
"""


def _verbatim(conn, statement):
    """Run SQL on the DBAPI cursor with no parameters, so ``%`` is never a placeholder."""
    cursor = conn.connection.cursor()
    try:
        cursor.execute(statement)
        return cursor.fetchall() if cursor.description else []
    finally:
        cursor.close()


def unexpected_objects(conn):
    """Names of every object the baseline does not permit to exist before it runs."""
    found = [row[0] for row in _verbatim(conn, UNEXPECTED_OBJECTS_SQL)]
    if _verbatim(conn, "SELECT to_regclass('public.alembic_version')")[0][0]:
        rows = _verbatim(conn, "SELECT count(*) FROM public.alembic_version")[0][0]
        if rows:
            found.append(f"alembic_version holding {rows} row(s)")
    return found


def upgrade():
    conn = op.get_bind()
    found = unexpected_objects(conn)
    if found:
        raise RuntimeError(
            "The v2 era baseline runs only on an empty database; refusing. This database is "
            "neither empty nor at a supported revision (SOP-DB-001 §V.C.2). Found: "
            + ", ".join(sorted(found))
        )
    ddl = BASELINE_SCHEMA.read_bytes()
    if hashlib.sha256(ddl).hexdigest() != BASELINE_SHA256:
        raise RuntimeError(f"{BASELINE_SCHEMA.name} does not match its frozen SHA-256; refusing")
    _verbatim(conn, ddl.decode("utf-8"))
    print("✅ Created the v2 launch baseline schema")


def downgrade():
    raise RuntimeError(
        "d7a3e9b1c5f2 is the v2 schema era baseline; nothing precedes it in the supported "
        "lineage (SOP-DB-001 §V.C). Recover by snapshot restore, not downgrade."
    )
