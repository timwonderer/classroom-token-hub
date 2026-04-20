import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db_env import resolve_test_database_url

# Override env vars for testing.
# Prefer a real PostgreSQL test database when configured; otherwise fall back to
# in-memory SQLite for isolated environments that do not provide one.
project_root = Path(__file__).resolve().parent.parent
resolved_test_db_url = resolve_test_database_url(os.environ, project_root=project_root)
if resolved_test_db_url:
    os.environ["TEST_DATABASE_URL"] = resolved_test_db_url
    os.environ["DATABASE_URL"] = resolved_test_db_url
else:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("PEPPER", "legacy-pepper")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# Ensure ENCRYPTION_KEY and PEPPER_KEY are set for tests, if not already in .env
# Use valid Fernet keys (32 url-safe base64-encoded bytes)
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("PEPPER_KEY", "tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=")

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool
from app import app as flask_app, db, Student
from app.extensions import limiter


def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _terminate_other_postgres_sessions():
    """Kill stale sessions against the dedicated Postgres test DB before schema reset."""
    if db.engine.dialect.name != "postgresql":
        return

    engine_url = db.engine.url
    db_name = engine_url.database
    if not db_name:
        return

    admin_url = engine_url.set(database="postgres")
    admin_engine = create_engine(
        admin_url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )

    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"db_name": db_name},
            )
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def app():
    """Provide the Flask app instance for tests."""
    # Use a separate test database to avoid clashing with dev data.
    # Prefer TEST_DATABASE_URL when present; DATABASE_URL has already been
    # rewritten above to the resolved test database for import-time safety.
    test_db_url = os.environ.get("TEST_DATABASE_URL", os.environ["DATABASE_URL"])

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=test_db_url,
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
        RATELIMIT_ENABLED=False,
    )
    
    # Ensure strict separation - if connection fails, test fails
    with flask_app.app_context():
        db.session.remove()
        _terminate_other_postgres_sessions()
        db.drop_all()
        db.create_all()

    yield flask_app


@pytest.fixture
def client(app):
    """
    Test client with per-test database isolation.

    On PostgreSQL, keep the schema stable and wrap each test in an outer
    transaction plus a nested savepoint so explicit commits inside tests do not
    leak state into the next test.
    """
    ctx = app.app_context()
    ctx.push()

    limiter.reset()

    if db.engine.dialect.name == 'postgresql':
        connection = db.engine.connect()
        outer_transaction = connection.begin()
        nested_transaction = connection.begin_nested()

        session_factory = sessionmaker(bind=connection)
        test_session = scoped_session(session_factory)

        original_session = db.session
        db.session = test_session

        @event.listens_for(test_session(), "after_transaction_end")
        def restart_savepoint(session, transaction):
            nonlocal nested_transaction
            if transaction.nested and not transaction._parent.nested:
                nested_transaction = connection.begin_nested()

        client = flask_app.test_client()

        try:
            yield client
        finally:
            event.remove(test_session(), "after_transaction_end", restart_savepoint)
            limiter.reset()
            test_session.remove()
            db.session = original_session
            if nested_transaction.is_active:
                nested_transaction.rollback()
            if outer_transaction.is_active:
                outer_transaction.rollback()
            connection.close()
            ctx.pop()
        return

    # SQLite fallback for isolated environments without PostgreSQL.
    db.create_all()
    client = flask_app.test_client()
    try:
        yield client
    finally:
        limiter.reset()
        db.session.remove()
        db.drop_all()
        ctx.pop()


@pytest.fixture
def client_with_fk(client):
    """
    Enable foreign key enforcement for tests that rely on CASCADE behavior.
    SQLite requires PRAGMA foreign_keys=ON per connection; PostgreSQL enforces by default.
    """
    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        event.listen(db.engine, "connect", _set_sqlite_pragma)

        # Also enable on the current connection
        db.session.execute(text("PRAGMA foreign_keys=ON"))

    yield client
    if dialect == 'sqlite':
        event.remove(db.engine, "connect", _set_sqlite_pragma)


@pytest.fixture
def test_student():
    from app.hash_utils import hash_username, get_random_salt
    salt = get_random_salt()
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("test", salt),
        pin_hash="fake-hash",
    )
    db.session.add(stu)
    db.session.commit()
    return stu
