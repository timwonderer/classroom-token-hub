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
test_database_url = (
    dotenv_config.get("TEST_DATABASE_URL")
    or os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")  # CI sets DATABASE_URL; accept it when TEST_DATABASE_URL is absent
)
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
os.environ.setdefault("AUDIT_HMAC_KEY", "test-audit-hmac-key-for-tests-only-not-for-production")


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from app import app as flask_app, db, Student
from flask import current_app
from app.extensions import limiter
from app.models import Transaction, Seat

@event.listens_for(Transaction, "init")
def intercept_transaction_student_id(target, args, kwargs):
    """Test-only shim to intercept legacy student_id during Transaction instantiation."""
    student_id = kwargs.pop('student_id', None)
    if student_id:
        target._transient_student_id = student_id

@event.listens_for(Transaction, "before_insert")
def resolve_seat_from_transient_student(mapper, connection, target):
    """Test-only shim to resolve seat_id from legacy student_id before insert."""
    if hasattr(target, '_transient_student_id'):
        student_id = target._transient_student_id
        if getattr(target, 'seat_id', None) is None:
            class_id = getattr(target, 'class_id', None)
            join_code = getattr(target, 'join_code', None)
            
            # resolve class_id
            if not class_id and join_code:
                class_row = connection.execute(
                    sa.text("SELECT class_id FROM classes WHERE join_code = :jc LIMIT 1"),
                    {"jc": join_code}
                ).fetchone()
                if class_row:
                    class_id = class_row[0]
                    target.class_id = class_id
            
            # resolve seat_id
            if class_id:
                seat_row = connection.execute(
                    sa.text("SELECT id FROM seats WHERE student_id = :sid AND class_id = :cid LIMIT 1"),
                    {"sid": student_id, "cid": class_id}
                ).fetchone()
                if seat_row:
                    target.seat_id = seat_row[0]
            else:
                # fallback
                seat_row = connection.execute(
                    sa.text("SELECT id, class_id FROM seats WHERE student_id = :sid LIMIT 1"),
                    {"sid": student_id}
                ).fetchone()
                if seat_row:
                    target.seat_id = seat_row[0]
                    target.class_id = seat_row[1]

            if getattr(target, 'seat_id', None) is None:
                # Create a mock seat on the fly for tests that skip ClassEconomy creation
                import uuid
                from datetime import datetime, timezone
                pub_id = str(uuid.uuid4())
                cid = class_id or str(uuid.uuid4())
                target.class_id = cid
                target.join_code = join_code or "TEST_JC"
                connection.execute(
                    sa.text("""
                    INSERT INTO seats (public_id, student_id, class_id, join_code, role, has_received_rent_exemption, created_at, updated_at) 
                    VALUES (:pid, :sid, :cid, :jc, 'student', false, :now, :now)
                    """),
                    {
                        "pid": pub_id, "sid": student_id, "cid": cid, 
                        "jc": target.join_code, "now": datetime.now(timezone.utc)
                    }
                )
                seat_row = connection.execute(
                    sa.text("SELECT id FROM seats WHERE public_id = :pid"),
                    {"pid": pub_id}
                ).fetchone()
                if seat_row:
                    target.seat_id = seat_row[0]

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
        # Dispose first to release any stale pooled connections.
        db.engine.dispose()

        with db.engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.execute(text("SET search_path TO public"))
            conn.commit()

            # Create all tables/types through the same connection.
            db.Model.metadata.create_all(bind=conn)
            conn.commit()

        # Ensure subsequent tests get fresh pooled connections.
        db.engine.dispose()
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
        lock_conn = None
        lock_key_primary = 0x435448  # "CTH"
        lock_key_secondary = 0x54455354  # "TEST"
        is_postgres = "postgresql" in (test_db_url or "")

        try:
            if is_postgres:
                # Serialize full test lifecycle (rebuild + execution) across
                # concurrent pytest processes sharing one test database.
                lock_conn = db.engine.connect()
                lock_conn.execute(
                    text("SELECT pg_advisory_lock(:k1, :k2)"),
                    {"k1": lock_key_primary, "k2": lock_key_secondary},
                )
                lock_conn.commit()

            _rebuild_database_state()
            yield flask_app
        finally:
            db.session.remove()
            if lock_conn is not None:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:k1, :k2)"),
                    {"k1": lock_key_primary, "k2": lock_key_secondary},
                )
                lock_conn.commit()
                lock_conn.close()


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
