"""Request trace migration clears detached records and preserves live ownership."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text


def _migration(connection):
    path = Path(__file__).resolve().parents[3] / "migrations/versions/a5e5f6a7b8c9_request_trace_deletion_closure.py"
    spec = importlib.util.spec_from_file_location("trace_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


@pytest.fixture
def old_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'trace.db'}")
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE classes (class_id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE seats (public_id VARCHAR(36) PRIMARY KEY, class_id VARCHAR(36), role VARCHAR(20))"))
        connection.execute(text("""CREATE TABLE actor_request_trace (
            id INTEGER PRIMARY KEY, actor_public_id VARCHAR(64) NOT NULL, class_id VARCHAR(36), actor_type VARCHAR(20),
            CONSTRAINT fk_actor_request_trace_class_id_classes FOREIGN KEY(class_id) REFERENCES classes(class_id) ON DELETE SET NULL
        )"""))
        connection.execute(text("INSERT INTO classes VALUES ('a'), ('b')"))
        connection.execute(text("INSERT INTO seats VALUES ('seat-a', 'a', 'student'), ('seat-b', 'b', 'teacher')"))
    yield engine
    engine.dispose()


def test_trace_migration_removes_detached_rows_and_installs_cascades(old_database):
    with old_database.begin() as connection:
        connection.execute(text("""INSERT INTO actor_request_trace VALUES
            (1,'seat-a','a','student'), (2,'seat-b','b','teacher'),
            (3,'removed-seat',NULL,'student'), (4,'removed-seat','a','student')"""))
        migration = _migration(connection)
        migration.upgrade()
        assert connection.execute(text("SELECT id FROM actor_request_trace ORDER BY id")).scalars().all() == [1, 2]
        assert all(fk["options"]["ondelete"] == "CASCADE" for fk in inspect(connection).get_foreign_keys("actor_request_trace"))
        connection.execute(text("DELETE FROM seats WHERE public_id='seat-a'"))
        assert connection.execute(text("SELECT id FROM actor_request_trace")).scalars().all() == [2]
        connection.execute(text("DELETE FROM classes WHERE class_id='b'"))
        assert connection.execute(text("SELECT COUNT(*) FROM actor_request_trace")).scalar() == 0
        migration.downgrade()
        assert len(inspect(connection).get_foreign_keys("actor_request_trace")) == 1


def test_trace_migration_rejects_mismatched_live_scope(old_database):
    with old_database.begin() as connection:
        connection.execute(text("INSERT INTO actor_request_trace VALUES (1,'seat-a','b','student')"))
        with pytest.raises(RuntimeError, match="mismatched live"):
            _migration(connection).upgrade()
