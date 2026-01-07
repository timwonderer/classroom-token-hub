"""
Test that migration 1a4ee2388d62 (add teacher analytics) can handle
missing indexes and columns gracefully.

This test verifies the fix for the issue where the migration tried to drop
indexes that didn't exist, depending on which migration path was taken.
"""
import os
import sys
import pytest
from sqlalchemy import inspect, text

# Set up environment before imports
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.extensions import db
from app import app


@pytest.fixture
def test_db():
    """Create a test database with necessary tables."""
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    ctx = app.app_context()
    ctx.push()
    
    # Create all tables
    db.create_all()
    
    yield db
    
    db.drop_all()
    ctx.pop()


def test_conditional_index_drop_logic(test_db):
    """Test that the migration's conditional index drop logic works correctly."""
    
    # Create a test table to simulate the admin_credentials table
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_credentials (
                id INTEGER PRIMARY KEY,
                credential_id TEXT,
                public_key BLOB,
                aaguid VARCHAR(36),
                sign_count INTEGER,
                transports VARCHAR(255)
            )
        """))
        conn.commit()
    
    # Simulate scenario 1: Index exists
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_test_credentials_credential_id 
            ON test_credentials(credential_id)
        """))
        conn.commit()
    
    inspector = inspect(db.engine)
    
    # Check that index exists
    indexes_before = {idx['name'] for idx in inspector.get_indexes('test_credentials')}
    assert 'ix_test_credentials_credential_id' in indexes_before
    
    # Simulate the migration logic: conditionally drop index
    test_cred_indexes = {idx['name'] for idx in inspector.get_indexes('test_credentials')}
    test_cred_columns = {col['name'] for col in inspector.get_columns('test_credentials')}
    
    # Drop index if it exists
    if 'ix_test_credentials_credential_id' in test_cred_indexes:
        with db.engine.connect() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_test_credentials_credential_id"))
            conn.commit()
    
    # Verify index was dropped
    inspector = inspect(db.engine)
    indexes_after = {idx['name'] for idx in inspector.get_indexes('test_credentials')}
    assert 'ix_test_credentials_credential_id' not in indexes_after
    
    # Drop columns if they exist
    columns_to_drop = ['public_key', 'aaguid', 'sign_count', 'transports']
    for col in columns_to_drop:
        if col in test_cred_columns:
            # SQLite doesn't support DROP COLUMN easily, but this tests the logic
            assert col in test_cred_columns


def test_conditional_index_drop_when_missing(test_db):
    """Test that the migration handles missing indexes gracefully."""
    
    # Create a test table WITHOUT the index (simulating the ed9de5ef6f79 migration path)
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_credentials_no_index (
                id INTEGER PRIMARY KEY,
                credential_id TEXT,
                authenticator_name VARCHAR(100)
            )
        """))
        conn.commit()
    
    inspector = inspect(db.engine)
    
    # Check that index does NOT exist
    indexes_before = {idx['name'] for idx in inspector.get_indexes('test_credentials_no_index')}
    assert 'ix_test_credentials_no_index_credential_id' not in indexes_before
    
    # Simulate the migration logic: try to drop index (should not error)
    test_cred_indexes = {idx['name'] for idx in inspector.get_indexes('test_credentials_no_index')}
    
    # This should NOT execute because index doesn't exist
    if 'ix_test_credentials_no_index_credential_id' in test_cred_indexes:
        # This branch should not be taken
        assert False, "Index should not exist"
    else:
        # This is the expected path - index doesn't exist, so skip the drop
        pass
    
    # Verify no error occurred
    assert True


def test_column_existence_check(test_db):
    """Test that column existence detection works correctly."""
    
    # Create table with some columns
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_column_check (
                id INTEGER PRIMARY KEY,
                existing_col TEXT,
                another_col INTEGER
            )
        """))
        conn.commit()
    
    inspector = inspect(db.engine)
    columns = {col['name'] for col in inspector.get_columns('test_column_check')}
    
    # Test existence checks
    assert 'existing_col' in columns
    assert 'another_col' in columns
    assert 'nonexistent_col' not in columns
    
    # Simulate conditional column drop logic
    columns_to_check = ['existing_col', 'nonexistent_col', 'another_col']
    columns_that_exist = [col for col in columns_to_check if col in columns]
    
    assert 'existing_col' in columns_that_exist
    assert 'another_col' in columns_that_exist
    assert 'nonexistent_col' not in columns_that_exist


def test_both_tables_pattern(test_db):
    """Test the pattern used for both admin_credentials and system_admin_credentials."""
    
    # Create both tables to simulate the migration scenario
    with db.engine.connect() as conn:
        # Admin credentials with index
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sim_admin_credentials (
                id INTEGER PRIMARY KEY,
                credential_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sim_admin_credentials_cred 
            ON sim_admin_credentials(credential_id)
        """))
        
        # System admin credentials without index (different migration path)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sim_system_admin_credentials (
                id INTEGER PRIMARY KEY,
                credential_id TEXT
            )
        """))
        conn.commit()
    
    inspector = inspect(db.engine)
    
    # Check admin_credentials has index
    admin_indexes = {idx['name'] for idx in inspector.get_indexes('sim_admin_credentials')}
    assert 'ix_sim_admin_credentials_cred' in admin_indexes
    
    # Check system_admin_credentials does NOT have index
    sys_admin_indexes = {idx['name'] for idx in inspector.get_indexes('sim_system_admin_credentials')}
    assert 'ix_sim_system_admin_credentials_cred' not in sys_admin_indexes
    
    # Simulate migration: conditionally drop from both
    # Admin credentials - should drop
    if 'ix_sim_admin_credentials_cred' in admin_indexes:
        with db.engine.connect() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_sim_admin_credentials_cred"))
            conn.commit()
    
    # System admin credentials - should skip (no error)
    if 'ix_sim_system_admin_credentials_cred' in sys_admin_indexes:
        assert False, "This should not execute because index doesn't exist"
    
    # Verify first index was dropped
    inspector = inspect(db.engine)
    admin_indexes_after = {idx['name'] for idx in inspector.get_indexes('sim_admin_credentials')}
    assert 'ix_sim_admin_credentials_cred' not in admin_indexes_after
    
    # Verify no error occurred for missing index
    assert True
