"""Derive a release artifact from Git and a new private PostgreSQL 14 cluster."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from uuid import uuid4
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import zipfile

from alembic.script import ScriptDirectory
from fresh_database import ROOT, digest, dump, install, inventory, require, target


def installable_ddl(oracle):
    # Preserve the original varchar IN catalog expressions (see SOP-DB-001).
    pattern = rb"\(\(([a-z_]+)\)::text = ANY \(\(ARRAY\[((?:'[a-zA-Z_]+'::character varying(?:, )?)+)\]\)::text\[\]\)\)"
    def original(match):
        names = re.findall(rb"'[a-zA-Z_]+'", match[2])
        return b"(" + match[1] + b" IN (" + b", ".join(names) + b"))"
    return b"".join(re.sub(pattern, original, line) if b"CHECK (" in line or line.startswith(b"CREATE UNIQUE INDEX")
                    else line for line in oracle.splitlines(keepends=True))


def generate(sha, output):
    require(re.fullmatch("[a-f0-9]{40}", sha), "supply exact reviewed source SHA")
    require(not output.exists(), "choose a new output directory")
    # Short socket path even on macOS. No inherited PG*, application config or TCP listener.
    with tempfile.TemporaryDirectory(prefix="cth-schema-", dir="/tmp") as tmp:
        tmp = Path(tmp)
        source = tmp / "source"
        source.mkdir()
        env = {"PATH": os.environ["PATH"], "HOME": str(tmp), "LC_ALL": "C"}
        # The generator is a standalone process. Apply the scrubbed environment
        # to in-process libpq and pg_dump as well as the migration subprocess.
        os.environ.clear()
        os.environ.update(env)
        def run(*args, **kwargs):
            return subprocess.run(args, env=env, check=True, **kwargs)
        run("git", "-C", ROOT, "archive", "--format=zip", "-o", tmp/"source.zip", sha)
        with zipfile.ZipFile(tmp/"source.zip") as archive:
            archive.extractall(source)
        heads = ScriptDirectory(str(source/"migrations")).get_heads()
        require(len(heads) == 1, "ambiguous release head")
        revision = heads[0]
        opts = SimpleNamespace(host=str(tmp), port=55439, user="cth_baseline", database="cth_oracle_test")
        run("initdb", "--no-locale", "-E", "UTF8", "-A", "trust", "-U", opts.user, "-D", tmp/"data",
            stdout=subprocess.DEVNULL)
        run("pg_ctl", "-D", tmp/"data", "-l", tmp/"pg.log", "-o", f"-h '' -k {tmp} -p {opts.port}", "-w", "start")
        try:
            run("createdb", "-h", tmp, "-p", str(opts.port), "-U", opts.user, "-T", "template0", opts.database)
            empty = digest(dump(opts))
            env.update(FLASK_SKIP_DOTENV="1", PYTHON_DOTENV_DISABLED="1", FLASK_APP="app", FLASK_ENV="testing",
                       DATABASE_URL=f"postgresql://{opts.user}@/{opts.database}?host={tmp}&port={opts.port}",
                       SECRET_KEY=secrets.token_hex(32), PEPPER_KEY=secrets.token_hex(32),
                       AUDIT_HMAC_KEY=secrets.token_hex(32),
                       ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
            run(sys.executable, "-m", "flask", "db", "upgrade", revision, cwd=source)
            schema = dump(opts)
            ddl = installable_ddl(schema)
            conn = target(opts)
            try:
                with conn.cursor() as cur:
                    cur.execute("SHOW server_version")
                    version = cur.fetchone()[0]
                    require(version.startswith("14."), "generation requires PostgreSQL 14")
                    state = inventory(cur, [(revision,)])
            finally:
                conn.close()
            report = {**state, "release_sha": sha, "revision": revision, "postgresql": version,
                      "pg_dump": run("pg_dump", "--version", capture_output=True, text=True).stdout.strip(),
                      "schema_sha256": digest(schema), "empty_schema_sha256": empty, "ddl_sha256": digest(ddl)}
            bundle = source / "migrations/fresh" / revision
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle/"schema.sql").write_bytes(ddl)
            (bundle/"manifest.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
            # Exercise the actual installer under an ordinary database owner.
            run("createuser", "-h", tmp, "-p", str(opts.port), "-U", opts.user,
                "--no-superuser", "--no-createdb", "--no-createrole", "cth_install")
            run("createdb", "-h", tmp, "-p", str(opts.port), "-U", opts.user,
                "-O", "cth_install", "-T", "template0", "cth_direct_test")
            direct = SimpleNamespace(**{**vars(opts), "database": "cth_direct_test",
                                        "user": "cth_install", "installation_id": uuid4()})
            with target(direct) as connection, connection.cursor() as cur:
                cur.execute("COMMENT ON DATABASE cth_direct_test IS %s", ("cth-fresh:" + str(direct.installation_id),))
            connection.close()
            install(direct, release_root=source)
            with target(direct) as connection, connection.cursor() as cur:
                require(inventory(cur, [(revision,)]) == state, "post-stamp state mismatch")
            connection.close()
            require(digest(dump(direct)) == digest(schema), "post-stamp schema mismatch")
            output.mkdir(parents=True)
            for filename in ("schema.sql", "manifest.json"):
                shutil.copyfile(bundle / filename, output / filename)
        finally:
            run("pg_ctl", "-D", tmp/"data", "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.source_sha, args.output)
