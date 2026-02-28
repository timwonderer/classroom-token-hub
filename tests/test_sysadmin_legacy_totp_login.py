import pyotp
from sqlalchemy import text

from app import db
from app.models import SystemAdmin
from app.utils.encryption import encrypt_totp, is_totp_encrypted


def test_sysadmin_login_with_plaintext_totp_reencrypts_secret(client):
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username="legacy_totp_sysadmin", totp_secret=encrypt_totp(secret))
    db.session.add(sysadmin)
    db.session.flush()
    sysadmin_id = sysadmin.id

    # Bypass validator to simulate an old plaintext row from production.
    db.session.execute(
        text("UPDATE system_admins SET totp_secret = :secret WHERE id = :id"),
        {"secret": secret, "id": sysadmin_id},
    )
    db.session.commit()

    before = db.session.get(SystemAdmin, sysadmin_id)
    assert not is_totp_encrypted(before.totp_secret)

    response = client.post(
        "/sysadmin/login",
        data={
            "username": "legacy_totp_sysadmin",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 302
    assert "/sysadmin/login" not in response.headers["Location"]

    db.session.expire(before)
    db.session.refresh(before)
    assert is_totp_encrypted(before.totp_secret)


def test_sysadmin_login_with_malformed_plaintext_totp_fails(client):
    """
    Verify that login fails for a legacy account with a malformed (non-base32)
    plaintext TOTP secret.
    """
    malformed_secret = "this-is-not-base32!"
    # Create a user first, then overwrite with malformed secret
    sysadmin = SystemAdmin(username="malformed_totp_sysadmin", totp_secret=encrypt_totp(pyotp.random_base32()))
    db.session.add(sysadmin)
    db.session.flush()
    sysadmin_id = sysadmin.id

    # Bypass validator to simulate a malformed plaintext row from production.
    db.session.execute(
        text("UPDATE system_admins SET totp_secret = :secret WHERE id = :id"),
        {"secret": malformed_secret, "id": sysadmin_id},
    )
    db.session.commit()

    before = db.session.get(SystemAdmin, sysadmin_id)
    assert not is_totp_encrypted(before.totp_secret)
    assert before.totp_secret == malformed_secret

    # Attempt to log in. The TOTP code is irrelevant as the secret is invalid.
    response = client.post(
        "/sysadmin/login",
        data={
            "username": "malformed_totp_sysadmin",
            "totp_code": "123456",
        },
    )

    # Assert login fails and redirects back to the login page.
    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]

    # Verify the malformed secret was not modified.
    db.session.refresh(before)
    assert before.totp_secret == malformed_secret
    assert not is_totp_encrypted(before.totp_secret)


def test_sysadmin_login_redirects_to_username_migration_for_legacy_username(client):
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username="legacy_username_sysadmin", totp_secret=encrypt_totp(secret))
    db.session.add(sysadmin)
    db.session.commit()

    response = client.post(
        "/sysadmin/login",
        data={
            "username": "legacy_username_sysadmin",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 302
    assert "/sysadmin/username-migration" in response.headers["Location"]
