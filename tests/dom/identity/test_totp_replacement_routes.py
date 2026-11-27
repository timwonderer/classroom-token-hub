"""Self-service TOTP replacement over HTTP (FEAT-IDEN-106, SPEC-IDEN-002 §IX).

One implementation serves ``/admin`` and ``/sysadmin``. A replacement is authorized by a
fresh passkey assertion bound to the operation; the old secret stays valid until the new
code is confirmed.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest

from app import db
from app.feats.base import FEATContext
from app.models import AuditEvent, CredentialOperation, CredentialOperationStage, User
from app.services import credential_lifecycle as lifecycle
from app.utils.encryption import decrypt_totp
from app.utils.user_ids import passkey_external_id
from tests.dom.identity.test_passkey_lifecycle import _sysadmin, _teacher
from tests.helpers import temporal
from tests.helpers.passkey import HELD_SEED, fake_passwordless, give_totp_seed, record_passkey, totp_code  # noqa: F401

PREFIXES = ("/admin", "/sysadmin")


def _user(user_id):
    return db.session.query(User).filter_by(id=user_id).populate_existing().one()


def _ops(user_id):
    db.session.expire_all()
    return CredentialOperation.query.filter_by(user_id=user_id).all()


def _open_ops(user_id):
    return [o for o in _ops(user_id) if o.stage not in (
        CredentialOperationStage.COMPLETED, CredentialOperationStage.CANCELLED)]


def _stored_seed(user_id):
    return _user(user_id).totp_secret_encrypted


def _old_code_valid(user_id, seed=HELD_SEED):
    return lifecycle.evaluate_totp_code(_user(user_id), pyotp.TOTP(seed).at(temporal.now()))


def _challenge(client, prefix):
    response = client.post(f"{prefix}/totp/replace/challenge")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _start(client, fake, credential, prefix="/admin", token=None, challenge=None):
    if challenge is None:
        challenge = _challenge(client, prefix)["challenge"]
    if token is None:
        token = fake.sign_in_token(credential)
    return client.post(f"{prefix}/totp/replace/start", json={"token": token, "challenge": challenge})


def _confirm(client, code, prefix="/admin"):
    return client.post(f"{prefix}/totp/replace/confirm", json={"code": code})


def _signed_out(client, prefix):
    return client.get(f"{prefix}/passkey/settings").status_code in (302, 401)


def _principal(client, app, fake, prefix, credential="cred-a"):
    if prefix == "/admin":
        _, user_id = _teacher(client, app, fake, passkeys=(credential,))
    else:
        user_id = _sysadmin(client, fake, passkeys=(credential,))
    return user_id


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__a_fresh_passkey_assertion_replaces_the_totp(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    before = _stored_seed(user_id)
    generation = _user(user_id).credential_generation

    started = _start(client, fake_passwordless, "cred-a", prefix)
    assert started.status_code == 200
    body = started.get_json()
    new_secret = body["secret"]
    assert len(new_secret) >= 32 and new_secret != HELD_SEED
    assert body["qr"].startswith("data:image/png;base64,")

    # Staged only: the old secret is untouched and still signs in; the pending seed is encrypted.
    assert _stored_seed(user_id) == before and _old_code_valid(user_id)
    (operation,) = _open_ops(user_id)
    assert operation.pending_totp_encrypted and decrypt_totp(operation.pending_totp_encrypted) == new_secret
    assert new_secret not in operation.pending_totp_encrypted

    done = _confirm(client, pyotp.TOTP(new_secret).at(temporal.now()), prefix)
    assert done.status_code == 200 and done.get_json()["redirect"].endswith(f"{prefix}/login")

    user = _user(user_id)
    assert decrypt_totp(user.totp_secret_encrypted) == new_secret
    assert user.credential_generation == generation + 1
    assert not _old_code_valid(user_id)
    assert lifecycle.evaluate_totp_code(user, pyotp.TOTP(new_secret).at(temporal.now()))
    (operation,) = _ops(user_id)
    assert operation.stage is CredentialOperationStage.COMPLETED and operation.pending_totp_encrypted is None
    assert _signed_out(client, prefix)
    events = AuditEvent.query.filter_by(table_name="credential_lifecycle_outcome").all()
    assert len(events) == 1 and events[0].actor_type == ("teacher" if prefix == "/admin" else "sysadmin")


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__a_wrong_new_code_changes_nothing(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    before = _stored_seed(user_id)
    secret = _start(client, fake_passwordless, "cred-a", prefix).get_json()["secret"]
    taken = {pyotp.TOTP(secret).at(temporal.now(), counter_offset=k) for k in (-1, 0, 1)}
    wrong = next(f"{n:06d}" for n in range(10**6) if f"{n:06d}" not in taken)

    refused = _confirm(client, wrong, prefix)

    assert refused.status_code == 400 and refused.get_json()["code"] == "code_rejected"
    assert _stored_seed(user_id) == before and _old_code_valid(user_id)
    (operation,) = _open_ops(user_id)
    assert operation.pending_totp_encrypted
    # The same operation still completes with the right code.
    assert _confirm(client, pyotp.TOTP(secret).at(temporal.now()), prefix).status_code == 200


def test_FEAT_IDEN_106__the_old_totp_code_cannot_confirm_the_replacement(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    _start(client, fake_passwordless, "cred-a")
    assert _confirm(client, totp_code()).status_code == 400
    assert _old_code_valid(user_id)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__a_missing_or_wrong_assertion_is_refused(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    challenge = _challenge(client, prefix)["challenge"]

    cases = {
        "no body": client.post(f"{prefix}/totp/replace/start", json={}),
        "unknown token": _start(client, fake_passwordless, "cred-a", prefix, token="verify_nope", challenge=challenge),
        "totp code as proof": _start(client, fake_passwordless, "cred-a", prefix, token=totp_code(), challenge=challenge),
        "no challenge": client.post(
            f"{prefix}/totp/replace/start", json={"token": fake_passwordless.sign_in_token("cred-a")}),
        "forged challenge": _start(client, fake_passwordless, "cred-a", prefix, challenge="0" * 64),
        "registration token": _start(
            client, fake_passwordless, "cred-a", prefix,
            token=fake_passwordless.complete_registration(user_id), challenge=challenge),
        "wrong ceremony origin": None,
    }
    fake_passwordless.origin = "https://evil.test"
    cases["wrong ceremony origin"] = _start(client, fake_passwordless, "cred-a", prefix, challenge=challenge)
    fake_passwordless.origin = "https://cth.test"

    for name, response in cases.items():
        assert response.status_code in (400, 403), name
    assert _ops(user_id) == [] and _old_code_valid(user_id)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__a_credential_not_recorded_for_the_principal_is_refused(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    # A valid provider assertion for a credential that is not an activated local binding.
    fake_passwordless.credentials["cred-pending"] = passkey_external_id(user_id)
    assert _start(client, fake_passwordless, "cred-pending", prefix).status_code == 403
    assert _ops(user_id) == []


def test_FEAT_IDEN_106__a_passkey_token_is_single_use(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    token = fake_passwordless.sign_in_token("cred-a")
    challenge = _challenge(client, "/admin")["challenge"]
    assert _start(client, fake_passwordless, "cred-a", token=token, challenge=challenge).status_code == 200
    client.post("/admin/totp/replace/cancel")
    assert _start(client, fake_passwordless, "cred-a", token=token, challenge=challenge).status_code == 403


def test_FEAT_IDEN_106__a_challenge_from_another_session_is_refused(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    user = _user(user_id)
    other = lifecycle._step_up_value(
        user_id, lifecycle.CredentialOperationPurpose.TOTP_REPLACE, "another-session",
        user.credential_generation, lifecycle._step_up_bucket())
    assert _start(client, fake_passwordless, "cred-a", challenge=other).status_code == 403
    # A challenge for another purpose does not authorize this one either.
    wrong_purpose = lifecycle._step_up_value(
        user_id, lifecycle.CredentialOperationPurpose.PASSKEY_REVOKE, user.current_session_nonce,
        user.credential_generation, lifecycle._step_up_bucket())
    assert _start(client, fake_passwordless, "cred-a", challenge=wrong_purpose).status_code == 403
    assert _ops(user_id) == []


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__cancel_erases_the_pending_seed_and_keeps_the_old_totp(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    before = _stored_seed(user_id)
    secret = _start(client, fake_passwordless, "cred-a", prefix).get_json()["secret"]

    assert client.post(f"{prefix}/totp/replace/cancel").status_code == 200

    (operation,) = _ops(user_id)
    assert operation.stage is CredentialOperationStage.CANCELLED and operation.pending_totp_encrypted is None
    assert _stored_seed(user_id) == before and _old_code_valid(user_id)
    assert _confirm(client, pyotp.TOTP(secret).at(temporal.now()), prefix).status_code == 404
    assert _stored_seed(user_id) == before
    # A new replacement can start afterwards.
    assert _start(client, fake_passwordless, "cred-a", prefix).status_code == 200


def test_FEAT_IDEN_106__an_expired_replacement_cannot_activate(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    before = _stored_seed(user_id)
    secret = _start(client, fake_passwordless, "cred-a").get_json()["secret"]

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=10, seconds=1)):
        refused = _confirm(client, pyotp.TOTP(secret).at(temporal.now()))

    assert refused.status_code == 409 and refused.get_json()["code"] == "operation_expired"
    assert _stored_seed(user_id) == before and _old_code_valid(user_id)


def test_FEAT_IDEN_106__a_second_start_is_refused_while_one_is_open(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    assert _start(client, fake_passwordless, "cred-a").status_code == 200
    again = _start(client, fake_passwordless, "cred-a")
    assert again.status_code == 409 and again.get_json()["code"] == "operation_already_open"
    assert len(_open_ops(user_id)) == 1


def test_FEAT_IDEN_106__another_principal_cannot_confirm_or_cancel_the_operation(client, app, fake_passwordless):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    _, alice = _teacher(client, app, fake_passwordless, passkeys=("cred-a",), key="chemistry_p1")
    secret = _start(client, fake_passwordless, "cred-a").get_json()["secret"]
    alice_before = _stored_seed(alice)

    with client.session_transaction() as sess:
        sess.clear()
    other = initialize_as_teacher("biology_block_a", client, app).teacher_user.id
    assert other != alice

    assert _confirm(client, pyotp.TOTP(secret).at(temporal.now())).status_code == 404
    assert client.post("/admin/totp/replace/cancel").status_code == 404
    assert _stored_seed(alice) == alice_before
    (operation,) = _open_ops(alice)
    assert operation.pending_totp_encrypted
    # Nor can the other principal use Alice's passkey to authorize their own replacement.
    give_totp_seed(other)
    record_passkey(other, "cred-other", fake_passwordless)
    db.session.expire_all()
    stolen = fake_passwordless.sign_in_token("cred-a")
    assert _start(client, fake_passwordless, "cred-other", token=stolen).status_code == 403
    assert _ops(other) == []


def test_FEAT_IDEN_106__a_principal_without_a_passkey_cannot_replace(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    assert _start(client, fake_passwordless, "cred-x", token="verify_none").status_code in (400, 403)
    assert _ops(user_id) == []


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__the_endpoints_need_a_signed_in_principal(client, app, fake_passwordless, prefix):
    for name in ("challenge", "start", "confirm", "cancel"):
        response = client.post(f"{prefix}/totp/replace/{name}", json={})
        assert response.status_code in (302, 401), name


def test_FEAT_IDEN_106__a_sysadmin_session_cannot_use_the_teacher_endpoints(client, app, fake_passwordless):
    _sysadmin(client, fake_passwordless)
    assert client.post("/admin/totp/replace/challenge").status_code in (302, 401, 403, 404)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_INV_ARC_007__the_settings_page_get_writes_nothing(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    secret = _start(client, fake_passwordless, "cred-a", prefix).get_json()["secret"]
    db.session.expire_all()
    snapshot = (
        _stored_seed(user_id), _user(user_id).credential_generation, AuditEvent.query.count(),
        [(o.id, o.stage, o.pending_totp_encrypted) for o in _ops(user_id)],
    )

    page = client.get(f"{prefix}/passkey/settings")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "totpCancelButton" in html and secret not in html  # progress shown, seed never re-rendered
    db.session.expire_all()
    assert snapshot == (
        _stored_seed(user_id), _user(user_id).credential_generation, AuditEvent.query.count(),
        [(o.id, o.stage, o.pending_totp_encrypted) for o in _ops(user_id)],
    )


def test_FEAT_IDEN_106__the_challenge_endpoint_stores_nothing(client, app, fake_passwordless):
    user_id = _principal(client, app, fake_passwordless, "/admin")
    body = _challenge(client, "/admin")
    assert body["challenge"] and body["apiKey"] and body["alias"]
    assert _ops(user_id) == []


def test_FEAT_IDEN_106__a_teacher_with_no_active_class_can_replace_the_totp(client, app, fake_passwordless):
    """FEAT-IDEN-106 §II: no active classroom is required, so no endpoint redirects to onboarding."""
    _, user_id = _teacher(client, app, fake_passwordless)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:classless:{uuid.uuid4().hex}"):
        user = _user(user_id)
        user.last_active_class_id = None
        user.last_active_seat_id = None

    assert _challenge(client, "/admin")["alias"]
    new_secret = _start(client, fake_passwordless, "cred-a").get_json()["secret"]
    assert client.post("/admin/totp/replace/cancel").status_code == 200
    assert _start(client, fake_passwordless, "cred-a").status_code == 200
    secret = _open_ops(user_id)[0].pending_totp_encrypted
    done = _confirm(client, pyotp.TOTP(decrypt_totp(secret)).at(temporal.now()))
    assert done.status_code == 200 and done.get_json()["redirect"].endswith("/admin/login")
    assert new_secret != decrypt_totp(_user(user_id).totp_secret_encrypted)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__a_stale_cancel_cannot_cancel_a_newer_replacement(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    first = _start(client, fake_passwordless, "cred-a", prefix).get_json()["binding"]
    assert client.post(f"{prefix}/totp/replace/cancel", json={"binding": first}).status_code == 200
    second = _start(client, fake_passwordless, "cred-a", prefix).get_json()["binding"]
    assert first != second

    stale = client.post(f"{prefix}/totp/replace/cancel", json={"binding": first})
    assert stale.status_code == 409 and stale.get_json()["code"] == "binding_mismatch"
    (operation,) = _open_ops(user_id)
    assert operation.pending_totp_encrypted is not None

    assert client.post(f"{prefix}/totp/replace/cancel", json={"binding": "not-a-binding"}).status_code == 409
    assert client.post(f"{prefix}/totp/replace/cancel", json={"binding": second}).status_code == 200
    assert _open_ops(user_id) == []


@pytest.mark.parametrize("prefix", PREFIXES)
def test_FEAT_IDEN_106__the_settings_page_carries_the_binding_of_the_open_replacement(client, app, fake_passwordless, prefix):
    user_id = _principal(client, app, fake_passwordless, prefix)
    binding = _start(client, fake_passwordless, "cred-a", prefix).get_json()["binding"]
    page = client.get(f"{prefix}/passkey/settings").get_data(as_text=True)
    assert f'id="totpCancelButton" data-binding="{binding}"' in page
