"""
Tests for sysadmin plaintext username login fallback and migration flow.

Regression: the @validates('username') validator on SystemAdmin was eagerly
backfilling username_hash/username_lookup_hash, causing needs_hashed_username_migration()
to return False and bypassing the migration screen. The plaintext username was
never cleared from the database.
"""

import pyotp
import pytest
from sqlalchemy import text

from app import db
from app.models import SystemAdmin
from app.utils.encryption import encrypt_totp
from app.utils.username_migration import needs_hashed_username_migration
from app.routes.system_admin import _find_sysadmin_by_auth_username


def _insert_legacy_sysadmin(username: str, totp_secret: str) -> int:
    """Insert a legacy sysadmin record directly, bypassing ORM validators."""
    encrypted = encrypt_totp(totp_secret)
    result = db.session.execute(
        text(
            "INSERT INTO system_admins "
            "(username, username_hash, username_lookup_hash, salt, totp_secret) "
            "VALUES (:username, NULL, NULL, NULL, :secret)"
        ),
        {"username": username, "secret": encrypted},
    )
    db.session.commit()
    return result.lastrowid


def test_sysadmin_validator_does_not_backfill_hash_fields(client):
    """Creating a SystemAdmin with a plaintext username must NOT auto-populate
    hash fields — that would bypass the migration screen."""
    secret = pyotp.random_base32()
    admin = SystemAdmin(username="testadmin", totp_secret=encrypt_totp(secret))
    db.session.add(admin)
    db.session.commit()

    assert admin.username == "testadmin"
    assert admin.username_hash is None, (
        "validator must not backfill username_hash; migration path must set it"
    )
    assert admin.username_lookup_hash is None, (
        "validator must not backfill username_lookup_hash; migration path must set it"
    )
    assert needs_hashed_username_migration(admin) is True


def test_plaintext_fallback_finds_legacy_sysadmin(client):
    """_find_sysadmin_by_auth_username must locate a legacy sysadmin whose
    record has null hash fields (plaintext fallback path)."""
    secret = pyotp.random_base32()
    _insert_legacy_sysadmin("legacyadmin", secret)

    admin = _find_sysadmin_by_auth_username("legacyadmin")

    assert admin is not None, (
        "legacy sysadmin with null hash fields must be found via plaintext fallback"
    )
    assert admin.username == "legacyadmin"
    assert admin.username_hash is None
    assert needs_hashed_username_migration(admin) is True


def test_legacy_sysadmin_completes_migration_via_route(client):
    """The migration route sets hash fields and clears the plaintext username."""
    secret = pyotp.random_base32()
    admin_id = _insert_legacy_sysadmin("migrationuser", secret)

    # Simulate an already-authenticated sysadmin session (skips the login rate limit)
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = admin_id
        sess["sysadmin_auth_username"] = "migrationuser"
        sess["force_sysadmin_username_migration"] = True
        from app.utils.time import utc_now
        sess["last_activity"] = utc_now().isoformat()

    resp = client.post("/sysadmin/username-migration", data={"action": "continue"})
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]

    admin = db.session.get(SystemAdmin, admin_id)
    db.session.expire(admin)
    db.session.refresh(admin)

    assert admin.username is None, "plaintext username must be cleared after migration"
    assert admin.username_hash is not None, "username_hash must be set after migration"
    assert admin.username_lookup_hash is not None, "username_lookup_hash must be set"


def test_migrated_sysadmin_no_longer_needs_migration(client):
    """After migration is complete (username=None, hash fields set), the
    needs_hashed_username_migration check must return False."""
    secret = pyotp.random_base32()
    admin_id = _insert_legacy_sysadmin("postmigrate", secret)

    from app.utils.username_migration import build_hashed_username_fields
    admin = db.session.get(SystemAdmin, admin_id)
    salt, username_hash, username_lookup_hash = build_hashed_username_fields("postmigrate")
    admin.salt = salt
    admin.username_hash = username_hash
    admin.username_lookup_hash = username_lookup_hash
    admin.username = None
    db.session.commit()

    db.session.expire(admin)
    db.session.refresh(admin)

    assert needs_hashed_username_migration(admin) is False, (
        "after migration, needs_hashed_username_migration must return False"
    )
