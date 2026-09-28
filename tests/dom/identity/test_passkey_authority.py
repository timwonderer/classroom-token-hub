"""A passkey signs in only the principal it is recorded for (DOM-IDEN-003).

Until 2026-09-28 sign-in trusted the ``user_<id>`` that passwordless.dev
returned and checked only the role. users.id restarted at 1 at the launch
wipe, and passwordless.dev still held pre-launch passkeys, so a passkey
registered as ``user_3`` before the wipe signed in whoever is user 3 now.
Registration never verified its token, recorded no credential id, and removal
left the credential working on passwordless.dev.

These tests run against an in-memory passwordless.dev (tests/helpers/passkey.py).
"""

from __future__ import annotations

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, PasskeyCredential, User, UserRole
from tests.dom.identity.helpers import (
    admin_delete_class,
    admin_passkey_auth_finish,
    admin_passkey_register_start,
    sysadmin_passkey_auth_finish,
    valid_destruction_gate,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.passkey import fake_passwordless  # noqa: F401  (fixture)


def _record_passkey(user_id, credential_id, key):
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"test:passkey:{key}"):
        db.session.add(PasskeyCredential(user_id=user_id, credential_id=credential_id, authenticator_name=key))
        db.session.flush()


def _register_finish(client, token):
    return client.post("/admin/passkey/register/finish", json={"token": token, "authenticatorName": "Key"})


def _signed_in_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def _logged_out(client):
    with client.session_transaction() as sess:
        sess.clear()


def _class_delete_phrase(class_id):
    row = db.session.get(ClassEconomy, class_id)
    return f"DELETE {(row.display_name or '').strip() or row.join_code}".upper()


# ---- registration ----------------------------------------------------------

