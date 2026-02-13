import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Override env vars for testing
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
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
from app import app as flask_app, db, Student


@pytest.fixture
def app():
    """Provide the Flask app instance for tests."""
    # Use a separate test database to avoid clashing with dev data
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/classroom_economy_test"
    )

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=test_db_url,
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    
    # Ensure strict separation - if connection fails, test fails
    with flask_app.app_context():
        
        db.drop_all() 
        db.create_all()
        pass

    yield flask_app


@pytest.fixture
def client(app):
    """
    Test client that creates a fresh database for each test.
    Ensures isolation between tests.
    """
    ctx = app.app_context()
    ctx.push()
    
    # Create all tables for the test
    db.create_all()
    
    client = flask_app.test_client()
    yield client
    
    # Teardown: Drop all tables after test
    db.session.remove()
    db.drop_all()
    ctx.pop()


@pytest.fixture
def client_with_fk(client):
    """
    Enable foreign key enforcement for tests that rely on CASCADE behavior.
    SQLite requires PRAGMA foreign_keys=ON per connection; PostgreSQL enforces by default.
    """
    from sqlalchemy import event

    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        @event.listens_for(db.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Also enable on the current connection
        from sqlalchemy import text
        db.session.execute(text("PRAGMA foreign_keys=ON"))

    yield client


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

