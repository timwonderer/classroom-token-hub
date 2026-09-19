"""Recovery-session schema migration on an existing User table."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_recovery_session_migration_preserves_existing_user(tmp_path):
    path = Path(__file__).resolve().parents[3] / "migrations/versions/f4d4e5f6a7b8_student_recovery_session.py"
    spec = importlib.util.spec_from_file_location("recovery_session_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username_hash VARCHAR(64) NOT NULL)"))
            connection.execute(text("INSERT INTO users VALUES (1, 'existing-user')"))
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            columns = {c["name"] for c in inspect(connection).get_columns("users")}
            assert {"recovery_setup_nonce_hash", "recovery_setup_expires_at"} <= columns
            assert connection.execute(text("SELECT recovery_setup_nonce_hash FROM users WHERE id=1")).scalar() is None
            migration.upgrade()  # Fresh-bootstrap metadata already has these columns.
            migration.downgrade()
            assert {c["name"] for c in inspect(connection).get_columns("users")} == {"id", "username_hash"}
            assert connection.execute(text("SELECT username_hash FROM users WHERE id=1")).scalar() == "existing-user"
    finally:
        engine.dispose()
