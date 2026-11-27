"""Passkey enrollment, selected replacement and revocation (FEAT-IDEN-102, FEAT-IDEN-107).

SPEC-IDEN-002 §V/§IX and DOM-IDEN-003 §VII.A: a passkey is added, replaced or removed
only after fresh TOTP; the
pending registration is persisted before the provider issues a token; the old credential
is retired remotely before its local binding goes; and completion advances the
credential generation, voids the sign-in and emits one non-identifying outcome.

The provider is the in-memory fake in ``tests/helpers/passkey.py``. It proves local
behaviour only: it is not evidence of passwordless.dev's real delete/inventory semantics.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import shutil
import subprocess
import textwrap
import uuid
from types import SimpleNamespace
from contextlib import contextmanager

import pytest
import sqlalchemy as sa

from app import db
from app.feats import passkey_lifecycle_feat as feat
from app.feats.base import FEATContext
from app.models import (
    AuditEvent,
    CredentialOperation,
    CredentialOperationPurpose,
    CredentialOperationStage,
    PasskeyCredential,
    User,
)
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service
from app.services.credential_lifecycle import CredentialOperationRefused, TotpCode
from app.utils.encryption import decrypt_totp
from app.utils.user_ids import passkey_external_id
from tests.helpers import temporal
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.operation_routes import seed_sysadmin_session
from tests.helpers.passkey import (  # noqa: F401  (fake_passwordless is a fixture)
    HELD_SEED,
    fake_passwordless,
    finish_registration,
    give_totp_seed,
    record_passkey,
    start_registration,
    totp_code,
)

_TERMINAL = (CredentialOperationStage.COMPLETED, CredentialOperationStage.CANCELLED)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _teacher(client, app, fake, passkeys=("cred-a",), key="chemistry_p1"):
    """A signed-in teacher holding a 160-bit TOTP seed and the named activated passkeys."""
    classroom = initialize_as_teacher(key, client, app)
    user_id = classroom.teacher_user.id
    give_totp_seed(user_id)
    for credential in passkeys:
        record_passkey(user_id, credential, fake, name=f"name-{credential}")
    return classroom, user_id


def _sysadmin(client, fake, passkeys=("cred-s1",)):
    from app.services.identity_service import create_system_principal
    from app.utils.auth_username import build_hashed_username_fields

    with FEATContext("FEAT-IDEN-008", idempotency_key=f"passkey-test:sysadmin:{uuid.uuid4().hex}"):
        create_system_principal("op_sysadmin")
    lookup = build_hashed_username_fields("op_sysadmin")[2]
    user_id = User.query.filter_by(username_lookup_hash=lookup).one().id
    give_totp_seed(user_id)
    for credential in passkeys:
        record_passkey(user_id, credential, fake)
    seed_sysadmin_session(client, user_id=user_id, username="op_sysadmin")
    return user_id


def _user(user_id):
    return db.session.query(User).filter_by(id=user_id).populate_existing().one()


def _nonce(user_id):
    return _user(user_id).current_session_nonce


def _bound(user_id):
    db.session.expire_all()
    return sorted(r.credential_id for r in PasskeyCredential.query.filter_by(user_id=user_id).all())


def _row_id(credential_id):
    return PasskeyCredential.query.filter_by(credential_id=credential_id).one().id


def _operations(user_id):
    db.session.expire_all()
    return CredentialOperation.query.filter_by(user_id=user_id).all()


def _open_operations(user_id):
    return [o for o in _operations(user_id) if o.stage not in _TERMINAL]


def _outcomes():
    db.session.expire_all()
    return AuditEvent.query.filter_by(table_name="credential_lifecycle_outcome").all()


def _wrong_code():
    import pyotp
    taken = {pyotp.TOTP(HELD_SEED).at(temporal.now(), counter_offset=k) for k in (-1, 0, 1)}
    return next(f"{n:06d}" for n in range(1000000) if f"{n:06d}" not in taken)


def _signed_out(client, prefix="/admin") -> bool:
    return client.get(f"{prefix}/passkey/settings").status_code in (302, 401)


def _new_credential(fake, user_id):
    """Complete a browser registration on the fake; returns ``(token, credential_id)``."""
    before = set(fake.credentials)
    token = fake.complete_registration(user_id)
    (credential_id,) = set(fake.credentials) - before
    return token, credential_id


def _replace(client, fake, user_id, old_credential, *, prefix="/admin", name="Replacement"):
    """The browser's replacement: start (TOTP + selection), register, finish."""
    started = start_registration(client, prefix=prefix, replace_passkey_id=_row_id(old_credential))
    assert started.status_code == 200, started.get_json()
    token, credential_id = _new_credential(fake, user_id)
    return finish_registration(client, token, prefix=prefix, name=name), credential_id


def _enroll(client, fake, user_id, *, prefix="/admin", name="Added"):
    started = start_registration(client, prefix=prefix)
    assert started.status_code == 200, started.get_json()
    token, credential_id = _new_credential(fake, user_id)
    return finish_registration(client, token, prefix=prefix, name=name), credential_id


def _revoke(client, row_id, *, prefix="/admin", code=None):
    return client.delete(
        f"{prefix}/passkey/{row_id}/delete", json={"totp_code": totp_code() if code is None else code},
    )


def _latest_binding(user_id):
    """The binding of the principal's most recent operation, as its settings page (or start response) held it."""
    db.session.expire_all()
    operation = (
        CredentialOperation.query.filter_by(user_id=user_id).order_by(CredentialOperation.created_at.desc()).first()
    )
    return None if operation is None else lifecycle.registration_binding(operation)


def _resume(client, user_id, **body):
    return client.post(
        "/admin/passkey/resume", json={"binding": _latest_binding(user_id), **body},
    )


def _committed_state(user_id):
    """Bindings, operation stages and outcome-row count as another connection sees them."""
    with db.engine.connect() as connection:
        bound = sorted(r[0] for r in connection.execute(
            sa.text("SELECT credential_id FROM passkey_credentials WHERE user_id = :u"), {"u": user_id}))
        stages = sorted(r[0] for r in connection.execute(
            sa.text("SELECT stage FROM credential_operations WHERE user_id = :u"), {"u": user_id}))
        outcomes = connection.execute(sa.text(
            "SELECT count(*) FROM audit_events WHERE table_name = 'credential_lifecycle_outcome'")).scalar()
    return bound, stages, outcomes


def _fail_after_staging(monkeypatch):
    """``complete_retirement`` stages every write, then the transaction fails before it commits.

    The first call runs the real command (so its bindings, generation, session rotation and
    outcome row are all staged in the open transaction) and then raises; the FEAT context
    rolls that transaction back. Later calls are the real command.
    """
    real = lifecycle.complete_retirement
    attempts = []

    def staged_then_failing(operation, **kwargs):
        attempts.append(1)
        result = real(operation, **kwargs)
        if len(attempts) == 1:
            raise RuntimeError("the connection dropped before commit")
        return result

    monkeypatch.setattr(lifecycle, "complete_retirement", staged_then_failing)


def _committed_stage(operation_id):
    """The stage another connection sees: only committed state, independent of the test session."""
    with db.engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT stage FROM credential_operations WHERE id = :id"), {"id": operation_id},
        ).scalar()


def _retirement_committed(client, fake, user_id, old="cred-b"):
    """A replacement whose retirement intent is committed but whose provider deletion failed."""
    fake.fail_deletes = True
    response, new_credential = _replace(client, fake, user_id, old)
    assert response.status_code == 503, response.get_json()
    fake.fail_deletes = False
    (operation,) = _open_operations(user_id)
    return operation.id, new_credential


# ---------------------------------------------------------------------------
# enrollment: the fresh-TOTP gate
# ---------------------------------------------------------------------------

def test_a_login_session_alone_cannot_start_an_enrollment(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless)

    no_code = client.post("/admin/passkey/register/start", json={})
    wrong_code = start_registration(client, code=_wrong_code())

    assert no_code.status_code == 403 and wrong_code.status_code == 403
    assert fake_passwordless.calls == []  # no provider token was ever requested
    assert _operations(user_id) == []


def test_a_fresh_code_starts_one_pending_registration_and_returns_a_token(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless)

    response = start_registration(client)

    assert response.status_code == 200
    assert response.get_json()["token"].startswith("register_")
    (operation,) = _open_operations(user_id)
    assert operation.purpose is CredentialOperationPurpose.PASSKEY_ENROLL
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING


def test_the_pending_registration_is_committed_before_the_provider_issues_a_token(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless)
    seen = []
    original = fake_passwordless.register_token

    def spy(register_token):
        seen.append((db.session().in_transaction(), [
            _committed_stage(o.id) for o in CredentialOperation.query.filter_by(user_id=user_id)
        ]))
        return original(register_token)

    fake_passwordless.register_token = spy
    assert start_registration(client).status_code == 200

    assert seen == [(False, ["registration_pending"])]


def test_the_registration_token_never_outlives_the_operation_deadline(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless)
    captured = []
    original = fake_passwordless.register_token
    fake_passwordless.register_token = lambda rt: (captured.append(rt.expires_at), original(rt))[1]

    assert start_registration(client).status_code == 200
    (operation,) = _open_operations(user_id)

    assert captured[0] <= operation.deadline_at
    assert temporal.seconds_between(temporal.now(), captured[0]) <= lifecycle.REGISTRATION_TOKEN_SECONDS

    # Near the end of the interactive window the token is capped by the deadline itself.
    with temporal.pinned_clock(temporal.shifted(operation.deadline_at, seconds=-30)):
        assert lifecycle.registration_token_expiry(operation.deadline_at) == operation.deadline_at


