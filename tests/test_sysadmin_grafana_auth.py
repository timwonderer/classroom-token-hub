from datetime import timedelta

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp

from app import db
from app.auth import SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES
from app.models import SystemAdmin, User, UserRole
from app.utils.encryption import encrypt_totp
from app.utils.time import utc_now


def _create_sysadmin(username: str = "grafana_sysadmin"):
    secret = pyotp.random_base32()
    sysadmin = make_sysadmin(username, encrypt_totp(secret))
    user = User(
        user_role=UserRole.SYSADMIN,
        username_hash=sysadmin.username_hash,
        username_lookup_hash=sysadmin.username_lookup_hash,
        totp_secret_encrypted=sysadmin.totp_secret,
    )
    db.session.add_all([sysadmin, user])
    db.session.commit()
    return sysadmin, user, secret


def _login_sysadmin_session(client, sysadmin_id: int, *, user_id: int, username: str = "grafana_sysadmin", minutes_ago: int = 0):
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin_id
        sess["user_id"] = user_id
        sess["sysadmin_auth_username"] = username
        sess["last_activity"] = (utc_now() - timedelta(minutes=minutes_ago)).isoformat()


def test_sysadmin_login_get_requests_do_not_trip_rate_limit(client):
    for _ in range(12):
        response = client.get("/sysadmin/login")
        assert response.status_code == 200


def test_grafana_auth_check_uses_longer_sysadmin_timeout(client):
    sysadmin, user, _ = _create_sysadmin("grafana_timeout")
    _login_sysadmin_session(
        client,
        sysadmin.id,
        user_id=user.id,
        username="grafana_timeout",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES - 5,
    )

    response = client.get("/sysadmin/grafana/auth-check")

    assert response.status_code == 200
    assert response.headers["X-Auth-User"] == "grafana_timeout"


def test_expired_grafana_subrequest_returns_401_instead_of_login_redirect(client):
    sysadmin, user, _ = _create_sysadmin("grafana_expired")
    _login_sysadmin_session(
        client,
        sysadmin.id,
        user_id=user.id,
        username="grafana_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = client.get("/sysadmin/grafana/public/build/app.js")

    assert response.status_code == 401
    assert "/sysadmin/login" not in (response.headers.get("Location") or "")


def test_expired_sysadmin_dashboard_still_redirects_to_login(client):
    sysadmin, user, _ = _create_sysadmin("dashboard_expired")
    _login_sysadmin_session(
        client,
        sysadmin.id,
        user_id=user.id,
        username="dashboard_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = client.get("/sysadmin/dashboard")

    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]


def test_sysadmin_dashboard_accepts_legacy_naive_last_activity_timestamp(client):
    sysadmin, user, _ = _create_sysadmin("dashboard_naive")
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["user_id"] = user.id
        sess["sysadmin_auth_username"] = "dashboard_naive"
        sess["last_activity"] = (utc_now() - timedelta(minutes=5)).replace(tzinfo=None).isoformat()

    response = client.get("/sysadmin/dashboard")

    assert response.status_code == 200


def test_sysadmin_auth_check_rejects_mismatched_shadow_session(client):
    sysadmin, user, _ = _create_sysadmin("auth_check_mismatch")
    other = make_sysadmin("auth_check_other", encrypt_totp(pyotp.random_base32()))
    db.session.add(other)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = other.id
        sess["user_id"] = user.id
        sess["last_activity"] = utc_now().isoformat()

    response = client.get("/sysadmin/auth-check")

    assert response.status_code == 401


def test_grafana_auth_check_rejects_missing_canonical_user(client):
    sysadmin, _, _ = _create_sysadmin("grafana_missing_user")
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["last_activity"] = utc_now().isoformat()

    response = client.get("/sysadmin/grafana/auth-check")

    assert response.status_code == 401
