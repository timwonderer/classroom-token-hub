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
