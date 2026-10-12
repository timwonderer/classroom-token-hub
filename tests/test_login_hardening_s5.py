"""Teacher and sysadmin login hardening (audit S5).

Before this change: the sysadmin login made no server-side Turnstile call
even though the widget already rendered on its page, neither login route
budgeted attempts per *account* (only per IP), and a correct TOTP code
could be submitted more than once within ``valid_window=1``'s ~90-second
drift tolerance. DOM-IDEN-003 SS VII prescribes TOTP-or-passkey login; this
is hardening within that design, not a change to it.
"""

from __future__ import annotations

import uuid

import pyotp

from app import db
from app.extensions import limiter
from app.feats.base import FEATContext
from app.models import User, UserRole
from app.utils.auth_username import build_hashed_username_fields
from app.utils.encryption import encrypt_totp


def _create_teacher(username: str) -> tuple[User, str]:
    totp_secret = pyotp.random_base32()
    _, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"test-s5:{uuid.uuid4().hex}"):
        user = User(
            user_role=UserRole.TEACHER,
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            totp_secret_encrypted=encrypt_totp(totp_secret),
        )
        db.session.add(user)
        db.session.flush()
    db.session.commit()
    return user, totp_secret


def _create_sysadmin(username: str) -> tuple[User, str]:
    totp_secret = pyotp.random_base32()
    _, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"test-s5-sysadmin:{uuid.uuid4().hex}"):
        user = User(
            user_role=UserRole.SYSADMIN,
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            totp_secret_encrypted=encrypt_totp(totp_secret),
        )
        db.session.add(user)
        db.session.flush()
    db.session.commit()
    return user, totp_secret


def test_sysadmin_login_blocked_without_turnstile(client, monkeypatch):
    """The sysadmin login must call verify_turnstile_token, mirroring the
    teacher login's existing ingress gate. Before this change it never did.
    """
    _create_sysadmin("s5_sysadmin_turnstile")

    monkeypatch.setattr("app.routes.system_admin.verify_turnstile_token", lambda *a, **k: False)
    response = client.post(
        "/sysadmin/login",
        data={"username": "s5_sysadmin_turnstile", "totp_code": "123456"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_sysadmin_login_still_works_once_turnstile_passes(client, monkeypatch):
    sysadmin, secret = _create_sysadmin("s5_sysadmin_turnstile_ok")
    monkeypatch.setattr("app.routes.system_admin.verify_turnstile_token", lambda *a, **k: True)

    response = client.post(
        "/sysadmin/login",
        data={"username": "s5_sysadmin_turnstile_ok", "totp_code": pyotp.TOTP(secret).now()},
    )
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == sysadmin.id


def test_admin_login_account_lockout_outlasts_a_shared_ip_budget(client, app):
    """A per-account attempt budget exists independent of the per-IP one:
    repeated wrong-TOTP attempts against one teacher account are refused
    before the per-IP ``10 per minute`` limit would ever be reached.
    """
    _create_teacher("s5_admin_lockout")
    app.config["RATELIMIT_ENABLED"] = True
    try:
        response = None
        for _ in range(6):
            response = client.post(
                "/admin/login",
                data={"username": "s5_admin_lockout", "totp_code": "000000"},
            )
        assert response.status_code == 429
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()


def test_sysadmin_login_account_lockout_outlasts_a_shared_ip_budget(client, app):
    _create_sysadmin("s5_sysadmin_lockout")
    app.config["RATELIMIT_ENABLED"] = True
    try:
        response = None
        for _ in range(6):
            response = client.post(
                "/sysadmin/login",
                data={"username": "s5_sysadmin_lockout", "totp_code": "000000"},
            )
        assert response.status_code == 429
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()


def test_admin_login_account_lockout_is_scoped_per_account(client, app):
    """A second, distinct account is not swept up by the first account's
    lockout -- the key is per-account, not per-IP or global.
    """
    _create_teacher("s5_admin_lockout_a")
    other, secret = _create_teacher("s5_admin_lockout_b")
    app.config["RATELIMIT_ENABLED"] = True
    try:
        for _ in range(6):
            client.post(
                "/admin/login",
                data={"username": "s5_admin_lockout_a", "totp_code": "000000"},
            )
        response = client.post(
            "/admin/login",
            data={"username": "s5_admin_lockout_b", "totp_code": pyotp.TOTP(secret).now()},
        )
        assert response.status_code == 302
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()


def test_admin_login_totp_code_cannot_be_replayed(client, app):
    """A valid code is good for ``valid_window=1`` (~90s of drift), so
    without this guard the exact same captured code could sign in twice.
    The first submission of a code succeeds; resubmitting that same code
    is refused even though pyotp would still accept it.
    """
    teacher, secret = _create_teacher("s5_admin_replay")
    app.config["RATELIMIT_ENABLED"] = True
    try:
        code = pyotp.TOTP(secret).now()
        first = client.post("/admin/login", data={"username": "s5_admin_replay", "totp_code": code})
        assert first.status_code == 302
        with client.session_transaction() as sess:
            sess.clear()

        replay = client.post("/admin/login", data={"username": "s5_admin_replay", "totp_code": code})
        assert replay.status_code == 429
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()


def test_admin_login_a_fresh_code_after_a_typo_is_not_blocked(client, app):
    """Replay protection is keyed on the exact code value, so correcting a
    typo with a *different* code is not caught by it."""
    teacher, secret = _create_teacher("s5_admin_retry")
    app.config["RATELIMIT_ENABLED"] = True
    try:
        wrong = client.post("/admin/login", data={"username": "s5_admin_retry", "totp_code": "111111"})
        assert wrong.status_code == 302  # redirects back to the login form

        right = client.post(
            "/admin/login",
            data={"username": "s5_admin_retry", "totp_code": pyotp.TOTP(secret).now()},
        )
        assert right.status_code == 302
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()
