"""The v2 schema era begins at the v2.0.0 launch baseline (SOP-DB-001 §V.C).

The supported lineage has one root, ``d7a3e9b1c5f2``, which executes a frozen,
hashed copy of the launch schema and refuses any database that already holds an
application-owned object. The 171 revisions that led to launch are provenance
under ``migrations/archive/v2_prelaunch/``: nothing executes them, nothing links
to them, and a database recorded at one of them is refused rather than repaired.

Detectors are pure functions over source text so each is fed a synthetic
violation (SOP-TEST-003 §IX.A).
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import re
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from sqlalchemy import inspect, text

from app import db

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "migrations"
VERSIONS = MIGRATIONS / "versions"
ARCHIVE = MIGRATIONS / "archive" / "v2_prelaunch"
BASELINE_REVISION = "d7a3e9b1c5f2"

# Live sources that could link the supported lineage back to provenance.
LIVE_ROOTS = ("app", "scripts", "tests", "infra", ".github", "migrations/versions")
LIVE_SUFFIXES = {".py", ".yml", ".yaml", ".sh"}


def _baseline_module():
    path = next(VERSIONS.glob(f"{BASELINE_REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("_era_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _declared(source: str) -> tuple[str | None, list[str]]:
    """(revision, parents) from a revision file, without importing it."""
    revision, parents = None, []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "revision":
                revision = ast.literal_eval(node.value)
            elif node.targets[0].id == "down_revision":
                value = ast.literal_eval(node.value)
                parents = list(value) if isinstance(value, (list, tuple)) else ([value] if value else [])
    return revision, parents


def _archived_revisions() -> set[str]:
    """Revisions outside the supported lineage.

    The archive also holds the original launch-head file for ``d7a3e9b1c5f2``;
    that id lives on as the baseline, so it is not outside the lineage.
    """
    declared = {_declared(p.read_text(encoding="utf-8"))[0] for p in (ARCHIVE / "versions").glob("*.py")}
    assert BASELINE_REVISION in declared, "the original launch-head revision is missing from provenance"
    return declared - {BASELINE_REVISION}


# ---- detectors ---------------------------------------------------------------

def find_links_to_provenance(source: str, archived: set[str]) -> list[str]:
    """Parents a live revision declares that are archived revisions."""
    return [parent for parent in _declared(source)[1] if parent in archived]


_ARCHIVE_LOAD = re.compile(
    r"(?:from|import)\s+migrations\.archive\b"
    r"|spec_from_file_location\([^)]*archive"
    r"|['\"/]archive/v2_prelaunch/(?:versions|baseline)/[^'\"]+\.(?:py|sql)['\"][^\n]*(?:exec_module|read_text|exec_driver_sql|execute)",
    re.DOTALL,
)


def find_archive_execution(source: str) -> list[str]:
    """Places a live source imports or executes an archived migration artifact."""
    return [" ".join(m.group(0).split())[:100] for m in _ARCHIVE_LOAD.finditer(source)]


# ---- the supported lineage ---------------------------------------------------

def test_lineage_has_one_root_and_it_is_the_launch_revision():
    script = ScriptDirectory(str(MIGRATIONS))
    assert script.get_bases() == [BASELINE_REVISION]
    assert len(script.get_heads()) == 1


def test_baseline_executes_its_frozen_artifact():
    module = _baseline_module()
    assert module.down_revision is None
    assert hashlib.sha256(module.BASELINE_SCHEMA.read_bytes()).hexdigest() == module.BASELINE_SHA256


def test_no_live_revision_links_to_an_archived_revision():
    archived = _archived_revisions()
    assert len(archived) == 170, "the provenance set changed size; the guard would weaken silently"
    offenders = {
        path.name: links
        for path in VERSIONS.glob("*.py")
        if (links := find_links_to_provenance(path.read_text(encoding="utf-8"), archived))
    }
    assert offenders == {}


def test_no_live_source_executes_an_archived_artifact():
    offenders = []
    for root in LIVE_ROOTS:
        for path in sorted((ROOT / root).rglob("*")):
            if path.suffix in LIVE_SUFFIXES and path.is_file() and path != Path(__file__).resolve():
                offenders += [f"{path.relative_to(ROOT)}: {hit}"
                              for hit in find_archive_execution(path.read_text(encoding="utf-8", errors="replace"))]
    assert offenders == []


def test_an_archived_revision_cannot_be_resolved():
    """A database recorded at a pre-launch revision is refused, not upgraded."""
    script = ScriptDirectory(str(MIGRATIONS))
    for revision in ("7c3d4e5f6a7b", "c7a7b8c9d0e1", "0001"):
        with pytest.raises(ResolutionError):
            list(script.iterate_revisions("heads", revision))


# ---- mutation proofs ---------------------------------------------------------

def test_mutation_revision_parented_on_provenance_is_reported():
    source = "revision = 'zz01'\ndown_revision = '7c3d4e5f6a7b'\n"
    assert find_links_to_provenance(source, {"7c3d4e5f6a7b"}) == ["7c3d4e5f6a7b"]
    merge = "revision = 'zz02'\ndown_revision = ('a0faf8b2a35d', '7c3d4e5f6a7b')\n"
    assert find_links_to_provenance(merge, {"7c3d4e5f6a7b"}) == ["7c3d4e5f6a7b"]
    assert not find_links_to_provenance("revision = 'zz03'\ndown_revision = 'a0faf8b2a35d'\n", {"7c3d4e5f6a7b"})


@pytest.mark.parametrize("source", [
    "from migrations.archive.v2_prelaunch.versions import x",
    "spec = importlib.util.spec_from_file_location('m', ROOT / 'migrations/archive/v2_prelaunch/versions/c7a7b8c9d0e1_seat_owned_records.py')",
    "conn.exec_driver_sql(Path('migrations/archive/v2_prelaunch/baseline/0001_baseline_schema.sql').read_text())",
])
def test_mutation_executing_an_archived_artifact_is_reported(source):
    assert find_archive_execution(source)


def test_reading_provenance_as_text_is_not_execution():
    # The migration validator's regression test reads two archived files as text.
    assert not find_archive_execution('path = ROOT / "migrations" / "archive" / "v2_prelaunch" / "versions" / name')


# ---- the baseline fails closed -------------------------------------------------

def test_baseline_refuses_a_database_holding_application_objects(client):
    module = _baseline_module()
    with db.engine.connect() as conn:
        found = module.unexpected_objects(conn)
        assert "relation seats" in found and "relation ledger_transaction" in found
        assert any(item.startswith("function ") for item in found)
        assert any(item.startswith("type ") for item in found)
        assert "alembic_version holding 1 row(s)" in found


def test_baseline_upgrade_on_a_populated_database_raises_and_changes_nothing(client):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _baseline_module()
    catalog = text("SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace")
    with db.engine.connect() as conn:
        before = conn.execute(catalog).scalar()
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="runs only on an empty database"):
                module.upgrade()
        conn.rollback()
        assert conn.execute(catalog).scalar() == before


def test_baseline_permits_only_infrastructure_objects(client):
    """An empty schema with Alembic's own empty table passes; each extra object is named."""
    module = _baseline_module()
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("CREATE TABLE public.alembic_version (version_num VARCHAR(32) NOT NULL, "
                              "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
            assert module.unexpected_objects(conn) == []

            for ddl, expected in [
                ("CREATE SEQUENCE public.stray_seq", "relation stray_seq"),
                ("CREATE TYPE public.stray_enum AS ENUM ('a')", "type stray_enum"),
                ("CREATE FUNCTION public.stray_fn() RETURNS int LANGUAGE sql AS 'SELECT 1'", "function stray_fn"),
                ("CREATE SCHEMA stray_schema", "schema stray_schema"),
                ("INSERT INTO public.alembic_version VALUES ('0001')", "alembic_version holding 1 row(s)"),
            ]:
                conn.execute(text(ddl))
                assert expected in module.unexpected_objects(conn), ddl
        finally:
            transaction.rollback()


def test_baseline_refuses_a_changed_artifact(client, monkeypatch):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _baseline_module()
    monkeypatch.setattr(module, "unexpected_objects", lambda conn: [])
    monkeypatch.setattr(module, "BASELINE_SHA256", "0" * 64)
    monkeypatch.setattr(module, "_verbatim", lambda conn, sql: pytest.fail("executed a changed artifact"))
    with db.engine.connect() as conn, Operations.context(MigrationContext.configure(conn)):
        with pytest.raises(RuntimeError, match="frozen SHA-256"):
            module.upgrade()


def test_baseline_downgrade_refuses():
    with pytest.raises(RuntimeError, match="era baseline"):
        _baseline_module().downgrade()


# ---- end-state contracts relocated from retired pre-launch migration tests ----

def _columns(table):
    return {c["name"]: c for c in inspect(db.engine).get_columns(table)}


def test_support_ticket_is_class_scoped_without_a_key_to_seats(client):
    """Was test_support_seat_revision_scopes_the_ticket_without_a_key_to_seats (e3c3d4e5f6a7)."""
    columns = _columns("issues")
    assert columns["class_public_id"]["nullable"] is False
    assert not [fk for fk in inspect(db.engine).get_foreign_keys("issues") if fk["referred_table"] == "seats"]


def test_support_permissions_default_to_no_consent(client):
    """Was test_permission_migration_defaults_old_rows_to_no_consent (d2b2c3d4e5f6)."""
    column = _columns("issues")["support_permissions"]
    assert column["nullable"] is False
    assert column["default"].startswith("'{}'")


def test_request_trace_lives_and_dies_with_its_class_only(client):
    """Was test_request_trace_migration (a5e5f6a7b8c9, d9e1f3a5b7c9): class FK cascades, no seat FK."""
    fks = inspect(db.engine).get_foreign_keys("actor_request_trace")
    assert [(fk["referred_table"], fk["constrained_columns"], fk["options"].get("ondelete")) for fk in fks] == [
        ("classes", ["class_id"], "CASCADE")
    ]


def test_student_recovery_session_columns_exist(client):
    """Was test_recovery_session_migration (f4d4e5f6a7b8)."""
    columns = _columns("users")
    for name in ("recovery_setup_nonce_hash", "recovery_setup_expires_at"):
        assert columns[name]["nullable"] is True
