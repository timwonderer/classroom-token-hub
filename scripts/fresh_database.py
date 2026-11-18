"""Install a reviewed CTH release database. No Flask config or DATABASE_URL is used."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID

import psycopg2
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[1]
COLUMNS = "id, name, description, category_type, is_active, display_order"
IDENT = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(opts, snapshot=None):
    # Only transport/header lines are removed. Keep complete database definitions.
    command = ["pg_dump", "--schema-only", "--no-owner", "--no-password", "--lock-wait-timeout=5s",
               "--host", opts.host, "--port", str(opts.port), "--username", opts.user,
               "--dbname", opts.database]
    if snapshot:
        command += ["--snapshot", snapshot]
    env = {k: os.environ[k] for k in ("PATH", "HOME", "PGPASSFILE") if k in os.environ}
    data = subprocess.check_output(command, env={**env, "LC_ALL": "C"}, stderr=subprocess.PIPE)
    return re.sub(rb"^(?:\\(?:un)?restrict [A-Za-z0-9]+|-- Dumped (?:from database|by pg_dump) version [^\n]*)\n", b"", data, flags=re.M)


def target(opts):
    require(Path(opts.host).is_absolute() and Path(opts.host).is_dir(), "explicit Unix socket directory required")
    require(1 <= opts.port <= 65535 and IDENT.fullmatch(opts.user) and
            IDENT.fullmatch(opts.database) and opts.database not in ("postgres", "template0", "template1"),
            "invalid or reserved target")
    require(not any(key.startswith("PG") and key != "PGPASSFILE" for key in os.environ),
            "clear inherited libpq variables; only PGPASSFILE is supported")
    return psycopg2.connect(host=opts.host, port=opts.port, dbname=opts.database, user=opts.user,
                            options="-c search_path=pg_catalog", connect_timeout=5)


def rows(cur, query):
    cur.execute(query)
    return cur.fetchall()


def user_objects(cur, kind):
    cur.execute("""SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE c.relkind=ANY(%s) AND n.nspname NOT IN ('information_schema','pg_catalog')
                   AND n.nspname NOT LIKE 'pg_toast%%' ORDER BY 1,2""", (list(kind),))
    return cur.fetchall()


def inventory(cur, expected_version):
    # Never export application rows. Fail if anything except approved reference data exists.
    for schema, name in user_objects(cur, "rpmf"):
        table = sql.Identifier(schema, name)
        if (schema, name) == ("public", "alembic_version"):
            require(rows(cur, "SELECT version_num FROM public.alembic_version") == expected_version,
                    "unexpected migration state")
        elif (schema, name) != ("public", "issue_categories"):
            cur.execute(sql.SQL("SELECT EXISTS(SELECT FROM {} LIMIT 1)").format(table))
            require(not cur.fetchone()[0], "unexpected populated table: " + name)
    categories = rows(cur, "SELECT " + COLUMNS + " FROM public.issue_categories ORDER BY id")
    require(len(categories) == 15 and rows(cur, "SELECT count(created_at), count(DISTINCT created_at) "
            "FROM public.issue_categories") == [(15, 1)], "invalid reference seed or timestamps")
    seq = {}
    for schema, name in user_objects(cur, "S"):
        require(schema == "public", "unexpected sequence schema")
        seq[name] = list(rows(cur, sql.SQL("SELECT last_value,is_called FROM {}").format(
            sql.Identifier(schema, name)))[0])
    return {"categories": [list(row) for row in categories], "sequences": seq}


def install(opts, release_root=ROOT):
    from alembic.script import ScriptDirectory
    heads = ScriptDirectory(str(release_root / "migrations")).get_heads()
    require(len(heads) == 1, "ambiguous release head")
    bundle = release_root / "migrations/fresh" / heads[0]
    manifest = json.loads((bundle / "manifest.json").read_text())
    ddl = (bundle / "schema.sql").read_bytes()
    require(digest(ddl) == manifest["ddl_sha256"], "artifact checksum mismatch")
    require(heads == [manifest["revision"]],
            "artifact does not match this checkout's sole head")
    require(re.match(r"pg_dump \(PostgreSQL\) 14\.", subprocess.check_output(
        ["pg_dump", "--version"], text=True)), "PostgreSQL 14 pg_dump required")
    conn = target(opts)
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_database(), session_user, r.rolname, shobj_description(d.oid,'pg_database'),
                           current_setting('server_version_num')::int / 10000,
                           pg_try_advisory_lock(1163151443, 1)
                           FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=current_database()""")
            require(cur.fetchone() == (opts.database, opts.user, opts.user, "cth-fresh:" + str(opts.installation_id),
                                       14, True), "target identity, owner, enrollment, server or lock mismatch")
            require(rows(cur, """SELECT pg_encoding_to_char(encoding), datcollate, datctype
                                 FROM pg_database WHERE datname=current_database()""") == [("UTF8", "C", "C")],
                    "expected UTF8 and C collation/ctype")
            require(rows(cur, """SELECT EXISTS(SELECT FROM pg_db_role_setting s JOIN pg_database d
                                 ON s.setdatabase=d.oid WHERE d.datname=current_database())""") == [(False,)],
                    "database-specific role or session settings present")
            require(rows(cur, "SELECT EXISTS(SELECT FROM pg_largeobject_metadata)") == [(False,)], "large objects present")
            require(digest(dump(opts)) == manifest["empty_schema_sha256"], "database is not a recognized empty template")
            require(rows(cur, """SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()
                                 AND pid<>pg_backend_pid()""") == [(0,)],
                    "another client is connected; take the fresh target offline")
            cur.execute(ddl.decode())
            cur.executemany("INSERT INTO public.issue_categories (" + COLUMNS + ",created_at) "
                            "VALUES (%s,%s,%s,%s,%s,%s,transaction_timestamp())", manifest["categories"])
            for name, (value, called) in manifest["sequences"].items():
                cur.execute("SELECT pg_catalog.setval(%s::regclass,%s,%s)", ("public." + name, value, called))
            relations = user_objects(cur, "rp")
        conn.commit()  # pg_dump must see installed DDL. No revision exists yet.
        conn.set_session(isolation_level="REPEATABLE READ")
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            for schema, name in relations:
                cur.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(sql.Identifier(schema, name)))
            snapshot = rows(cur, "SELECT pg_export_snapshot()")[0][0]
            require(digest(dump(opts, snapshot)) == manifest["schema_sha256"], "installed schema mismatch; unversioned")
            actual = inventory(cur, [])
            require(all(actual[k] == manifest[k] for k in actual), "installed reference state mismatch; unversioned")
            cur.execute("INSERT INTO public.alembic_version(version_num) VALUES (%s)", (manifest["revision"],))
        conn.commit()
        print("Verified new database at revision", manifest["revision"])
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("host", "database", "user"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--installation-id", type=UUID, required=True)
    try:
        install(parser.parse_args())
    except psycopg2.Error as error:
        sys.exit("Installation refused or incomplete; PostgreSQL SQLSTATE: " + str(error.pgcode))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit("Installation refused or incomplete: " + str(error))


if __name__ == "__main__":
    main()
