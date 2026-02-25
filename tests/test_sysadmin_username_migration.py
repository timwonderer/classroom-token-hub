"""
Tests for sysadmin plaintext username login fallback and migration flow.

Regression: the @validates('username') validator on SystemAdmin was eagerly
backfilling username_hash/username_lookup_hash, causing needs_hashed_username_migration()
to return False and bypassing the migration screen. The plaintext username was
never cleared from the database.

PR 1024 regression: _find_sysadmin_by_auth_username was reverted to plaintext-only
lookup, breaking login for sysadmins who had already migrated to hash-based storage.
Also: legacy plaintext TOTP secrets caused login to fail because decrypt_totp raised
ValueError and the code did not fall back to treating the value as a raw secret.
"""

import binascii
import pyotp
import pytest
from sqlalchemy import text

from app import db
from app.models import SystemAdmin
from app.utils.encryption import encrypt_totp, is_totp_encrypted
from app.utils.username_migration import needs_hashed_username_migration, build_hashed_username_fields
from app.routes.system_admin import _find_sysadmin_by_auth_username


def _insert_legacy_sysadmin(username: str, totp_secret: str) -> int:
    """Insert a legacy sysadmin record directly, bypassing ORM validators."""
    admin = SystemAdmin(username=username, totp_secret=encrypt_totp(totp_secret))
    # username_hash and username_lookup_hash intentionally left NULL to simulate
    # a pre-migration record. The @validates('username') validator only normalises
    # the string and does not touch the hash fields, so this is safe.
    db.session.add(admin)
    db.session.flush()  # assigns PK without committing
    db.session.commit()
    return admin.id


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


def test_hash_lookup_finds_migrated_sysadmin(client):
    """_find_sysadmin_by_auth_username must find a fully migrated sysadmin
    (username=None, hash fields set) via the username_lookup_hash path."""
    secret = pyotp.random_base32()
    admin_id = _insert_legacy_sysadmin("hashedadmin", secret)

    # Migrate the record to hash-based storage (username cleared).
    admin = db.session.get(SystemAdmin, admin_id)
    salt, username_hash, username_lookup_hash = build_hashed_username_fields("hashedadmin")
    admin.salt = salt
    admin.username_hash = username_hash
    admin.username_lookup_hash = username_lookup_hash
    admin.username = None
    db.session.commit()

    found = _find_sysadmin_by_auth_username("hashedadmin")

    assert found is not None, (
        "migrated sysadmin with null plaintext username must be found via hash lookup"
    )
    assert found.id == admin_id
    assert found.username is None
    assert found.username_lookup_hash is not None


def _insert_plaintext_totp_sysadmin(username: str, totp_secret: str) -> int:
    """Insert a legacy sysadmin with a raw plaintext TOTP secret (pre-encryption era).

    Uses ORM flush for a portable PK, then overwrites totp_secret via raw SQL to
    bypass the @validates('totp_secret') encryption guard.
    """
    admin = SystemAdmin(username=username, totp_secret=encrypt_totp(totp_secret))
    db.session.add(admin)
    db.session.flush()
    admin_id = admin.id
    db.session.execute(
        text("UPDATE system_admins SET totp_secret = :secret WHERE id = :id"),
        {"secret": totp_secret, "id": admin_id},
    )
    db.session.commit()
    return admin_id


def test_login_with_plaintext_totp_succeeds_and_encrypts(client):
    """A sysadmin whose totp_secret was stored as plaintext (pre-encryption era)
    must still be able to log in, and the secret must be encrypted in the DB
    on first successful authentication."""
    totp_secret = pyotp.random_base32()
    admin_id = _insert_plaintext_totp_sysadmin("plaintotpadmin", totp_secret)

    # Confirm raw storage is NOT encrypted yet.
    admin = db.session.get(SystemAdmin, admin_id)
    assert not is_totp_encrypted(admin.totp_secret), (
        "test setup: totp_secret should be plaintext before login"
    )

    totp_code = pyotp.TOTP(totp_secret).now()

    resp = client.post(
        "/sysadmin/login",
        data={"username": "plaintotpadmin", "totp_code": totp_code},
    )

    # Successful login redirects away from the login page.
    assert resp.status_code == 302
    assert "/login" not in resp.headers["Location"]

    # TOTP must now be stored encrypted.
    db.session.expire(admin)
    db.session.refresh(admin)
    assert is_totp_encrypted(admin.totp_secret), (
        "totp_secret must be encrypted after first successful login"
    )
