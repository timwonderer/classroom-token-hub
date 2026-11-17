"""Run B1 protected-row acceptance on an enrolled, offline disposable baseline."""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import text

from scripts.fresh_database import ROOT, inventory, require, target


def verify(opts):
    require(__debug__, "run with Python assertions enabled")
    require(not (ROOT / ".env").exists(), "run from a release source export without .env")
    require(opts.database.endswith("_test"), "target must be a disposable test database")
    path = os.environ["PATH"]
    os.environ.clear()
    os.environ["PATH"] = path

    def snapshot():
        conn = target(opts)
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT current_database(), session_user, pg_get_userbyid(datdba),
                                   shobj_description(oid,'pg_database'), current_setting('listen_addresses')
                               FROM pg_database WHERE datname=current_database()""")
                require(cur.fetchone() == (opts.database, opts.user, opts.user,
                                           f"cth-fresh:{opts.installation_id}", ""),
                        "target must be enrolled and owned by this user on a socket-only server")
                cur.execute("SELECT version_num FROM public.alembic_version")
                versions = cur.fetchall()
                require(len(versions) == 1, "expected one installed revision")
                revision = versions[0][0]
                manifest = json.loads((ROOT / "migrations/fresh" / revision / "manifest.json").read_text())
                state = inventory(cur, versions)
                require(state == {k: manifest[k] for k in state}, "database differs from fresh reference data")
                return state
        finally:
            conn.close()

    before = snapshot()
    uri = f"postgresql://{opts.user}@/{opts.database}?{urlencode({'host': opts.host, 'port': opts.port})}"
    os.environ.update(TEST_DATABASE_URL=uri, AUDIT_HMAC_KEY=secrets.token_hex(32))
    # Load test-only configuration directly. Pytest's database rebuild fixture must never run here.
    from tests.conftest import db, flask_app
    from tests.dom.ops.test_fresh_install_audit import test_first_manual_credit_authenticates_payload_and_complete_class_head

    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, ENV="testing", SESSION_COOKIE_SECURE=False,
                            RATELIMIT_ENABLED=False)
    with flask_app.app_context():
        engine = db.engine
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                require(connection.scalar(text("SELECT current_database()")) == opts.database, "wrong test target")
                # nextval normally survives rollback. RESTART creates transactional
                # sequence state for the test's allocations, discarded with the enclosing transaction.
                for name in before["sequences"]:
                    quoted = connection.dialect.identifier_preparer.quote(name)
                    connection.exec_driver_sql(f"ALTER SEQUENCE public.{quoted} RESTART")
                db.engines[None] = connection
                db.session.configure(join_transaction_mode="create_savepoint")
                test_first_manual_credit_authenticates_payload_and_complete_class_head(flask_app.test_client(), flask_app)
                require(outer.is_active, "test left the enclosing transaction")
            finally:
                db.session.remove()
                db.engines[None] = engine
                outer.rollback()
    require(snapshot() == before, "fresh reference data or sequence state changed")
    print("Verified the protected payroll credit, complete class head, rejection cases and rollback.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Private PostgreSQL Unix socket directory")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--user", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--installation-id", required=True, type=UUID)
    verify(parser.parse_args())
