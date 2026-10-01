"""GET /sysadmin/login renders the form; it does not sign anybody out.

A page load, a prefetch, or a background request that follows a redirect to
the login page must leave whatever principal the browser holds in place. Only
a successful sign-in replaces the session's principal, and it replaces all of
it, not just ``user_id``.
"""

import pyotp

from app import db
from app.models import User
from tests.dom.operation.test_sysadmin_grafana_auth import _create_sysadmin_via_cli
from tests.helpers.classroom_initializer import initialize_as_teacher

IDENTITY_KEYS = ("user_id", "role", "current_session_nonce", "last_activity", "admin_auth_username")


def _identity(client):
    with client.session_transaction() as sess:
        return {key: sess.get(key) for key in IDENTITY_KEYS}


def test_DOM_OPS_001__sysadmin_login_get_does_not_sign_out_teacher(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    assert client.get("/admin/").status_code == 200
    before = _identity(client)

    response = client.get("/sysadmin/login")

    assert response.status_code == 200
    assert _identity(client) == before
    assert client.get("/admin/").status_code == 200


def test_DOM_OPS_001__background_fetch_of_sysadmin_login_does_not_sign_out_teacher(client, app):
    """The Grafana shape: a fetch() that followed nginx's 302 to the login page."""
    initialize_as_teacher("chemistry_p1", client, app)
    before = _identity(client)

    client.get(
        "/sysadmin/login?next=/sysadmin/grafana/api/ds/query",
        headers={"Sec-Fetch-Mode": "cors", "Accept": "application/json, text/plain, */*"},
    )

    assert _identity(client) == before
    assert client.get("/admin/").status_code == 200


def test_DOM_OPS_001__failed_sysadmin_login_does_not_sign_out_teacher(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    _create_sysadmin_via_cli("login_failure_probe")
    before = _identity(client)

    response = client.post(
        "/sysadmin/login",
        data={"username": "login_failure_probe", "totp_code": "000000"},
    )

    assert response.status_code == 302
    assert _identity(client) == before
    assert client.get("/admin/").status_code == 200


def test_DOM_OPS_001__successful_sysadmin_login_replaces_the_teacher_principal(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    sysadmin, secret = _create_sysadmin_via_cli("login_success_probe")

    response = client.post(
        "/sysadmin/login",
        data={"username": "login_success_probe", "totp_code": pyotp.TOTP(secret).now()},
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == sysadmin.id
        assert sess["role"] == "sysadmin"
        # No residue of the teacher's session survives the principal change.
        assert "admin_auth_username" not in sess
        assert "login_time" not in sess
        assert "class_id" not in sess
        assert sess["current_session_nonce"] == db.session.get(User, sysadmin.id).current_session_nonce
    assert client.get("/admin/").status_code == 302