def test_registration_records_the_credential_the_token_names(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id

    response = _register_finish(client, fake_passwordless.complete_registration(user_id))

    assert response.status_code == 200
    rows = PasskeyCredential.query.filter_by(user_id=user_id).all()
    assert [r.credential_id for r in rows] == list(fake_passwordless.credentials)


def test_registration_refuses_a_token_for_another_principal(client, fake_passwordless):
    other = initialize("ap_csp_p3", client.application)
    other_user = User.query.filter(User.id != other.teacher_user.id).first()
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    assert other_user.id != classroom.teacher_user.id

    response = _register_finish(client, fake_passwordless.complete_registration(other_user.id))

    assert response.status_code == 400
    assert PasskeyCredential.query.count() == 0


def test_registration_refuses_a_sign_in_token(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    fake_passwordless.credentials["cred-x"] = f"user_{classroom.teacher_user.id}"

    response = _register_finish(client, fake_passwordless.sign_in_token("cred-x"))

    assert response.status_code == 400
    assert PasskeyCredential.query.count() == 0


def test_registration_refuses_a_token_it_cannot_verify(client, fake_passwordless):
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = _register_finish(client, "made-up-token")

    assert response.status_code in (400, 500)
    assert PasskeyCredential.query.count() == 0


def test_an_alias_held_by_an_old_registration_is_a_clear_409(client, fake_passwordless):
    initialize_as_teacher("chemistry_p1", client, client.application)
    # Bind every alias this teacher could use to a pre-launch external id.
    fake_passwordless.aliases = _AnyAliasOwnedBy("user_3")

    response = admin_passkey_register_start(client)

    assert response.status_code == 409
    assert "old passkey registration" in response.get_json()["error"]


class _AnyAliasOwnedBy(dict):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def get(self, key, default=None):
        return self._owner


# ---- sign-in ---------------------------------------------------------------

def test_a_pre_launch_passkey_signs_in_no_one(client, fake_passwordless):
    """The reported hole: "user_3" is not a UUID and names nobody now."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    _logged_out(client)
    fake_passwordless.credentials["cred-prelaunch"] = "user_3"

    response = admin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-prelaunch"))

    assert response.status_code == 401
    assert _signed_in_user_id(client) is None
    assert classroom.teacher_user.id


def test_a_credential_not_recorded_for_the_principal_signs_in_no_one(client, fake_passwordless):
    """Even naming a real teacher, a credential we never recorded for them fails."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    _record_passkey(user_id, "cred-recorded", "recorded")
    _logged_out(client)

    token = fake_passwordless.token_for(f"user_{user_id}", "cred-unrecorded")
    response = admin_passkey_auth_finish(client, token=token)

    assert response.status_code == 401
    assert _signed_in_user_id(client) is None


def test_a_recorded_credential_signs_in_its_principal(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    _record_passkey(user_id, "cred-good", "good")
    fake_passwordless.credentials["cred-good"] = f"user_{user_id}"
    _logged_out(client)

    response = admin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-good"))

    assert response.status_code == 200
    assert _signed_in_user_id(client) == user_id
    assert PasskeyCredential.query.filter_by(credential_id="cred-good").one().last_used is not None


def test_only_a_passkey_sign_in_token_signs_in(client, fake_passwordless):
    """A magic-link or registration token for the same credential is refused."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    _record_passkey(user_id, "cred-typed", "typed")
    fake_passwordless.credentials["cred-typed"] = f"user_{user_id}"
    _logged_out(client)

    for type_ in ("magic_link", "generated_signin", "passkey_register"):
        token = fake_passwordless.sign_in_token("cred-typed", type_=type_)
        assert admin_passkey_auth_finish(client, token=token).status_code == 401
    assert _signed_in_user_id(client) is None


def test_a_username_started_sign_in_accepts_only_that_user(client, fake_passwordless, monkeypatch):
    """Sign-in that began from teacher A's username cannot finish as teacher B."""
    a = initialize("chemistry_p1", client.application)
    b_user = User(user_role=UserRole.TEACHER, username_hash="teacher-b-hash", username_lookup_hash="teacher-b")
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:passkey:teacher-b"):
        db.session.add(b_user)
        db.session.flush()
    _record_passkey(a.teacher_user.id, "cred-a", "a")
    _record_passkey(b_user.id, "cred-b", "b")
    fake_passwordless.credentials.update({"cred-a": f"user_{a.teacher_user.id}", "cred-b": f"user_{b_user.id}"})
    monkeypatch.setattr(
        "app.routes.admin.find_canonical_user_by_auth_username",
        lambda *_a, **_k: db.session.get(User, a.teacher_user.id),
    )

    assert client.post("/admin/passkey/auth/start", json={"username": "teacher.a"}).status_code == 200
    response = admin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-b"))

    assert response.status_code == 401
    assert _signed_in_user_id(client) is None


def test_a_teacher_passkey_cannot_sign_in_as_sysadmin(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    _record_passkey(user_id, "cred-teacher", "teacher")
    fake_passwordless.credentials["cred-teacher"] = f"user_{user_id}"
    _logged_out(client)

    response = sysadmin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-teacher"))

    assert response.status_code == 401
    assert _signed_in_user_id(client) is None


# ---- removal ---------------------------------------------------------------

def test_removing_a_passkey_deletes_it_on_passwordless_first(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    _register_finish(client, fake_passwordless.complete_registration(classroom.teacher_user.id))
    row = PasskeyCredential.query.one()
    row_id, credential_id = row.id, row.credential_id

    response = client.delete(f"/admin/passkey/{row_id}/delete")

    assert response.status_code == 200
    assert ("delete_credential", credential_id) in fake_passwordless.calls
    assert credential_id not in fake_passwordless.credentials
    db.session.expire_all()
    assert PasskeyCredential.query.count() == 0


def test_a_failed_remote_removal_keeps_the_local_record(client, fake_passwordless):
    """Nothing local changes when passwordless.dev did not delete the credential."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    _register_finish(client, fake_passwordless.complete_registration(classroom.teacher_user.id))
    row = PasskeyCredential.query.one()
    fake_passwordless.fail_deletes = True

    response = client.delete(f"/admin/passkey/{row.id}/delete")

    assert response.status_code == 503
    db.session.expire_all()
    assert PasskeyCredential.query.count() == 1


# ---- account destruction ---------------------------------------------------

def test_destroying_an_account_deletes_its_passwordless_user(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    _register_finish(client, fake_passwordless.complete_registration(user_id))
    fake_passwordless.aliases["teacher.alice"] = f"user_{user_id}"

    response = admin_delete_class(client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id)))

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json().get("account_deleted") is True
    assert ("delete_user", f"user_{user_id}") in fake_passwordless.calls
    assert not fake_passwordless.credentials and not fake_passwordless.aliases
    db.session.expire_all()
    assert db.session.get(User, user_id) is None


def test_a_failed_remote_deletion_destroys_nothing(client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    user_id = classroom.teacher_user.id
    fake_passwordless.fail_deletes = True

    response = admin_delete_class(client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id)))

    assert response.status_code >= 400
    db.session.expire_all()
    assert db.session.get(User, user_id) is not None
    assert db.session.get(ClassEconomy, classroom.class_id) is not None


# ---- sessions from before the UUID change ----------------------------------

def test_a_session_holding_an_integer_user_id_is_ended_not_queried(client):
    initialize_as_teacher("chemistry_p1", client, client.application)
    with client.session_transaction() as sess:
        sess["user_id"] = 3

    response = client.get("/admin/dashboard")

    # Postgres would reject 3 as uuid input; the request must end the session
    # before any query, not fail with a 500.
    assert response.status_code < 500
    assert _signed_in_user_id(client) is None
