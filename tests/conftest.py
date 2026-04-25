import os
import sys
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

# Load environment variables from the project root .env file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=DOTENV_PATH)

# Read TEST_DATABASE_URL directly from .env so tests can use the dedicated test DB
dotenv_config = dotenv_values(DOTENV_PATH)
test_database_url = dotenv_config.get("TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError("TEST_DATABASE_URL must be set in .env for tests.")

# Override env vars for testing
os.environ["SECRET_KEY"] = "test-secret"
os.environ["TEST_DATABASE_URL"] = test_database_url
os.environ["DATABASE_URL"] = test_database_url
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("PEPPER", "legacy-pepper")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# Ensure ENCRYPTION_KEY and PEPPER_KEY are set for tests, if not already in .env
# Use valid Fernet keys (32 url-safe base64-encoded bytes)
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("PEPPER_KEY", "tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=")


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from app import app as flask_app, db, Student
from flask import current_app
from app.extensions import limiter

def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()





def _rebuild_database_state():
    """Rebuild the Postgres test database schema from scratch."""
    import app.models  # Ensure model metadata is registered before create_all().

    db.session.remove()
    
    # Determine dialect from config URL to avoid stale engine property access
    test_db_url = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    is_postgres = "postgresql" in test_db_url

    if is_postgres:
        # For Postgres, we do a faster wipe by dropping the schema.
        # We dispose the engine to clear all connections before dropping the schema.
        db.engine.dispose()
        
        # Use a raw connection to avoid SQLAlchemy's transaction management during schema drop
        with db.engine.connect() as conn:
            # Postgres doesn't allow DROP SCHEMA inside a transaction block in some cases,
            # or it can cause locks. We use an explicit commit.
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.execute(text("SET search_path TO public"))
            conn.commit()
        
        # Dispose again to ensure the next connection (for create_all) is fresh
        db.engine.dispose()
        
        # Fresh creation
        db.create_all()
        db.session.commit()
    else:
        # SQLite or other
        db.drop_all()
        db.create_all()

    db.session.remove()



@pytest.fixture
def app(request):
    """Provide the Flask app instance for tests."""

    test_db_url = os.environ.get("TEST_DATABASE_URL")

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=test_db_url,
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
        RATELIMIT_ENABLED=False,
    )

    with flask_app.app_context():
        _rebuild_database_state()

        yield flask_app

        db.session.remove()


@pytest.fixture
def client(app):
    """
    Test client that creates a fresh database for each test.
    Ensures isolation between tests.
    """
    ctx = app.app_context()
    ctx.push()
    
    limiter.reset()
    
    client = flask_app.test_client()
    yield client
    
    limiter.reset()
    db.session.remove()
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


@pytest.fixture(autouse=True)
def _auto_bypass_feat(request, app):
    """
    Temporarily bypass FEAT enforcement for all tests, 
    so legacy code and fixtures can create Transactions/StudentItems.
    Tests that specifically test FEAT should be named with test_feat_enforcement
    or use a marker.
    """
    # Skip bypass for tests that explicitly test enforcement logic
    if "enforce_feat" in request.keywords or \
       "test_feat_enforcement" in request.node.name or \
       "test_feat_enforcement" in str(request.fspath):
        yield
        return
        
    from app.feats.base import FEATBypass
    with FEATBypass():
        yield


@pytest.fixture
def test_student():
    from app.hash_utils import hash_username, get_random_salt
    from app.feats.base import FEATBypass
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
    with FEATBypass():
        db.session.commit()
    return stu