def test_every_provider_call_runs_with_no_database_transaction_open(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    open_during = []
    for name in ("register_token", "send", "delete_credential"):  # ``send`` is the /signin/verify round trip
        original = getattr(fake_passwordless, name)

        def spy(arg, _original=original, **kwargs):
            open_during.append(db.session().in_transaction())
            return _original(arg, **kwargs)

        setattr(fake_passwordless, name, spy)

    _replace(client, fake_passwordless, user_id, "cred-b")

    assert len(open_during) == 3 and not any(open_during)


# ---------------------------------------------------------------------------
# enrollment: completion
# ---------------------------------------------------------------------------

def test_enrollment_activates_the_credential_the_token_names_and_ends_the_sign_in(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    generation = _user(user_id).credential_generation
    nonce = _nonce(user_id)

    response, credential_id = _enroll(client, fake_passwordless, user_id, name="  YubiKey  ")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True and body["redirect"].endswith("/admin/login")
    assert "Sign in again" in body["message"]
    assert _bound(user_id) == [credential_id]
    assert PasskeyCredential.query.one().authenticator_name == "YubiKey"
    user = _user(user_id)
    assert user.credential_generation == generation + 1
    assert user.current_session_nonce != nonce
    assert _signed_out(client)
    (operation,) = _operations(user_id)
    assert operation.stage is CredentialOperationStage.COMPLETED
    assert operation.old_credential_id is None and operation.new_credential_id is None
    assert operation.session_binding_hash == lifecycle.ERASED_SESSION_BINDING
    assert lifecycle.credential_compliance(user) is lifecycle.CredentialCompliance.COMPLIANT


def test_a_second_passkey_may_be_added_and_the_first_survives(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))

    response, credential_id = _enroll(client, fake_passwordless, user_id)

    assert response.status_code == 200
    assert _bound(user_id) == sorted(["cred-a", credential_id])


def test_enrollment_emits_one_non_identifying_outcome(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    response, credential_id = _enroll(client, fake_passwordless, user_id, name="Distinctive label")

    (event,) = _outcomes()
    assert event.feat_id == "FEAT-IDEN-102" and event.operation == "TRANSITION"
    assert event.actor_type == "teacher" and event.chain_scope == "system"
    assert event.class_id is None and event.seat_id is None and event.actor_id_hash is None
    uuid.UUID(event.row_pk)
    payload = json.dumps([event.row_pk, event.correlation_id, event.request_id, event.idempotency_key,
                          getattr(event, "payload", None), getattr(event, "protected_payload", None)], default=str)
    for identifying in (user_id, credential_id, "Distinctive label", passkey_external_id(user_id)):
        assert identifying not in payload


def test_enrollment_is_refused_after_its_deadline_and_changes_nothing(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    assert start_registration(client).status_code == 200
    token, _ = _new_credential(fake_passwordless, user_id)
    (operation,) = _open_operations(user_id)

    with temporal.pinned_clock(temporal.shifted(operation.deadline_at, seconds=1)):
        response = finish_registration(client, token)

    assert response.status_code == 409 and response.get_json()["code"] == "operation_expired"
    assert _bound(user_id) == []


@pytest.mark.parametrize("make_token", ["sign_in", "other_principal", "unverifiable"])
def test_a_wrong_type_wrong_principal_or_unverifiable_token_registers_nothing(
    client, app, fake_passwordless, make_token,
):
    classroom, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    other = initialize("biology_block_a", app)
    assert start_registration(client).status_code == 200
    if make_token == "sign_in":
        fake_passwordless.credentials["cred-x"] = passkey_external_id(user_id)
        token = fake_passwordless.sign_in_token("cred-x")
    elif make_token == "other_principal":
        token = fake_passwordless.complete_registration(other.teacher_user.id)
    else:
        token = "made-up-token"

    response = finish_registration(client, token)

    assert response.status_code == 400
    assert _bound(user_id) == []
    # The operation is still pending: the user can cancel and start again.
    assert [o.stage for o in _open_operations(user_id)] == [CredentialOperationStage.REGISTRATION_PENDING]
    assert other


def test_a_token_naming_a_credential_already_recorded_is_refused(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    fake_passwordless.credentials["cred-a"] = passkey_external_id(user_id)
    token = fake_passwordless._token(
        passkey_external_id(user_id), "cred-a", "passkey_register", nickname=client.last_registration_binding,
    )

    response = finish_registration(client, token)

    assert response.status_code == 400
    assert _bound(user_id) == ["cred-a"]


def test_finishing_without_a_pending_registration_is_refused(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    token, _ = _new_credential(fake_passwordless, user_id)

    response = finish_registration(client, token)

    assert response.status_code == 404 and response.get_json()["code"] == "operation_not_found"
    assert _bound(user_id) == []


def test_a_registration_cannot_be_finished_from_another_session_of_the_same_teacher(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    assert start_registration(client).status_code == 200
    token, _ = _new_credential(fake_passwordless, user_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:nonce:{uuid.uuid4().hex}"):
        _user(user_id).current_session_nonce = "a-newer-sign-in"

    with pytest.raises(CredentialOperationRefused) as refused:
        feat.finish_registration(
            user_id=user_id, session_nonce=_nonce(user_id) + "-stale", token=token,
            binding=client.last_registration_binding, authenticator_name="x",
        )

    assert refused.value.category == "session_not_current"
    assert _bound(user_id) == []


def test_a_pending_or_candidate_credential_cannot_sign_in(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    token, pending = _new_credential(fake_passwordless, user_id)
    client_b = app.test_client()

    # Registration pending: the provider can sign the new credential in, the registry cannot.
    attempt = client_b.post("/admin/passkey/auth/finish", json={"token": fake_passwordless.sign_in_token(pending)})
    assert attempt.status_code == 401

    # Candidate verified (recorded on the operation, not yet activated): still no authority.
    verified = passkey_service.verify_token(token)
    (operation,) = _open_operations(user_id)
    with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:record:{uuid.uuid4().hex}"):
        lifecycle.record_registered_credential(
            db.session.get(CredentialOperation, operation.id), verified, session_nonce=_nonce(user_id),
        )
    assert _open_operations(user_id)[0].stage is CredentialOperationStage.CANDIDATE_VERIFIED
    attempt = client_b.post("/admin/passkey/auth/finish", json={"token": fake_passwordless.sign_in_token(pending)})
    assert attempt.status_code == 401
    assert _bound(user_id) == ["cred-a"]


def test_a_late_cancel_bearing_an_earlier_attempts_binding_leaves_the_newer_operation_open(
    client, app, fake_passwordless,
):
    """Two tabs: A is cancelled and B started; A's stale Cancel button must not end B."""
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    binding_a = client.last_registration_binding
    assert client.post("/admin/passkey/cancel", json={"binding": binding_a}).status_code == 200
    assert start_registration(client).status_code == 200
    binding_b = client.last_registration_binding
    (before,) = _open_operations(user_id)

    late = client.post("/admin/passkey/cancel", json={"binding": binding_a})

    assert late.status_code == 409 and late.get_json()["code"] == "binding_mismatch"
    (after,) = _open_operations(user_id)
    assert after.id == before.id and after.stage is CredentialOperationStage.REGISTRATION_PENDING
    # B's own binding (and, where none exists, the unbound form) still cancels it.
    assert client.post("/admin/passkey/cancel", json={"binding": binding_b}).status_code == 200
    assert _open_operations(user_id) == []


@pytest.mark.parametrize("malformed", ["", 123, [], {}, "not-a-binding", "A" * 64, False])
def test_a_cancel_with_a_malformed_binding_is_refused_and_the_operation_stays_open(
    client, app, fake_passwordless, malformed,
):
    """A supplied binding that is not the operation's is never read as an unbound cancel."""
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    (before,) = _open_operations(user_id)

    refused = client.post("/admin/passkey/cancel", json={"binding": malformed})

    assert refused.status_code == 409 and refused.get_json()["code"] == "binding_mismatch"
    (after,) = _open_operations(user_id)
    assert after.id == before.id and after.stage is CredentialOperationStage.REGISTRATION_PENDING


@pytest.mark.parametrize("body", [{}, {"binding": None}])
def test_a_cancel_with_no_binding_or_a_null_binding_still_cancels_the_open_operation(
    client, app, fake_passwordless, body,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200

    assert client.post("/admin/passkey/cancel", json=body).status_code == 200
    assert _open_operations(user_id) == []


def test_cancelling_before_completion_frees_the_slot_and_keeps_the_old_binding(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    assert start_registration(client).get_json()["code"] == "operation_already_open"

    assert client.post("/admin/passkey/cancel", json={}).status_code == 200

    assert _open_operations(user_id) == []
    assert _bound(user_id) == ["cred-a"]
    assert start_registration(client).status_code == 200


def test_a_failed_token_request_cancels_the_operation(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless)
    fake_passwordless.aliases = type("Owned", (dict,), {"get": lambda self, k, d=None: "user_3"})()

    response = start_registration(client)

    assert response.status_code == 409
    assert _open_operations(user_id) == []


# ---------------------------------------------------------------------------
# selected replacement
# ---------------------------------------------------------------------------

def test_replacing_b_among_a_b_c_with_d_preserves_a_and_c(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    generation = _user(user_id).credential_generation

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 200, response.get_json()
    assert _bound(user_id) == sorted(["cred-a", "cred-c", d])
    assert [c for c in fake_passwordless.calls if c[0] == "delete_credential"] == [("delete_credential", "cred-b")]
    assert set(fake_passwordless.credentials) == {"cred-a", "cred-c", d}
    assert _user(user_id).credential_generation == generation + 1
    assert _signed_out(client)
    (event,) = _outcomes()
    assert event.feat_id == "FEAT-IDEN-102"
    (operation,) = _operations(user_id)
    assert operation.stage is CredentialOperationStage.COMPLETED
    assert operation.old_credential_id is None and operation.new_credential_id is None


def test_replacement_commits_intent_and_consumes_the_session_binding_before_the_provider_delete(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    observed = []
    original = fake_passwordless.delete_credential

    def spy(delete_credential):
        # Remote-before-local: at deletion time the old binding is still the local authority,
        # the intent is already committed, and no transaction is open.
        with db.engine.connect() as connection:
            local = connection.execute(sa.text(
                "SELECT count(*) FROM passkey_credentials WHERE credential_id = :c"), {"c": delete_credential.credential_id},
            ).scalar()
            row = connection.execute(sa.text(
                "SELECT stage, session_binding_hash, retirement_intent_at FROM credential_operations")).one()
        observed.append((db.session().in_transaction(), local, row.stage, row.session_binding_hash,
                         row.retirement_intent_at is not None))
        return original(delete_credential)

    fake_passwordless.delete_credential = spy
    assert _replace(client, fake_passwordless, user_id, "cred-b")[0].status_code == 200

    assert observed == [(False, 1, "retirement_committed", lifecycle.ERASED_SESSION_BINDING, True)]


@pytest.mark.parametrize("foreign", [False, True])
def test_replacing_a_missing_or_foreign_credential_is_refused_and_opens_nothing(
    client, app, fake_passwordless, foreign,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    other = initialize("biology_block_a", app)
    other_user = other.teacher_user.id
    record_passkey(other_user, "cred-foreign", fake_passwordless)
    target = _row_id("cred-foreign") if foreign else 10 ** 9

    response = client.post(
        "/admin/passkey/register/start", json={"totp_code": totp_code(), "replace_passkey_id": target},
    )

    assert response.status_code in (403, 404)
    assert [c for c in fake_passwordless.calls if c[0] == "register_token"] == []
    assert _bound(other_user) == ["cred-foreign"]
    assert other


def test_a_signed_in_teacher_whose_totp_is_wrong_cannot_replace(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))

    response = start_registration(client, code=_wrong_code(), replace_passkey_id=_row_id("cred-a"))

    assert response.status_code == 403
    assert _operations(user_id) == []


def test_a_failed_provider_delete_keeps_the_old_binding_and_pending_is_reported(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    generation = _user(user_id).credential_generation
    fake_passwordless.fail_deletes = True

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 503 and response.get_json()["code"] == "provider_unavailable"
    assert "authenticator app still signs you in" in response.get_json()["error"]
    assert _bound(user_id) == ["cred-a", "cred-b"]  # nothing local changed; D is not bound
    assert _user(user_id).credential_generation == generation
    assert not _signed_out(client)  # the sign-in survives a pending change
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.PROVIDER_UNCERTAIN
    assert operation.error_category == "provider_unavailable" and operation.attempt_count == 1
    assert operation.old_credential_id == "cred-b" and operation.new_credential_id == d
    assert _outcomes() == []


def test_the_pending_replacement_finishes_when_the_provider_recovers(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    generation = _user(user_id).credential_generation
    operation_id, d = _retirement_committed(client, fake_passwordless, user_id)
    page = client.get("/admin/passkey/settings").get_data(as_text=True)
    assert "waiting to finish" in page and "resumePasskeyButton" in page

    response = _resume(client, user_id)

    assert response.status_code == 200 and response.get_json()["message"].startswith("Passkey replaced")
    assert _bound(user_id) == sorted(["cred-a", d])
    assert _user(user_id).credential_generation == generation + 1  # advanced once, not per attempt
    assert len(_outcomes()) == 1
    assert _operations(user_id)[0].id == operation_id
    assert _signed_out(client)


def test_a_lost_delete_response_is_not_taken_for_success_or_rollback(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.lose_next_delete_response = True

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 503
    assert "cred-b" not in fake_passwordless.credentials  # the provider did delete it
    assert _bound(user_id) == ["cred-a", "cred-b"]  # but we never assumed so
    assert _resume(client, user_id).status_code == 200  # same exact deletion retried
    assert _bound(user_id) == sorted(["cred-a", d])


def test_a_commit_failure_after_the_remote_delete_leaves_recoverable_state(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    generation = _user(user_id).credential_generation
    _fail_after_staging(monkeypatch)

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 500
    assert "cred-b" not in fake_passwordless.credentials  # remote retirement happened
    bound, stages, outcomes = _committed_state(user_id)
    assert bound == ["cred-a", "cred-b"]  # the staged swap never committed
    assert stages == [CredentialOperationStage.RETIREMENT_COMMITTED.value]  # the intent did
    assert outcomes == 0
    assert _user(user_id).credential_generation == generation

    assert _resume(client, user_id).status_code == 200
    bound, stages, outcomes = _committed_state(user_id)
    assert bound == sorted(["cred-a", d]) and outcomes == 1
    assert stages == [CredentialOperationStage.COMPLETED.value]
    assert _user(user_id).credential_generation == generation + 1


def test_after_intent_the_fixed_operation_finishes_past_its_deadline_and_session(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    operation_id, d = _retirement_committed(client, fake_passwordless, user_id)
    (operation,) = _open_operations(user_id)

    with temporal.pinned_clock(temporal.shifted(operation.deadline_at, hours=3)):
        # A sweep leaves committed retirement alone, then the fixed work finishes with no session.
        with FEATContext("FEAT-IDEN-108", idempotency_key=f"test:sweep:{uuid.uuid4().hex}"):
            lifecycle.expire_stale_operations()
        assert feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id)) == ("replaced", False)

    assert _bound(user_id) == sorted(["cred-a", d])
    assert _operations(user_id)[0].id == operation_id


def test_before_intent_expiry_preserves_the_old_credential_and_the_sweep_cancels(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert start_registration(client, replace_passkey_id=_row_id("cred-b")).status_code == 200
    (operation,) = _open_operations(user_id)

    with temporal.pinned_clock(temporal.shifted(operation.deadline_at, seconds=1)):
        with FEATContext("FEAT-IDEN-108", idempotency_key=f"test:sweep:{uuid.uuid4().hex}"):
            assert lifecycle.expire_stale_operations()["cancelled"] == 1

    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert [o.stage for o in _operations(user_id)] == [CredentialOperationStage.CANCELLED]
    assert _outcomes() == []


def test_retirement_cannot_be_cancelled_once_committed(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)

    response = client.post("/admin/passkey/cancel", json={})

    assert response.status_code == 409 and response.get_json()["code"] == "retirement_committed"
    assert [o.stage for o in _open_operations(user_id)] == [CredentialOperationStage.PROVIDER_UNCERTAIN]


# ---------------------------------------------------------------------------
# supersession and duplicate completion
# ---------------------------------------------------------------------------

def _supersede(user_id):
    with FEATContext("FEAT-IDEN-105", idempotency_key=f"test:supersede:{uuid.uuid4().hex}"):
        user = lifecycle._lock_user(user_id)
        return lifecycle.supersede_for_recovery(user)


def test_recovery_supersedes_a_pending_registration_before_intent(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert start_registration(client, replace_passkey_id=_row_id("cred-b")).status_code == 200
    token, _ = _new_credential(fake_passwordless, user_id)

    assert _supersede(user_id) == 1
    response = finish_registration(client, token)

    assert response.status_code in (404, 409)
    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert "cred-b" in fake_passwordless.credentials


def test_recovery_supersedes_committed_retirement_which_then_cannot_activate_or_resign_anyone_out(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    assert _supersede(user_id) == 1
    generation, nonce = _user(user_id).credential_generation, _nonce(user_id)

    with pytest.raises(CredentialOperationRefused):
        feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id))

    assert _bound(user_id) == ["cred-a", "cred-b"]
    user = _user(user_id)
    assert user.credential_generation == generation and user.current_session_nonce == nonce
    assert _outcomes() == []


def _complete_twice(client, app, fake):
    """Returns ``(first, second, generation_after_first, nonce_after_newer_sign_in)``."""
    _, user_id = _teacher(client, app, fake, passkeys=("cred-a", "cred-b"))
    operation_id, d = _retirement_committed(client, fake, user_id)
    fake.credentials.pop("cred-b", None)

    def complete():
        with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:complete:{uuid.uuid4().hex}"):
            return lifecycle.complete_retirement(
                lifecycle.get_operation_for_user(operation_id, user_id), authenticator_name="D",
            )

    first = complete()
    generation = _user(user_id).credential_generation
    # A later sign-in establishes a new session; the replayed completion must not void it.
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:nonce:{uuid.uuid4().hex}"):
        _user(user_id).current_session_nonce = "a-later-sign-in"
    second = complete()
    return user_id, first, second, generation


def test_a_duplicate_completion_returns_the_stored_outcome_and_repeats_no_effect(client, app, fake_passwordless):
    user_id, first, second, generation = _complete_twice(client, app, fake_passwordless)

    assert first == lifecycle.COMPLETED and second == lifecycle.ALREADY_COMPLETED
    user = _user(user_id)
    assert user.credential_generation == generation
    assert user.current_session_nonce == "a-later-sign-in"
    assert len(_outcomes()) == 1
    assert len([b for b in _bound(user_id) if b != "cred-a"]) == 1  # one activation, never two


def test_a_duplicate_activation_is_idempotent(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=())
    assert start_registration(client).status_code == 200
    token, credential_id = _new_credential(fake_passwordless, user_id)
    nonce = _nonce(user_id)
    assert finish_registration(client, token).status_code == 200
    (operation,) = _operations(user_id)

    with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:activate:{uuid.uuid4().hex}"):
        again = lifecycle.activate_passkey(
            db.session.get(CredentialOperation, operation.id), authenticator_name="x", session_nonce=nonce,
        )

    assert again == lifecycle.ALREADY_COMPLETED
    assert _bound(user_id) == [credential_id] and len(_outcomes()) == 1


# ---------------------------------------------------------------------------
# revocation (FEAT-IDEN-107)
# ---------------------------------------------------------------------------

def test_revoking_b_among_a_b_c_preserves_a_and_c_and_totp(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    generation, seed = _user(user_id).credential_generation, _user(user_id).totp_secret_encrypted

    response = _revoke(client, _row_id("cred-b"))

    assert response.status_code == 200 and response.get_json()["message"].startswith("Passkey removed")
    assert _bound(user_id) == ["cred-a", "cred-c"]
    assert set(fake_passwordless.credentials) == {"cred-a", "cred-c"}
    user = _user(user_id)
    assert user.credential_generation == generation + 1 and user.totp_secret_encrypted == seed
    assert decrypt_totp(user.totp_secret_encrypted) == HELD_SEED
    assert _signed_out(client)
    (event,) = _outcomes()
    assert event.feat_id == "FEAT-IDEN-107" and event.actor_type == "teacher"
    (operation,) = _operations(user_id)
    assert operation.stage is CredentialOperationStage.COMPLETED and operation.old_credential_id is None


def test_revocation_needs_a_fresh_totp_code(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    row_id = _row_id("cred-b")

    for code in ("", "123", _wrong_code()):
        assert _revoke(client, row_id, code=code).status_code == 403
    assert client.delete(f"/admin/passkey/{row_id}/delete").status_code == 403  # a login session alone

    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert [c for c in fake_passwordless.calls if c[0] == "delete_credential"] == []
    assert _operations(user_id) == []


def _check_only_passkey_refused(client, app, fake):
    _, user_id = _teacher(client, app, fake, passkeys=("cred-only",))
    generation = _user(user_id).credential_generation

    response = _revoke(client, _row_id("cred-only"))

    assert response.status_code == 409 and response.get_json()["code"] == "only_passkey"
    assert "Replace it" in response.get_json()["error"]
    assert _bound(user_id) == ["cred-only"]
    assert [c for c in fake.calls if c[0] == "delete_credential"] == []  # the provider was never asked
    assert _user(user_id).credential_generation == generation
    assert _operations(user_id) == []  # nothing is left occupying the principal's slot
    assert not _signed_out(client)


def test_the_only_activated_passkey_cannot_be_revoked(client, app, fake_passwordless):
    _check_only_passkey_refused(client, app, fake_passwordless)


def test_the_only_passkey_can_still_be_replaced(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-only",))

    response, d = _replace(client, fake_passwordless, user_id, "cred-only")

    assert response.status_code == 200
    assert _bound(user_id) == [d]


def test_a_foreign_or_missing_passkey_cannot_be_revoked(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    other = initialize("biology_block_a", app)
    other_user = other.teacher_user.id
    record_passkey(other_user, "cred-foreign", fake_passwordless)
    foreign_row = _row_id("cred-foreign")

    for target in (foreign_row, 10 ** 9):
        response = client.delete(f"/admin/passkey/{target}/delete", json={"totp_code": totp_code()})
        assert response.status_code == 404 and response.get_json()["code"] == "credential_not_found"

    assert _bound(other_user) == ["cred-foreign"] and _bound(user_id) == ["cred-a", "cred-b"]
    assert "cred-foreign" in fake_passwordless.credentials
    assert [o for o in _operations(user_id) if o.stage not in _TERMINAL] == []
    assert other


def test_a_failed_remote_revocation_leaves_the_binding_and_is_reported_pending(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    generation = _user(user_id).credential_generation
    fake_passwordless.fail_deletes = True

    response = _revoke(client, _row_id("cred-b"))

    assert response.status_code == 503 and response.get_json()["code"] == "provider_unavailable"
    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert _user(user_id).credential_generation == generation and not _signed_out(client)
    (operation,) = _open_operations(user_id)
    assert operation.purpose is CredentialOperationPurpose.PASSKEY_REVOKE
    assert operation.stage is CredentialOperationStage.PROVIDER_UNCERTAIN

    fake_passwordless.fail_deletes = False
    assert _resume(client, user_id).get_json()["message"].startswith("Passkey removed")
    assert _bound(user_id) == ["cred-a"]


def test_a_lost_revocation_response_and_a_later_database_failure_converge(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.lose_next_delete_response = True
    _fail_after_staging(monkeypatch)

    assert _revoke(client, _row_id("cred-b")).status_code == 503  # deleted remotely, reply lost
    assert "cred-b" not in fake_passwordless.credentials

    # The retry confirms the deletion, stages the local completion, and the commit fails.
    assert _resume(client, user_id).status_code == 500
    bound, stages, outcomes = _committed_state(user_id)
    assert bound == ["cred-a", "cred-b"] and outcomes == 0
    assert stages == [CredentialOperationStage.PROVIDER_UNCERTAIN.value]

    assert _resume(client, user_id).status_code == 200
    bound, stages, outcomes = _committed_state(user_id)
    assert bound == ["cred-a"] and outcomes == 1
    assert stages == [CredentialOperationStage.COMPLETED.value]


def test_a_revocation_authorization_cannot_be_reused_after_it_is_consumed(client, app, fake_passwordless):
    """One request, one authorization: a second revoke while the first is pending is refused."""
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    fake_passwordless.fail_deletes = True
    assert _revoke(client, _row_id("cred-b")).status_code == 503
    fake_passwordless.fail_deletes = False

    second = _revoke(client, _row_id("cred-c"))

    assert second.status_code == 409 and second.get_json()["code"] == "operation_already_open"
    assert _bound(user_id) == ["cred-a", "cred-b", "cred-c"]


def test_a_stale_generation_refuses_revocation_completion(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.fail_deletes = True
    assert _revoke(client, _row_id("cred-b")).status_code == 503
    fake_passwordless.fail_deletes = False
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:gen:{uuid.uuid4().hex}"):
        _user(user_id).credential_generation += 1
    calls_before = list(fake_passwordless.calls)

    with pytest.raises(CredentialOperationRefused) as refused:
        feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id))

    assert refused.value.category == "stale_generation"
    assert fake_passwordless.calls == calls_before  # superseded work never reaches the provider
    assert "cred-b" in fake_passwordless.credentials
    assert _bound(user_id) == ["cred-a", "cred-b"]


def test_a_current_intent_still_proceeds_after_the_interactive_deadline_and_generation_check(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    operation_id, d = _retirement_committed(client, fake_passwordless, user_id)
    deadline = _operations(user_id)[0].deadline_at

    with temporal.pinned_clock(temporal.shifted(deadline, seconds=3600)):
        result = feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id))

    assert result == ("replaced", False)
    assert _bound(user_id) == sorted(["cred-a", d])


# ---------------------------------------------------------------------------
# principals, sessions, surfaces
# ---------------------------------------------------------------------------

def test_a_sysadmin_enrolls_replaces_and_revokes_through_the_same_implementation(client, app, fake_passwordless):
    user_id = _sysadmin(client, fake_passwordless, passkeys=("cred-s1",))

    added, s2 = _enroll(client, fake_passwordless, user_id, prefix="/sysadmin")
    assert added.status_code == 200 and added.get_json()["redirect"].endswith("/sysadmin/login")
    assert _bound(user_id) == sorted(["cred-s1", s2])
    seed_sysadmin_session(client, user_id=user_id, username="op_sysadmin")

    replaced, s3 = _replace(client, fake_passwordless, user_id, s2, prefix="/sysadmin")
    assert replaced.status_code == 200
    assert _bound(user_id) == sorted(["cred-s1", s3])
    seed_sysadmin_session(client, user_id=user_id, username="op_sysadmin")

    revoked = _revoke(client, _row_id(s3), prefix="/sysadmin")
    assert revoked.status_code == 200
    assert _bound(user_id) == ["cred-s1"]
    seed_sysadmin_session(client, user_id=user_id, username="op_sysadmin")

    only = _revoke(client, _row_id("cred-s1"), prefix="/sysadmin")
    assert only.status_code == 409 and only.get_json()["code"] == "only_passkey"
    assert {e.actor_type for e in _outcomes()} == {"sysadmin"}
    assert {e.feat_id for e in _outcomes()} == {"FEAT-IDEN-102", "FEAT-IDEN-107"}


def test_a_sysadmin_needs_fresh_totp(client, app, fake_passwordless):
    user_id = _sysadmin(client, fake_passwordless, passkeys=("cred-s1",))

    assert client.post("/sysadmin/passkey/register/start", json={}).status_code == 403
    assert fake_passwordless.calls == [] and _operations(user_id) == []


def test_a_teacher_cannot_reach_the_sysadmin_surface(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))

    assert start_registration(client, prefix="/sysadmin").status_code in (302, 401, 403, 404)
    assert _revoke(client, _row_id("cred-b"), prefix="/sysadmin").status_code in (302, 401, 403, 404)
    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert _operations(user_id) == []
    assert fake_passwordless.calls == []


def test_a_sysadmin_cannot_reach_the_teacher_surface(client, app, fake_passwordless):
    user_id = _sysadmin(client, fake_passwordless, passkeys=("cred-s1", "cred-s2"))

    assert start_registration(client, prefix="/admin").status_code in (302, 401, 403, 404)
    assert _revoke(client, _row_id("cred-s2"), prefix="/admin").status_code in (302, 401, 403, 404)
    assert client.get("/admin/passkey/settings").status_code in (302, 401, 403, 404)
    assert _bound(user_id) == ["cred-s1", "cred-s2"]
    assert _operations(user_id) == []
    assert fake_passwordless.calls == []

    # A real committed retirement with its real binding, resumed over the teacher surface:
    # refused by the surface itself (a 404 operation_not_found would not prove that).
    fake_passwordless.fail_deletes = True
    seed_sysadmin_session(client, user_id=user_id, username="op_sysadmin")
    assert _revoke(client, _row_id("cred-s2"), prefix="/sysadmin").status_code == 503
    fake_passwordless.fail_deletes = False
    (operation,) = _open_operations(user_id)
    binding = lifecycle.registration_binding(operation)
    calls = list(fake_passwordless.calls)

    refused = client.post("/admin/passkey/resume", json={"binding": binding})

    assert refused.status_code in (302, 401, 403)
    assert fake_passwordless.calls == calls  # no provider call was made for the refused request
    (still_open,) = _open_operations(user_id)
    assert still_open.id == operation.id and still_open.stage in lifecycle.RETIREMENT_STAGES
    assert _bound(user_id) == ["cred-s1", "cred-s2"]


def test_a_teacher_with_no_active_class_can_maintain_credentials(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:classless:{uuid.uuid4().hex}"):
        user = _user(user_id)
        user.last_active_class_id = None
        user.last_active_seat_id = None

    assert client.get("/admin/passkey/settings").status_code == 200
    assert _revoke(client, _row_id("cred-b")).status_code == 200
    assert _bound(user_id) == ["cred-a"]


def test_the_session_is_invalidated_after_each_kind_of_completion(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    stale = app.test_client()
    with stale.session_transaction() as sess, client.session_transaction() as source:
        sess.update(dict(source))
    assert stale.get("/admin/passkey/settings").status_code == 200

    assert _revoke(client, _row_id("cred-b")).status_code == 200

    # The browser that completed it and a copy of its cookie are both out.
    assert _signed_out(client)
    assert stale.get("/admin/passkey/settings").status_code in (302, 401)


def test_settings_page_mutates_nothing_and_states_the_state(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert start_registration(client).status_code == 200
    (operation,) = _open_operations(user_id)
    before = (operation.stage, operation.updated_at, _user(user_id).credential_generation)

    with temporal.pinned_clock(temporal.shifted(operation.deadline_at, seconds=1)):
        page = client.get("/admin/passkey/settings")

    assert page.status_code == 200
    (after,) = _operations(user_id)
    assert (after.stage, after.updated_at, _user(user_id).credential_generation) == before


def test_the_settings_page_has_a_labelled_code_input_and_text_states(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))

    html = client.get("/admin/passkey/settings").get_data(as_text=True)

    assert '<label for="passkey-totp-code"' in html and 'id="passkey-totp-code"' in html
    assert 'autocomplete="one-time-code"' in html
    assert "Your only passkey: replace it rather than delete it." in html
    assert "delete-passkey-btn" not in html.split("<script>")[0]  # no Delete offered for the only passkey


def test_the_sysadmin_settings_page_offers_the_same_controls(client, app, fake_passwordless):
    _sysadmin(client, fake_passwordless, passkeys=("cred-s1", "cred-s2"))

    html = client.get("/sysadmin/passkey/settings").get_data(as_text=True)

    assert 'id="passkey-totp-code"' in html and "replace-passkey-btn" in html and "delete-passkey-btn" in html


def test_labels_are_escaped_and_never_become_authority(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    response, _ = _enroll(client, fake_passwordless, user_id, name="<script>alert(1)</script>")
    assert response.status_code == 200
    seed_signed_in = app.test_client()
    with seed_signed_in.session_transaction() as sess:
        sess.update({"user_id": user_id, "role": "admin"})
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:nonce:{uuid.uuid4().hex}"):
        _user(user_id).current_session_nonce = "n"
    with seed_signed_in.session_transaction() as sess:
        sess["current_session_nonce"] = "n"

    html = seed_signed_in.get("/admin/passkey/settings").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


_MUTATIONS = (
    ("POST", "passkey/register/start"),
    ("POST", "passkey/register/finish"),
    ("POST", "passkey/resume"),
    ("POST", "passkey/cancel"),
    ("DELETE", "passkey/1/delete"),
)


@pytest.mark.parametrize("prefix", ["/admin", "/sysadmin"])
def test_every_passkey_mutation_route_is_csrf_protected(app, prefix):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        client = app.test_client()
        for method, path in _MUTATIONS:
            assert client.open(f"{prefix}/{path}", method=method, json={}).status_code == 400, path
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture
def limiter_on(app):
    from app.extensions import limiter
    was_enabled = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = was_enabled


@pytest.mark.parametrize("prefix", ["/admin", "/sysadmin"])
@pytest.mark.parametrize("method,path", _MUTATIONS)
def test_every_passkey_mutation_route_is_rate_limited(
    client, app, fake_passwordless, limiter_on, prefix, method, path,
):
    if prefix == "/admin":
        _teacher(client, app, fake_passwordless)
    else:
        _sysadmin(client, fake_passwordless)

    statuses = [client.open(f"{prefix}/{path}", method=method, json={}).status_code for _ in range(11)]

    assert 429 not in statuses[:10] and statuses[10] == 429


# ---------------------------------------------------------------------------
# structure: commands run only in their FEAT; the old FEAT-OPS-001 paths are gone
# ---------------------------------------------------------------------------

def test_commands_refuse_to_run_outside_their_feat(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    with FEATContext("FEAT-IDEN-107", idempotency_key=f"test:open:{uuid.uuid4().hex}"):
        operation = lifecycle.open_operation(
            _user(user_id), purpose=CredentialOperationPurpose.PASSKEY_REVOKE,
            proof=TotpCode(totp_code()), session_nonce=_nonce(user_id),
        )
        operation_id = operation.id
    for wrong in ("FEAT-IDEN-102", "FEAT-IDEN-106", "FEAT-TEST-SETUP"):
        with FEATContext(wrong, idempotency_key=f"test:wrong:{uuid.uuid4().hex}"):
            with pytest.raises(PermissionError):
                lifecycle.commit_revocation_intent(
                    lifecycle.get_operation_for_user(operation_id, user_id),
                    passkey_id=_row_id("cred-b"), session_nonce=_nonce(user_id),
                )
    with pytest.raises(PermissionError):
        lifecycle.complete_retirement(lifecycle.get_operation_for_user(operation_id, user_id))


def direct_binding_writes(source: str) -> list[int]:
    """Line numbers where ``source`` constructs a ``PasskeyCredential`` or names a removed writer.

    A pure scan over the parsed tree, so it does not depend on keyword order, spacing or
    line breaks: any call to the ``PasskeyCredential`` constructor (bare or attribute
    access) counts, wherever its arguments are.
    """
    import ast
    removed = {"create_admin_credential", "delete_admin_credential"}
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            target = node.func
            name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
            if name == "PasskeyCredential" or name in removed:
                hits.append(node.lineno)
    return hits


def test_no_route_or_service_still_writes_a_passkey_binding_directly():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[3] / "app"
    offenders = [
        str(path.relative_to(root)) for path in root.rglob("*.py")
        if path.name != "credential_lifecycle.py"
        and direct_binding_writes(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
    assert not hasattr(passkey_service, "remove_passkey") and not hasattr(passkey_service, "complete_registration")


def test_mutation_the_scanner_catches_the_constructor_whatever_the_keyword_order():
    violations = [
        "PasskeyCredential(user_id=u, credential_id=c)",
        "PasskeyCredential(credential_id=c, authenticator_name='n', user_id=u)",
        "db.session.add(models.PasskeyCredential(\n    authenticator_name='n',\n    credential_id=c,\n))",
        "PasskeyCredential(**fields)",
        "create_admin_credential(u, c)",
    ]
    for source in violations:
        assert direct_binding_writes(source), source
    # Lawful negative controls: reads, annotations and unrelated names are not writes.
    lawful = [
        "PasskeyCredential.query.filter_by(user_id=u).all()",
        "def f(row: PasskeyCredential) -> None: ...",
        "x = [r for r in rows if isinstance(r, PasskeyCredential)]",
        "# PasskeyCredential(user_id=u)",
    ]
    for source in lawful:
        assert direct_binding_writes(source) == [], source


# ---------------------------------------------------------------------------
# mutation proofs (testing.md Pattern 7): the guard tests above must go red without the fix
# ---------------------------------------------------------------------------

@contextmanager
def _mutant(monkeypatch, module, name, old, new):
    """Replace ``old`` with ``new`` in the source of ``module.name`` for the duration."""
    function = getattr(module, name)
    source = textwrap.dedent(inspect.getsource(function))
    assert source.count(old) == 1, f"{old!r} must occur exactly once in {name}"
    namespace = dict(module.__dict__)
    exec(compile(source.replace(old, new), module.__file__, "exec"), namespace)
    monkeypatch.setattr(module, name, namespace[name])
    yield


def test_mutation_the_only_passkey_guard_is_what_refuses_revocation(client, app, fake_passwordless, monkeypatch):
    with _mutant(monkeypatch, lifecycle, "commit_revocation_intent", "if held < 2:", "if held < 1:"):
        with pytest.raises(AssertionError):
            _check_only_passkey_refused(client, app, fake_passwordless)


def test_mutation_the_generation_recheck_is_what_refuses_stale_completion(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id, old="cred-b")
    _supersede(user_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:reopen:{uuid.uuid4().hex}"):
        # Reopen the cancelled receipt as a stale continuation would see it.
        operation = CredentialOperation.query.filter_by(user_id=user_id).one()
        operation.stage = CredentialOperationStage.RETIREMENT_COMMITTED
    with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:stale:{uuid.uuid4().hex}"):
        with pytest.raises(CredentialOperationRefused) as refused:
            lifecycle.complete_retirement(lifecycle.get_operation_for_user(operation.id, user_id))
    assert refused.value.category == "stale_generation"

    with _mutant(
        monkeypatch, lifecycle, "complete_retirement",
        "if principal.credential_generation != locked.authorized_generation:", "if False:",
    ):
        with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:stale:{uuid.uuid4().hex}"):
            lifecycle.complete_retirement(lifecycle.get_operation_for_user(operation.id, user_id))
    assert _bound(user_id) != ["cred-a", "cred-b"]  # the mutant activated a superseded continuation


def test_mutation_the_receipt_is_what_makes_a_duplicate_completion_inert(client, app, fake_passwordless, monkeypatch):
    with _mutant(
        monkeypatch, lifecycle, "complete_retirement",
        "if locked.stage is CredentialOperationStage.COMPLETED:\n        return ALREADY_COMPLETED",
        "if False:\n        return ALREADY_COMPLETED",
    ):
        with pytest.raises((AssertionError, CredentialOperationRefused)):
            test_a_duplicate_completion_returns_the_stored_outcome_and_repeats_no_effect(
                client, app, fake_passwordless,
            )


def _check_revocation_retires_remotely(client, app, fake):
    _, user_id = _teacher(client, app, fake, passkeys=("cred-a", "cred-b"))

    assert _revoke(client, _row_id("cred-b")).status_code == 200

    assert [c for c in fake.calls if c[0] == "delete_credential"] == [("delete_credential", "cred-b")]
    assert set(fake.credentials) == {"cred-a"}
    assert _bound(user_id) == ["cred-a"]


def test_revocation_retires_the_credential_at_the_provider_not_just_locally(client, app, fake_passwordless):
    _check_revocation_retires_remotely(client, app, fake_passwordless)


def test_mutation_skipping_the_provider_deletion_is_caught(client, app, fake_passwordless, monkeypatch):
    monkeypatch.setattr(passkey_service, "retire_remote_credential", lambda credential_id: None)
    with pytest.raises(AssertionError):
        _check_revocation_retires_remotely(client, app, fake_passwordless)


# ---------------------------------------------------------------------------
# review round: binding, provider not-found, labels, replay, interruption, sysadmin JSON
# ---------------------------------------------------------------------------

def _cancelled_a_then_started_b(client, fake, user_id):
    """Operation A started, its credential registered, then cancelled; operation B started.

    Returns A's ``(token, credential_id, binding)``; ``client.last_registration_binding`` is B's.
    """
    assert start_registration(client).status_code == 200
    binding_a = client.last_registration_binding
    token_a, credential_a = _new_credential(fake, user_id)
    assert client.post("/admin/passkey/cancel", json={}).status_code == 200
    assert start_registration(client).status_code == 200
    assert client.last_registration_binding != binding_a
    return token_a, credential_a, binding_a


def test_a_cancelled_operations_token_cannot_complete_a_later_operation(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    token_a, _, binding_a = _cancelled_a_then_started_b(client, fake_passwordless, user_id)

    response = finish_registration(client, token_a, binding=binding_a)

    assert response.status_code == 409 and response.get_json()["code"] == "binding_mismatch"
    assert _bound(user_id) == ["cred-a"]
    (operation,) = _open_operations(user_id)  # B is untouched and still pending
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING
    assert _signed_out(client) is False


def test_a_finish_without_the_binding_is_refused(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    token, _ = _new_credential(fake_passwordless, user_id)

    missing = client.post("/admin/passkey/register/finish", json={"token": token, "authenticatorName": "x"})
    wrong = finish_registration(client, token, binding="0" * 64)

    assert missing.get_json()["code"] == wrong.get_json()["code"] == "binding_mismatch"
    assert _bound(user_id) == ["cred-a"]


def test_the_binding_belongs_to_the_principal_as_well_as_the_operation(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    (operation,) = _open_operations(user_id)
    other_binding = lifecycle.registration_binding(
        SimpleNamespace(user_id="someone-else", id=operation.id)
    )

    assert other_binding != lifecycle.registration_binding(operation)


def test_mutation_the_binding_check_is_what_refuses_a_cancelled_operations_token(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    token_a, credential_a, binding_a = _cancelled_a_then_started_b(client, fake_passwordless, user_id)

    with monkeypatch.context() as patch:
        patch.setattr(lifecycle, "check_registration_binding", lambda operation, binding: None)
        response = finish_registration(client, token_a, binding=binding_a)

    assert _bound(user_id) != ["cred-a"] or response.status_code != 409  # the mutant lets A's token through


def test_a_provider_not_found_for_the_recorded_credential_counts_as_deleted(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.strict_missing_deletes = True
    operation_id, d = _retirement_committed(client, fake_passwordless, user_id)
    fake_passwordless.credentials.pop("cred-b")  # the provider did delete it; the reply was lost

    response = _resume(client, user_id)

    assert response.status_code == 200, response.get_json()
    assert ("delete_credential", "cred-b") in fake_passwordless.calls
    assert _bound(user_id) == sorted(["cred-a", d])
    assert len(_outcomes()) == 1


def test_any_other_provider_error_keeps_the_retirement_pending(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    fake_passwordless.fail_deletes = True  # a 500, not a not-found

    response = _resume(client, user_id)

    assert response.status_code == 503 and response.get_json()["code"] == "provider_unavailable"
    assert _bound(user_id) == ["cred-a", "cred-b"]


def test_only_a_not_found_confirmed_by_the_inventory_counts_as_deleted(client, app, fake_passwordless):
    """A 404 is convergence only when the provider's own listing no longer holds the credential."""
    from passwordless import PasswordlessError
    from passwordless.errors import PasswordlessProblemDetails

    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    external = passkey_service.passkey_external_id(user_id)

    def failing(status):
        class Client:
            def delete_credential(self, _):
                raise PasswordlessError(PasswordlessProblemDetails(type="t", title="t", status=status, error_code="e"))

            def get_credentials(self, _):
                return []  # absent from the listing
        return Client()

    for status in (400, 401, 403, 409, 429, 500, 503, 504):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(passkey_service, "_client", lambda status=status: failing(status))
            with pytest.raises(passkey_service.PasskeyServiceUnavailable):
                passkey_service.retire_remote_credential("cred-b", user_id)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(passkey_service, "_client", lambda: failing(404))
        assert passkey_service.retire_remote_credential("cred-b", user_id) is None
        # Without a principal there is no inventory to confirm against.
        with pytest.raises(passkey_service.PasskeyServiceUnavailable):
            passkey_service.retire_remote_credential("cred-b")
    assert external


def test_a_generic_404_with_the_credential_still_live_keeps_the_retirement_pending(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.generic_404_deletes = True  # a proxy or wrong path, not the provider
    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 503 and response.get_json()["code"] == "provider_unavailable"
    assert "cred-b" in fake_passwordless.credentials  # still live at the provider
    assert _bound(user_id) == ["cred-a", "cred-b"]  # so the binding is kept
    assert ("get_credentials", passkey_service.passkey_external_id(user_id)) in fake_passwordless.calls
    assert _outcomes() == []

    fake_passwordless.generic_404_deletes = False
    assert _resume(client, user_id).status_code == 200
    assert _bound(user_id) == sorted(["cred-a", d])


def test_a_404_is_not_confirmed_when_the_inventory_cannot_be_read(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.generic_404_deletes = True
    fake_passwordless.credentials.pop("cred-b")  # truly gone, but the listing is down
    fake_passwordless.fail_inventory = True

    response, _ = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 503
    assert _bound(user_id) == ["cred-a", "cred-b"]


def test_mutation_trusting_a_bare_404_would_drop_a_live_credentials_binding(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.generic_404_deletes = True
    monkeypatch.setattr(passkey_service, "_credential_absent_from_inventory", lambda *a, **k: True)

    response, _ = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 200 and "cred-b" in fake_passwordless.credentials  # the mutant's harm


def test_the_resume_form_names_the_replacements_passkey(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _, d = _retirement_committed(client, fake_passwordless, user_id)

    response = _resume(client, user_id, authenticatorName="  Office laptop  ")

    assert response.status_code == 200
    db.session.expire_all()
    assert PasskeyCredential.query.filter_by(credential_id=d).one().authenticator_name == "Office laptop"


def test_a_blank_resume_name_falls_back_to_the_default_label(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _, d = _retirement_committed(client, fake_passwordless, user_id)

    assert _resume(client, user_id).status_code == 200

    db.session.expire_all()
    assert PasskeyCredential.query.filter_by(credential_id=d).one().authenticator_name == "Unnamed Passkey"


@pytest.mark.parametrize("raw, expected", [
    ("  Laptop  ", "Laptop"),
    ("Lap\x00top", "Laptop"),
    ("Tab\there\nnow", "Tabherenow"),
    ("Key‮evil", "Keyevil"),
    ("​\x07   ", "Unnamed Passkey"),
    ("", "Unnamed Passkey"),
    (None, "Unnamed Passkey"),
    (123, "Unnamed Passkey"),
    ("é" * 150, "é" * 100),
    ("a" * 99 + " b", "a" * 99),
])
def test_authenticator_labels_are_normalized(raw, expected):
    assert lifecycle.normalize_authenticator_name(raw) == expected


def test_a_label_with_a_nul_is_stored_clean_and_the_enrollment_succeeds(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))

    response, credential = _enroll(client, fake_passwordless, user_id, name="Pad\x00lock")

    assert response.status_code == 200
    db.session.expire_all()
    assert PasskeyCredential.query.filter_by(credential_id=credential).one().authenticator_name == "Padlock"


def test_a_completed_finish_retried_is_answered_from_the_receipt_and_changes_nothing(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    response, d = _replace(client, fake_passwordless, user_id, "cred-b")
    assert response.status_code == 200
    generation, nonce, outcomes = _user(user_id).credential_generation, _nonce(user_id), len(_outcomes())
    calls = list(fake_passwordless.calls)

    result = feat.finish_registration(
        user_id=user_id, session_nonce=nonce, token="a-retried-token", binding=_latest_binding(user_id),
        authenticator_name="y",
    )

    assert result == ("replaced", True)
    assert fake_passwordless.calls == calls
    assert _bound(user_id) == sorted(["cred-a", d])
    user = _user(user_id)
    assert (user.credential_generation, user.current_session_nonce, len(_outcomes())) == (generation, nonce, outcomes)


def test_a_completed_resume_retried_is_answered_from_the_receipt_and_changes_nothing(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert _revoke(client, _row_id("cred-b")).status_code == 200
    generation, nonce, outcomes = _user(user_id).credential_generation, _nonce(user_id), len(_outcomes())
    calls = list(fake_passwordless.calls)

    assert feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id)) == ("revoked", True)

    assert fake_passwordless.calls == calls and _bound(user_id) == ["cred-a"]
    user = _user(user_id)
    assert (user.credential_generation, user.current_session_nonce, len(_outcomes())) == (generation, nonce, outcomes)


def test_with_no_operation_and_no_receipt_finish_and_resume_are_not_found(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    for call in (
        lambda: feat.finish_registration(user_id=user_id, session_nonce=_nonce(user_id), token="t",
                                         binding="b", authenticator_name="n"),
        lambda: feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id)),
    ):
        with pytest.raises(CredentialOperationRefused) as refused:
            call()
        assert refused.value.category == "operation_not_found"


def test_an_interrupted_registration_is_refused_and_can_be_cancelled_and_restarted(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    assert start_registration(client).status_code == 200
    token, credential = _new_credential(fake_passwordless, user_id)
    def dropped(*args, **kwargs):
        raise RuntimeError("the connection dropped")

    with monkeypatch.context() as patch:
        patch.setattr(lifecycle, "activate_passkey", dropped)
        assert finish_registration(client, token).status_code == 500
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.CANDIDATE_VERIFIED

    retried = finish_registration(client, token)

    assert retried.status_code == 409 and retried.get_json()["code"] == "registration_interrupted"
    assert _bound(user_id) == ["cred-a"]  # the candidate never held authority
    assert client.post("/admin/passkey/cancel", json={}).status_code == 200
    restarted, new_credential = _enroll(client, fake_passwordless, user_id)
    assert restarted.status_code == 200
    assert _bound(user_id) == sorted(["cred-a", new_credential])
    assert credential not in _bound(user_id)


def test_the_sysadmin_surface_answers_background_requests_with_json_401(client, app):
    start = client.post("/sysadmin/passkey/register/start", json={"totp_code": "000000"})
    revoke = client.delete("/sysadmin/passkey/1/delete", json={"totp_code": "000000"})

    for response in (start, revoke):
        assert response.status_code == 401
        assert response.get_json()["error"] == "authentication_required"
    navigation = client.get("/sysadmin/passkey/settings")
    assert navigation.status_code == 302 and "/sysadmin/login" in navigation.headers["Location"]


# ---------------------------------------------------------------------------
# review round 3: operation identity in the registration, receipts per operation
# ---------------------------------------------------------------------------

def test_a_cancelled_operations_registration_cannot_be_activated_under_a_later_operation(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    token_a, credential_a, _ = _cancelled_a_then_started_b(client, fake_passwordless, user_id)
    binding_b = client.last_registration_binding

    # A's provider result with B's own binding: the nickname A's registration carries is A's.
    response = finish_registration(client, token_a, binding=binding_b)

    assert response.status_code == 409 and response.get_json()["code"] == "binding_mismatch"
    assert _bound(user_id) == ["cred-a"]
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING
    assert operation.new_credential_id is None
    assert _signed_out(client) is False


def test_a_cancelled_operations_registration_cannot_become_a_replacement_under_a_later_operation(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert start_registration(client).status_code == 200
    token_a, credential_a = _new_credential(fake_passwordless, user_id)
    assert client.post("/admin/passkey/cancel", json={}).status_code == 200
    assert start_registration(client, replace_passkey_id=_row_id("cred-b")).status_code == 200

    response = finish_registration(client, token_a)  # B's binding, A's registration

    assert response.status_code == 409 and response.get_json()["code"] == "binding_mismatch"
    assert _bound(user_id) == ["cred-a", "cred-b"]
    assert "cred-b" in fake_passwordless.credentials
    assert ("delete_credential", "cred-b") not in fake_passwordless.calls


def test_mutation_the_provider_returned_nickname_is_what_ties_a_registration_to_its_operation(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    token_a, credential_a, _ = _cancelled_a_then_started_b(client, fake_passwordless, user_id)
    binding_b = client.last_registration_binding
    # Only the candidate-recording (nickname) check is removed; the echoed-binding comparison stays.
    monkeypatch.setattr(lifecycle, "check_registered_nickname", lambda operation, nickname: None)

    wrong_echo = finish_registration(client, token_a, binding="0" * 64)
    assert wrong_echo.status_code == 409 and wrong_echo.get_json()["code"] == "binding_mismatch"
    assert credential_a not in _bound(user_id)

    response = finish_registration(client, token_a, binding=binding_b)

    assert response.status_code == 200 and credential_a in _bound(user_id)  # the mutant activates A's credential


def _two_completed(client, app, fake):
    """A replacement completed (its receipt kept); returns the principal and that operation's binding."""
    _, user_id = _teacher(client, app, fake, passkeys=("cred-a", "cred-b"))
    response, _ = _replace(client, fake, user_id, "cred-b")
    assert response.status_code == 200
    return user_id, _latest_binding(user_id)


def test_a_delayed_finish_for_a_cancelled_registration_is_not_answered_from_an_earlier_receipt(
    client, app, fake_passwordless,
):
    user_id, completed_binding = _two_completed(client, app, fake_passwordless)
    # A later registration that was started and then cancelled (a direct FEAT run; the page's sign-in ended).
    nonce = _nonce(user_id)
    started = feat.start_registration(
        user_id=user_id, session_nonce=nonce, proof=lifecycle.TotpCode(totp_code()),
        alias="later", display_name="Later",
    )
    cancelled_binding = started[1]
    assert feat.cancel_registration(user_id=user_id, session_nonce=nonce) is True
    outcomes = len(_outcomes())

    with pytest.raises(CredentialOperationRefused) as refused:
        feat.finish_registration(
            user_id=user_id, session_nonce=nonce, token="t", binding=cancelled_binding, authenticator_name="n",
        )

    assert refused.value.category == "operation_not_found"
    assert len(_outcomes()) == outcomes
    # The completed operation's own retry is still answered from its receipt.
    assert feat.finish_registration(
        user_id=user_id, session_nonce=nonce, token="t", binding=completed_binding, authenticator_name="n",
    ) == ("replaced", True)


def test_a_delayed_resume_is_answered_only_from_its_own_operations_receipt(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    assert _revoke(client, _row_id("cred-b")).status_code == 200
    revoked_binding = _latest_binding(user_id)
    nonce = _nonce(user_id)
    feat.start_registration(
        user_id=user_id, session_nonce=nonce, proof=lifecycle.TotpCode(totp_code()),
        alias="later", display_name="Later",
    )
    other_binding = _latest_binding(user_id)
    assert feat.cancel_registration(user_id=user_id, session_nonce=nonce) is True

    with pytest.raises(CredentialOperationRefused) as refused:
        feat.resume_retirement(user_id=user_id, binding=other_binding)
    assert refused.value.category == "operation_not_found"
    with pytest.raises(CredentialOperationRefused) as unknown:
        feat.resume_retirement(user_id=user_id, binding="0" * 64)
    assert unknown.value.category == "operation_not_found"
    assert feat.resume_retirement(user_id=user_id, binding=revoked_binding) == ("revoked", True)


def test_a_resume_naming_another_operation_is_refused_while_one_is_open(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)

    response = client.post("/admin/passkey/resume", json={"binding": "0" * 64})

    assert response.status_code == 409 and response.get_json()["code"] == "binding_mismatch"
    assert _bound(user_id) == ["cred-a", "cred-b"]


def test_the_settings_page_carries_the_open_operations_binding_for_its_retry_control(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)

    page = client.get("/admin/passkey/settings").get_data(as_text=True)

    assert f'data-binding="{_latest_binding(user_id)}"' in page
    assert "loginUrl" in page


def test_the_expired_session_answer_is_json_with_a_message_the_client_shows(client, app, fake_passwordless):
    """The shape passkey.js relies on: ``error`` (a code), ``message`` (shown), HTTP 401, on finish and delete."""
    for prefix in ("/admin", "/sysadmin"):
        finish = client.post(f"{prefix}/passkey/register/finish", json={"token": "t", "binding": "b"})
        delete = client.delete(f"{prefix}/passkey/1/delete", json={"totp_code": "000000"})
        for response in (finish, delete):
            body = response.get_json()
            assert response.status_code == 401
            assert body["error"] == "authentication_required"
            assert isinstance(body["message"], str) and body["message"]


def test_the_client_sends_an_expired_session_to_sign_in_and_leaves_a_failed_ceremony_pending():
    """Behavior of static/js/passkey.js under stubbed window/document/fetch (a Node harness)."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    root = pathlib.Path(__file__).resolve().parents[3]
    run = subprocess.run(
        [node, str(root / "tests" / "js" / "passkey_behavior_harness.js"), str(root / "static" / "js" / "passkey.js")],
        capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)

    # A JSON 401 shows the server's message and navigates to the sign-in page.
    assert report["unauthorized"]["hrefs"] == ["/admin/login"]
    assert report["unauthorized"]["body"] == ["Your session ended. Sign in again."]
    assert report["unauthorized"]["reloads"] == 0
    # A failed ceremony is shown, sends no automatic cancel request, and reloads (after the delay)
    # so the page renders the pending operation with its Cancel control.
    assert report["ceremonyFailure"]["urls"] == ["/start"]
    assert report["ceremonyFailure"]["reloads"] == 1
    assert report["ceremonyFailure"]["body"] == ["ceremony failed"]


def test_a_completed_receipt_past_its_deadline_is_no_longer_replayed(client, app, fake_passwordless):
    user_id, binding = _two_completed(client, app, fake_passwordless)
    (receipt,) = [o for o in _operations(user_id) if o.stage is CredentialOperationStage.COMPLETED]
    nonce = _nonce(user_id)

    with temporal.pinned_clock(temporal.shifted(receipt.deadline_at, seconds=-1)):
        assert feat.resume_retirement(user_id=user_id, binding=binding) == ("replaced", True)
    with temporal.pinned_clock(temporal.shifted(receipt.deadline_at, seconds=1)):
        with pytest.raises(CredentialOperationRefused) as finish:
            feat.finish_registration(
                user_id=user_id, session_nonce=nonce, token="t", binding=binding, authenticator_name="n",
            )
        with pytest.raises(CredentialOperationRefused) as resume:
            feat.resume_retirement(user_id=user_id, binding=binding)
    assert finish.value.category == resume.value.category == "operation_not_found"


def test_a_committed_retirement_still_resumes_after_its_deadline_despite_the_receipt_cutoff(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _, d = _retirement_committed(client, fake_passwordless, user_id)
    deadline = _operations(user_id)[0].deadline_at

    with temporal.pinned_clock(temporal.shifted(deadline, seconds=60)):
        result = feat.resume_retirement(user_id=user_id, binding=_latest_binding(user_id))

    assert result == ("replaced", False) and d in _bound(user_id)


def test_a_resume_that_loses_the_race_to_a_concurrent_completion_is_a_replay(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    binding = _latest_binding(user_id)
    real_retire = passkey_service.retire_remote_credential
    raced = []

    def retire_then_lose_the_race(credential_id, user_id_=None):
        real_retire(credential_id, user_id_)
        if not raced:
            raced.append(True)  # the other request commits while this one is at the provider
            (open_operation,) = _open_operations(user_id)
            with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:race:{uuid.uuid4().hex}"):
                lifecycle.complete_retirement(
                    db.session.get(CredentialOperation, open_operation.id), authenticator_name="Other",
                )

    monkeypatch.setattr(passkey_service, "retire_remote_credential", retire_then_lose_the_race)

    result = feat.resume_retirement(user_id=user_id, binding=binding)

    assert result == ("replaced", True)


def test_the_route_does_not_rotate_the_session_for_a_resume_that_only_replayed(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    binding = _latest_binding(user_id)
    real_retire = passkey_service.retire_remote_credential

    def retire_then_lose_the_race(credential_id, user_id_=None):
        real_retire(credential_id, user_id_)
        (open_operation,) = _open_operations(user_id)
        with FEATContext("FEAT-IDEN-102", idempotency_key=f"test:race:{uuid.uuid4().hex}"):
            lifecycle.complete_retirement(db.session.get(CredentialOperation, open_operation.id), authenticator_name="Other")

    monkeypatch.setattr(passkey_service, "retire_remote_credential", retire_then_lose_the_race)
    outcomes = len(_outcomes())

    response = client.post("/admin/passkey/resume", json={"binding": binding})

    assert response.status_code == 200 and response.get_json()["success"] is True
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id  # a replay does not clear the cookie as a committed change does
    assert len(_outcomes()) == outcomes + 1  # only the request that committed emitted an outcome


def test_the_settings_page_renders_state_and_binding_from_one_operation_lookup(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    expected = _latest_binding(user_id)
    real = lifecycle.get_open_operation
    calls = []

    def completed_after_the_first_read(uid):
        calls.append(uid)
        return real(uid) if len(calls) == 1 else None  # another request completes it in between

    monkeypatch.setattr(lifecycle, "get_open_operation", completed_after_the_first_read)

    page = client.get("/admin/passkey/settings").get_data(as_text=True)

    assert 'id="resumePasskeyButton"' in page
    assert f'data-binding="{expected}"' in page  # never an empty binding beside the retry control


@pytest.mark.parametrize("malformed", ["\ud800" * 64, "\ud800", "A" * 64, "0" * 63, "0" * 64 + "\n", "é" * 64])
def test_a_malformed_binding_is_an_ordinary_refusal_never_an_error(client, app, fake_passwordless, malformed):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    assert start_registration(client).status_code == 200
    finish = finish_registration(client, "t", binding=malformed)
    cancel = client.post("/admin/passkey/cancel", json={"binding": malformed})
    assert finish.status_code == 409 and finish.get_json()["code"] == "binding_mismatch"
    assert cancel.status_code == 409 and cancel.get_json()["code"] == "binding_mismatch"
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING
    assert client.post("/admin/passkey/cancel", json={"binding": _latest_binding(user_id)}).status_code == 200

    _retirement_committed(client, fake_passwordless, user_id)
    resume = client.post("/admin/passkey/resume", json={"binding": malformed})
    assert resume.status_code == 409 and resume.get_json()["code"] == "binding_mismatch"
    assert len(_open_operations(user_id)) == 1  # the committed retirement was not touched

    assert client.post("/admin/passkey/resume", json={"binding": _latest_binding(user_id)}).status_code == 200
    # A completed receipt cannot be named by a malformed value either (not found, not an error).
    assert lifecycle.receipt_outcome_for_binding(
        user_id, malformed, CredentialOperationPurpose.PASSKEY_REPLACE,
    ) is None


# ---------------------------------------------------------------------------
# principal reconciliation at the lifecycle boundaries (FEAT-IDEN-108 §VI)
# ---------------------------------------------------------------------------

def _reconciliation_outcomes(monkeypatch):
    """The non-identifying reconciliation outcome categories emitted, in order (the audit row holds only a digest)."""
    seen = []
    real = lifecycle._emit_outcome

    def spy(**kwargs):
        if kwargs["action"] == "ACT-IDEN-108":
            seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(lifecycle, "_emit_outcome", spy)
    return seen


def _deletes(fake):
    return [c[1] for c in fake.calls if c[0] == "delete_credential"]


def _stray(fake, user_id, credential_id="stray-1"):
    """A credential the provider holds for the principal that no local state accounts for."""
    fake.credentials[credential_id] = passkey_external_id(user_id)
    return credential_id


def test_a_stray_provider_credential_is_retired_during_enrollment_and_the_new_one_activates(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)

    response, new = _enroll(client, fake_passwordless, user_id)

    assert response.status_code == 200
    assert _deletes(fake_passwordless) == [stray]  # the candidate and the active binding are never deleted
    assert set(fake_passwordless.credentials) == {"cred-a", new}
    assert _bound(user_id) == sorted(["cred-a", new])
    assert [o["outcome"] for o in outcomes] == ["reconciliation_provider_only_retired"]
    payload = json.dumps(outcomes, default=str)
    for identifying in (user_id, stray, new, "cred-a", passkey_external_id(user_id)):
        assert identifying not in payload


def test_mutation_without_the_reconciliation_call_the_stray_survives(
    client, app, fake_passwordless, monkeypatch,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    monkeypatch.setattr(feat, "_reconcile_principal", lambda *a, **k: None)

    assert _enroll(client, fake_passwordless, user_id)[0].status_code == 200

    assert stray in fake_passwordless.credentials and _deletes(fake_passwordless) == []


def test_reconciliation_never_reaches_another_principals_credentials(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    other = initialize("biology_block_a", app).teacher_user.id
    assert other != user_id
    give_totp_seed(other)
    record_passkey(other, "other-bound", fake_passwordless)
    _stray(fake_passwordless, other, "other-stray")
    stray = _stray(fake_passwordless, user_id)

    assert _enroll(client, fake_passwordless, user_id)[0].status_code == 200

    assert _deletes(fake_passwordless) == [stray]
    assert {"other-bound", "other-stray"} <= set(fake_passwordless.credentials)
    assert _bound(other) == ["other-bound"]
    listed = {c[1] for c in fake_passwordless.calls if c[0] == "get_credentials"}
    assert listed == {passkey_external_id(user_id)}


def test_replacement_retires_a_stray_and_keeps_a_and_c_and_the_new_credential(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    stray = _stray(fake_passwordless, user_id)

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 200, response.get_json()
    assert _deletes(fake_passwordless) == ["cred-b", stray]
    assert set(fake_passwordless.credentials) == {"cred-a", "cred-c", d}
    assert _bound(user_id) == sorted(["cred-a", "cred-c", d])
    # The retiring credential's remote absence is the intended effect, not a discrepancy.
    assert [o["outcome"] for o in outcomes] == ["reconciliation_provider_only_retired"]


def test_a_clean_replacement_emits_only_its_own_outcome(client, app, fake_passwordless, monkeypatch):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))

    assert _replace(client, fake_passwordless, user_id, "cred-b")[0].status_code == 200

    assert outcomes == [] and len(_outcomes()) == 1


def test_an_unusable_inventory_withholds_deletion_but_the_replacement_completes(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    stray = _stray(fake_passwordless, user_id)
    fake_passwordless.fail_inventory = True

    response, d = _replace(client, fake_passwordless, user_id, "cred-b")

    assert response.status_code == 200, response.get_json()
    assert _deletes(fake_passwordless) == ["cred-b"]  # only the recorded old credential
    assert stray in fake_passwordless.credentials
    assert _bound(user_id) == sorted(["cred-a", d])
    assert [o["outcome"] for o in outcomes] == ["reconciliation_inventory_unusable"]


@pytest.mark.parametrize("reply", [None, [object()], [SimpleNamespace(descriptor=SimpleNamespace(id=""))],
                                   [SimpleNamespace(descriptor=SimpleNamespace(id=7))]])
def test_a_malformed_inventory_is_never_read_as_empty_and_enrollment_still_activates(
    client, app, fake_passwordless, monkeypatch, reply,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    monkeypatch.setattr(fake_passwordless, "get_credentials", lambda _id: reply)

    response, new = _enroll(client, fake_passwordless, user_id)

    assert response.status_code == 200
    assert _deletes(fake_passwordless) == [] and stray in fake_passwordless.credentials
    assert _bound(user_id) == sorted(["cred-a", new])
    assert [o["outcome"] for o in outcomes] == ["reconciliation_inventory_unusable"]


def test_an_unconfirmed_stray_deletion_is_reported_and_does_not_block_enrollment(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    fake_passwordless.fail_deletes = True

    response, new = _enroll(client, fake_passwordless, user_id)

    assert response.status_code == 200
    assert _deletes(fake_passwordless) == [stray]  # attempted once, not assumed to have worked
    assert stray in fake_passwordless.credentials
    assert _bound(user_id) == sorted(["cred-a", new])
    assert [o["outcome"] for o in outcomes] == ["reconciliation_delete_unconfirmed"]


def test_an_active_binding_missing_remotely_is_reported_and_never_deleted_or_recreated(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.credentials.pop("cred-a")

    response, new = _enroll(client, fake_passwordless, user_id)

    assert response.status_code == 200
    assert _bound(user_id) == sorted(["cred-a", "cred-b", new])  # the local row survives
    assert "cred-a" not in fake_passwordless.credentials  # and nothing recreated it remotely
    assert _deletes(fake_passwordless) == []
    assert [o["outcome"] for o in outcomes] == ["reconciliation_active_absent_remotely"]


def test_an_empty_inventory_for_a_principal_with_bindings_deletes_nothing(
    client, app, fake_passwordless, monkeypatch,
):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    fake_passwordless.credentials.pop("cred-a")
    fake_passwordless.credentials.pop("cred-b")

    response, new = _replace(client, fake_passwordless, user_id, "cred-b")  # delete of cred-b: 200 on the fake

    assert response.status_code == 200
    assert _bound(user_id) == sorted(["cred-a", new])
    assert [o["outcome"] for o in outcomes] == ["reconciliation_active_absent_remotely"]


def test_revocation_retires_a_stray_and_keeps_the_other_passkeys(client, app, fake_passwordless, monkeypatch):
    outcomes = _reconciliation_outcomes(monkeypatch)
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b", "cred-c"))
    stray = _stray(fake_passwordless, user_id)

    response = _revoke(client, _row_id("cred-b"))

    assert response.status_code == 200, response.get_json()
    assert _deletes(fake_passwordless) == ["cred-b", stray]
    assert set(fake_passwordless.credentials) == {"cred-a", "cred-c"}
    assert _bound(user_id) == ["cred-a", "cred-c"]
    assert [o["outcome"] for o in outcomes] == ["reconciliation_provider_only_retired"]


def test_a_resumed_retirement_reconciles_before_it_completes(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a", "cred-b"))
    _retirement_committed(client, fake_passwordless, user_id)
    stray = _stray(fake_passwordless, user_id)

    assert _resume(client, user_id).status_code == 200

    assert stray not in fake_passwordless.credentials
    assert _deletes(fake_passwordless)[-1] == stray


def test_the_inventory_is_read_and_strays_deleted_with_no_transaction_open(client, app, fake_passwordless):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    open_during = []
    for name in ("get_credentials", "delete_credential"):
        original = getattr(fake_passwordless, name)

        def spy(arg, _original=original, _name=name):
            open_during.append((_name, db.session().in_transaction()))
            return _original(arg)

        setattr(fake_passwordless, name, spy)

    _enroll(client, fake_passwordless, user_id)

    assert open_during == [("get_credentials", False), ("delete_credential", False)]
    assert stray not in fake_passwordless.credentials


def test_a_superseded_operation_deletes_nothing(client, app, fake_passwordless, monkeypatch):
    """Supersession (generation bump and cancellation) is rechecked from local state before a destructive action."""
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    real = passkey_service.list_credential_ids

    def list_then_supersede(uid):
        ids = real(uid)
        _supersede(uid)  # a recovery lands while the provider is being read: the owning command
        return ids

    monkeypatch.setattr(passkey_service, "list_credential_ids", list_then_supersede)

    response, _ = _enroll(client, fake_passwordless, user_id)

    assert response.status_code != 200
    assert _deletes(fake_passwordless) == [] and stray in fake_passwordless.credentials
    assert _bound(user_id) == ["cred-a"]


def test_a_credential_bound_locally_while_the_inventory_was_read_is_not_deleted(
    client, app, fake_passwordless, monkeypatch,
):
    """Revalidation sees local authority gained since the inventory: a stray that became bound is protected."""
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    stray = _stray(fake_passwordless, user_id)
    real = passkey_service.list_credential_ids

    def list_then_bind(uid):
        ids = real(uid)
        record_passkey(uid, stray, None)
        return ids

    monkeypatch.setattr(passkey_service, "list_credential_ids", list_then_bind)

    _enroll(client, fake_passwordless, user_id)

    assert _deletes(fake_passwordless) == [] and stray in fake_passwordless.credentials


def test_an_enrollment_with_an_unknown_pending_credential_defers_every_provider_only_entry(
    client, app, fake_passwordless,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    _stray(fake_passwordless, user_id)
    assert start_registration(client).status_code == 200
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING

    scope = lifecycle.reconciliation_scope(operation)
    db.session.rollback()

    assert scope.pending_registration_unknown is True and scope.pending_id is None
    assert lifecycle.reconciliation_target_is_still_provider_only(operation, "stray-1") is False
    db.session.rollback()


def test_a_malformed_inventory_entry_never_confirms_a_404_as_deleted(client, app, fake_passwordless, monkeypatch):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    monkeypatch.setattr(
        fake_passwordless, "get_credentials",
        lambda _id: [SimpleNamespace(descriptor=SimpleNamespace(id=None))],
    )

    assert passkey_service._credential_absent_from_inventory("None", user_id) is False
    assert passkey_service._credential_absent_from_inventory("cred-gone", user_id) is False
    monkeypatch.setattr(fake_passwordless, "get_credentials", lambda _id: [])
    assert passkey_service._credential_absent_from_inventory("cred-gone", user_id) is True
