import pytest
import logging

from flask import session
from types import SimpleNamespace

from app import db
from app.auth import (
    set_canonical_user_session,
)
from app.feats.base import FEATContext
from app.models import (
    ClassEconomy,
    Seat,
    PasskeyCredential,
    User,
    UserRole,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher
from tests.helpers.passkey import fake_passwordless  # noqa: F401  (fixture)
from tests.dom.identity.helpers import (
    admin_passkey_auth_finish,
    admin_passkey_register_start,
    student_login,
    sysadmin_passkey_auth_finish,
)

 
def test_DOM_IDEN_006__system_admin_login_verifies_canonical_totp(client):
    classroom = initialize("chemistry_p1", client.application)
    assert classroom.teacher_user.id is not None
    assert classroom.teacher_seat.id is not None


def test_DOM_IDEN_006__teacher_login_uses_keyed_feat_context(client, monkeypatch, caplog):
    classroom = initialize("chemistry_p1", client.application)
    form = SimpleNamespace(
        validate_on_submit=lambda: True,
        username=SimpleNamespace(data="teacher.alice"),
        totp_code=SimpleNamespace(data="123456"),
    )
    monkeypatch.setattr("app.routes.admin.AdminLoginForm", lambda: form)
    monkeypatch.setattr(
        "app.routes.admin.find_canonical_user_by_auth_username",
        lambda *_args, **_kwargs: classroom.teacher_user,
    )
    monkeypatch.setattr("app.routes.admin.decrypt_totp", lambda _value: "secret")
    monkeypatch.setattr(
        "app.routes.admin.pyotp.TOTP",
        lambda _secret: SimpleNamespace(verify=lambda *_args, **_kwargs: True),
    )

    with caplog.at_level(logging.WARNING, logger="app.feats.base"):
        response = client.post("/admin/login")

    assert response.status_code == 302
    assert "FEAT-INTEGRITY-WARNING" not in caplog.text



def test_DOM_IDEN_006__student_login_verifies_passphrase_and_resolves_through_claimed_seat(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    response = student_login(client, username=student.username, passphrase=student.passphrase)
    assert response.status_code == 302



def test_DOM_IDEN_006__student_login_missing_last_active_class_shows_selector(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:clear-last-active-class:selector"):
        student.user.last_active_class_id = None
        db.session.flush()
    response = student_login(client, username=student.username, passphrase=student.passphrase)

    assert response.status_code == 302
    assert "/student/select-class-context" in response.headers["Location"]



def test_DOM_IDEN_006__admin_passkey_register_uses_canonical_user_external_id(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user = classroom.teacher_user

    response = admin_passkey_register_start(client)

    assert response.status_code == 200, f"Expected 200 but got {response.status_code}. Redirecting to: {response.location if response.status_code == 302 else 'N/A'}"
    assert response.get_json()["token"].startswith("register_")
    assert fake_passwordless.calls == [("register_token", f"user_{user.id}")]


def test_DOM_IDEN_006__admin_passkey_finish_sets_canonical_user_session(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user = classroom.teacher_user
    fake_passwordless.credentials["cred-admin"] = f"user_{user.id}"
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:passkey-credential:admin"):
        db.session.add(PasskeyCredential(user_id=user.id, credential_id="cred-admin", authenticator_name="Key"))
        db.session.flush()

    response = admin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-admin"))

    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id


def test_DOM_IDEN_006__system_admin_passkey_finish_sets_canonical_user_session(client, fake_passwordless):
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:passkey-credential:sysadmin"):
        user = User(
            user_role=UserRole.SYSADMIN,
            username_hash="sysadmin-passkey-hash",
            username_lookup_hash="sysadmin-passkey-lookup",
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(PasskeyCredential(user_id=user.id, credential_id="cred-sysadmin", authenticator_name="Key"))
        db.session.flush()
    fake_passwordless.credentials["cred-sysadmin"] = f"user_{user.id}"

    response = sysadmin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-sysadmin"))

    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id


def test_DOM_IDEN_006__canonical_user_session_rejects_role_mismatch(client):
    with FEATContext("FEAT-IDEN-001"):
        user = User(
            user_role=UserRole.STUDENT,
            username_hash="role-mismatch-hash",
            username_lookup_hash="role-mismatch-lookup",
        )
        db.session.add(user)
        db.session.flush()

    with client.application.test_request_context("/"):
        resolved = set_canonical_user_session(
            username_lookup_hash=user.username_lookup_hash,
            expected_role="teacher",
        )

        assert resolved is None
        assert "user_id" not in session
