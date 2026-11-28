"""TOTP seed length, credential compliance and TOTP-replacement operations.

SPEC-SEC-001 §V.1 item 7: a stored seed below 112 bits is noncompliant and every
new seed is 160 bits from one generator. SPEC-IDEN-002 / FEAT-IDEN-106: a TOTP is
replaced only through an operation proven by a fresh passkey assertion, and the
old secret survives everything short of a verified activation.

CTH has minted 160-bit seeds since it first pinned pyotp 2.9.0, so no enrolled seed
is expected to be short. The 16-character seed ``SHORT_SEED`` below is a synthetic
fixture for the noncompliant branch only: ``pyotp`` 2.12 refuses to construct a
``TOTP`` from it, so the tests classify it by length and never sign with it. Every
test that needs a working authenticator holds a 160-bit seed.
"""

from __future__ import annotations

import ast
import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pyotp
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.feats.base import FEATContext
from app.feats.credential_operations_feat import (
    activate_totp_replacement,
    authorize_totp_replacement,
    cancel_totp_replacement,
    expire_credential_operations,
    hold_totp_candidate,
    issue_totp_replacement_challenge,
    open_credential_operation,
)
from app.models import (
    AuditEvent,
    CredentialOperation,
    CredentialOperationPurpose,
    CredentialOperationStage,
    PasskeyCredential,
    User,
)
from app.services import credential_lifecycle as lifecycle
from app.services.credential_lifecycle import (
    CredentialCompliance,
    CredentialOperationRefused,
    TotpCode,
    credential_compliance,
    decoded_secret_bits,
    mint_totp_secret,
)
from app.services.passkey_service import PasskeyError
from app.utils.encryption import decrypt_totp, encrypt_totp
from app.utils.user_ids import parse_passkey_external_id, passkey_external_id
from tests.dom.identity.test_teacher_recovery_completion import (  # noqa: F401
    finish as recovery_finish, recovery, setup as recovery_setup,
)
from tests.helpers import temporal
from tests.helpers.canonical_classroom import _teacher_key_for
from tests.helpers.canonical_identities import TEACHERS
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.passkey import fake_passwordless  # noqa: F401  (fixture)

# Sixteen base32 characters: 80 bits. Synthetic and below the SPEC-SEC-001 §V.1
# item 7 floor; pyotp >= 2.12 cannot build a TOTP from it, so it is only ever stored
# and measured.
SHORT_SEED = "JBSWY3DPEHPK3PXP"
SEED_20 = "JBSWY3DPEHPK3PXPJBSQ"
SEED_32 = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
# The seed a signed-in teacher holds in these tests: 160 bits, distinct from SEED_32.
HELD_SEED = "KRSXG5CTMVRXEZLUKN2XAZLSMRSXGZLT"

REPO = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _code(secret, instant=None):
    """The code for ``secret`` at the resolver's instant (never the wall clock)."""
    return pyotp.TOTP(secret).at(instant or temporal.now())


def _accepted(secret, instant=None):
    """Every code the verifier accepts at ``instant``: previous, current and next step."""
    instant = instant or temporal.now()
    return {pyotp.TOTP(secret).at(instant, counter_offset=k) for k in (-1, 0, 1)}


def _wrong_code(*secrets):
    """A six-digit code outside all three accepted steps of every given seed."""
    taken = set().union(*(_accepted(secret) for secret in secrets))
    return next(f"{n:06d}" for n in range(1000000) if f"{n:06d}" not in taken)


# A fixed instant at which the legacy and candidate seeds below share no accepted code.
FIXED_INSTANT = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


def _set_seed(user_id, secret):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:seed:{uuid.uuid4().hex}"):
        db.session.get(User, user_id).totp_secret_encrypted = encrypt_totp(secret)


def _add_passkey(user_id, credential_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:passkey:{uuid.uuid4().hex}"):
        db.session.add(PasskeyCredential(user_id=user_id, credential_id=credential_id, authenticator_name="Key"))


def _user(user_id):
    return db.session.query(User).filter_by(id=user_id).populate_existing().one()


def _operation(operation_id):
    return db.session.query(CredentialOperation).filter_by(id=operation_id).populate_existing().one()


def _nonce(user_id):
    return _user(user_id).current_session_nonce


def _stored_seed(user_id):
    return _user(user_id).totp_secret_encrypted


def _enrolled_teacher(client, app, fake, key="chemistry_p1", seed=HELD_SEED, credential="cred-1", passkey=True):
    """A signed-in teacher holding ``seed`` and (unless ``passkey`` is false) one activated passkey."""
    classroom = initialize_as_teacher(key, client, app)
    user_id = classroom.teacher_user.id
    _set_seed(user_id, seed)
    if passkey:
        _add_passkey(user_id, credential)
        fake.credentials[credential] = passkey_external_id(user_id)
    return classroom, user_id


def _challenge(user_id, purpose="totp_replace", nonce=None):
    """A stateless (HMAC) step-up challenge: retained for TOTP-authorized passkey work, not TOTP replacement."""
    return lifecycle.issue_step_up_challenge(
        _user(user_id), purpose=CredentialOperationPurpose(purpose), session_nonce=nonce or _nonce(user_id),
    )


def _open_replacement(user_id, fake, credential="cred-1", nonce=None, **token_options):
    """Authorize a TOTP replacement the way the browser does: a stored challenge, then step-up evidence."""
    nonce = nonce or _nonce(user_id)
    challenge = issue_totp_replacement_challenge(user_id=user_id, session_nonce=nonce)
    token = fake.step_up_token(credential, **token_options)
    return authorize_totp_replacement(
        user_id=user_id, session_nonce=nonce, token=token, challenge=challenge,
    )


def _live_operations(user_id=None):
    db.session.expire_all()
    return [o for o in CredentialOperation.query.all()
            if o.stage not in (CredentialOperationStage.COMPLETED, CredentialOperationStage.CANCELLED)]


def _hold(user_id, operation_id, nonce=None):
    return hold_totp_candidate(
        user_id=user_id, operation_id=operation_id,
        session_nonce=nonce or _nonce(user_id), account_name="teacher",
    )


def _activate(user_id, operation_id, code, nonce=None):
    return activate_totp_replacement(
        user_id=user_id, operation_id=operation_id, code=code, session_nonce=nonce or _nonce(user_id),
    )


def _outcome_events():
    return AuditEvent.query.filter_by(table_name="credential_lifecycle_outcome").all()


# ---------------------------------------------------------------------------
# the pinned pyotp enforces the floor; compliance is derived from live state
# ---------------------------------------------------------------------------

def test_a_160_bit_seed_signs_in(client, app):
    classroom = initialize("chemistry_p1", app)
    user_id = classroom.teacher_user.id
    _set_seed(user_id, HELD_SEED)
    assert len(HELD_SEED) == 32
    username = TEACHERS[_teacher_key_for(classroom)]["username"]

    response = client.post(
        "/admin/login", data={"username": username, "totp_code": _code(HELD_SEED)},
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == user_id


def test_the_pinned_pyotp_refuses_a_seed_below_the_floor():
    """The dependency pin is what enforces SPEC-SEC-001 §V.1 item 7 at sign-in."""
    assert len(SHORT_SEED) == 16
    with pytest.raises(ValueError):
        pyotp.TOTP(SHORT_SEED)
    pyotp.TOTP(HELD_SEED)


def test_a_sub_floor_seed_does_not_sign_in(client, app, monkeypatch):
    """The login route reaches ``pyotp.TOTP(seed)``, the constructor raises, and the
    handler answers with the ordinary invalid-code response (no 500, no session)."""
    from app.routes import admin as admin_routes

    classroom = initialize("chemistry_p1", app)
    user_id = classroom.teacher_user.id
    _set_seed(user_id, SHORT_SEED)
    username = TEACHERS[_teacher_key_for(classroom)]["username"]

    real_totp = pyotp.TOTP
    calls = []

    def recording_totp(secret, *args, **kwargs):
        try:
            return real_totp(secret, *args, **kwargs)
        except ValueError as error:
            calls.append((secret, error))
            raise

    monkeypatch.setattr(admin_routes.pyotp, "TOTP", recording_totp)

    response = client.post("/admin/login", data={"username": username, "totp_code": "123456"})

    assert [secret for secret, _ in calls] == [SHORT_SEED]
    assert isinstance(calls[0][1], ValueError)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/admin/login")
    with client.session_transaction() as sess:
        assert sess.get("user_id") != user_id
        assert ("error", "Invalid credentials or TOTP code.") in sess.get("_flashes", [])


def test_short_seed_is_reported_noncompliant(client, app):
    classroom = initialize("chemistry_p1", app)
    user_id = classroom.teacher_user.id
    _set_seed(user_id, SHORT_SEED)

    assert decoded_secret_bits(_user(user_id)) == 80
    # Order proof: the passkey is reported before the seed.
    assert credential_compliance(_user(user_id)) is CredentialCompliance.PASSKEY_MISSING
    _add_passkey(user_id, "cred-1")
    assert credential_compliance(_user(user_id)) is CredentialCompliance.TOTP_NONCOMPLIANT
    _set_seed(user_id, mint_totp_secret())
    assert credential_compliance(_user(user_id)) is CredentialCompliance.COMPLIANT


def test_a_compliant_seed_without_a_passkey_is_passkey_missing(client, app):
    classroom = initialize("chemistry_p1", app)
    user_id = classroom.teacher_user.id
    _set_seed(user_id, mint_totp_secret())

    assert credential_compliance(_user(user_id)) is CredentialCompliance.PASSKEY_MISSING


def test_compliance_is_not_stored(client, app):
    """No completion flag: the only inputs are the passkey table and the seed."""
    columns = {c.name for c in User.__table__.columns}
    assert not {c for c in columns if "compliance" in c or "compliant" in c}


@pytest.mark.parametrize("seed, bits", [(SHORT_SEED, 80), (SEED_20, 100), (SEED_32, 160)])
def test_decoded_secret_bits_by_seed_length(seed, bits):
    """Mutation proof: the measure tracks length, so a floor change cannot hide."""
    assert decoded_secret_bits(SimpleNamespace(totp_secret_encrypted=encrypt_totp(seed))) == bits


@pytest.mark.parametrize("stored", [None, "", "not-an-encrypted-seed"])
def test_decoded_secret_bits_fails_closed_on_missing_or_unreadable_seed(stored):
    assert decoded_secret_bits(SimpleNamespace(totp_secret_encrypted=stored)) == 0


def test_decoded_secret_bits_rejects_a_non_base32_seed():
    assert decoded_secret_bits(SimpleNamespace(totp_secret_encrypted=encrypt_totp("!!!!!!!!!!!!!!!!"))) == 0


def test_the_floor_sits_between_the_short_and_generated_lengths():
    assert lifecycle.TOTP_MIN_SEED_BITS == 112
    assert lifecycle.TOTP_GENERATED_SEED_BITS == 160
    assert 80 < lifecycle.TOTP_MIN_SEED_BITS <= lifecycle.TOTP_GENERATED_SEED_BITS


# ---------------------------------------------------------------------------
# fresh seeds are 160 bits, from one generator
# ---------------------------------------------------------------------------

def _is_160_bit_base32(secret):
    return len(secret) == 32 and len(base64.b32decode(secret)) * 8 == 160


def test_mint_asks_for_its_length_rather_than_trusting_the_library_default(monkeypatch):
    """Mutation proof: a library whose default length is 80 bits must still yield 160.

    pyotp's default has changed between releases (16 characters before 2.4.0, 32
    since), so the generator states the length itself.
    """
    monkeypatch.setattr(lifecycle.pyotp, "random_base32", lambda length=16, chars=None: "A" * length)

    assert len(mint_totp_secret()) == 32


def test_fresh_seed_is_160_bits(app, recovery):  # noqa: F811
    from app.feats.teacher_signup_feat import prepare_totp, stage_signup
    from app.services.identity_service import create_system_principal

    assert _is_160_bit_base32(mint_totp_secret())

    metadata = dict(class_display_name="Physics", section="A", class_timezone="America/Los_Angeles",
                    teacher_first_name="First", teacher_last_name="Last")
    nonce = stage_signup(previous_nonce=None, metadata=metadata, correlation_id="seed-test",
                         idempotency_key="seed-test:stage")
    signup_secret = prepare_totp(nonce=nonce, username="seed_signup", correlation_id="seed-test",
                                 idempotency_key="seed-test:prepare")
    assert _is_160_bit_base32(signup_secret)

    recovery_secret = recovery_setup(recovery)["secret"]
    assert _is_160_bit_base32(recovery_secret)

    with FEATContext("FEAT-IDEN-008", idempotency_key="seed-test:sysadmin"):
        sysadmin_secret = create_system_principal("seed_sysadmin")
    assert _is_160_bit_base32(sysadmin_secret)


def test_create_teacher_stores_the_seed_it_is_given_and_mints_none(app):
    """classroom_setup.create_teacher is not a mint site: it only stores."""
    from app.services.classroom_setup import create_teacher

    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:create-teacher"):
        stored = create_teacher("seed_teacher_given", totp_secret=SHORT_SEED)
        absent = create_teacher("seed_teacher_none")
    assert decrypt_totp(stored.totp_secret_encrypted) == SHORT_SEED
    assert absent.totp_secret_encrypted is None


def unmanaged_seed_generation(source: str, exempt_function: str | None = None) -> list[int]:
    """Lines that name pyotp's ``random_base32`` in any way (call, alias or import).

    ``exempt_function`` excuses exactly one such reference, inside that function; a
    second one there, or any elsewhere in the file, is reported.
    """
    tree = ast.parse(source)
    exempt_nodes = set()
    for node in ast.walk(tree):
        if exempt_function and isinstance(node, ast.FunctionDef) and node.name == exempt_function:
            inside = [n for n in ast.walk(node) if _names_generator(n)]
            exempt_nodes.update(id(n) for n in inside[:1])
    return sorted(n.lineno for n in ast.walk(tree) if _names_generator(n) and id(n) not in exempt_nodes)


def _names_generator(node) -> bool:
    return (
        (isinstance(node, ast.Attribute) and node.attr == "random_base32")
        or (isinstance(node, ast.Name) and node.id == "random_base32")
        or (isinstance(node, ast.ImportFrom) and any(a.name == "random_base32" for a in node.names))
    )


def test_only_the_single_generator_names_random_base32():
    offenders = {}
    for path in sorted((REPO / "app").rglob("*.py")):
        exempt = "mint_totp_secret" if path == REPO / "app" / "services" / "credential_lifecycle.py" else None
        found = unmanaged_seed_generation(path.read_text(encoding="utf-8"), exempt)
        if found:
            offenders[str(path.relative_to(REPO))] = found
    assert offenders == {}


@pytest.mark.parametrize("mutation", [
    "import pyotp\nsecret = pyotp.random_base32()\n",
    "import pyotp\nsecret = pyotp.random_base32(length=16)\n",
    "import pyotp as p\nsecret = p.random_base32(16)\n",
    "from pyotp import random_base32 as rb\nsecret = rb()\n",
    "import pyotp\ngenerate = pyotp.random_base32\n",
])
def test_seed_generation_guard_detects_near_misses(mutation):
    """Mutation proof (SOP-TEST-003 §IX.A): the detector reports the spellings a change would use."""
    assert unmanaged_seed_generation(mutation)


_MINT = "import pyotp\ndef mint_totp_secret():\n    return pyotp.random_base32(32)\n"


def test_the_exemption_covers_only_the_one_call_in_mint_totp_secret():
    assert unmanaged_seed_generation(_MINT, "mint_totp_secret") == []
    # A second generator in the same file, in another function or in the exempt one.
    other = _MINT + "def other():\n    return pyotp.random_base32(16)\n"
    assert unmanaged_seed_generation(other, "mint_totp_secret") == [5]
    twice = _MINT.replace("return pyotp.random_base32(32)", "pyotp.random_base32(16)\n    return pyotp.random_base32(32)")
    assert len(unmanaged_seed_generation(twice, "mint_totp_secret")) == 1


def test_seed_generation_guard_ignores_the_single_generator_call():
    assert unmanaged_seed_generation("from app.services.credential_lifecycle import mint_totp_secret\nx = mint_totp_secret()\n") == []


# ---------------------------------------------------------------------------
# opening an operation
# ---------------------------------------------------------------------------

def test_open_operation_refuses_a_totp_code_for_totp_replace(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(CredentialOperationRefused) as refused:
        open_credential_operation(
            user_id=user_id, purpose="totp_replace",
            proof=TotpCode(_code(HELD_SEED)), session_nonce=_nonce(user_id),
        )

    assert refused.value.category == "proof_kind_mismatch"
    assert CredentialOperation.query.count() == 0


def test_the_retired_passkey_replace_purpose_opens_nothing(client, app):
    # The purpose guard runs before any principal lookup, so no passkey is needed.
    user_id = initialize_as_teacher("chemistry_p1", client, app).teacher_user.id

    with pytest.raises(CredentialOperationRefused) as refused:
        open_credential_operation(
            user_id=user_id, purpose="passkey_replace", proof=TotpCode(_code(HELD_SEED)),
            session_nonce=_nonce(user_id),
        )

    assert refused.value.category == "unknown_purpose"
    assert CredentialOperation.query.count() == 0


def test_open_operation_refuses_the_retired_passkey_replace_purpose_directly(client, app):
    user_id = initialize_as_teacher("chemistry_p1", client, app).teacher_user.id

    with pytest.raises(CredentialOperationRefused) as refused:
        lifecycle.open_operation(
            _user(user_id), purpose=CredentialOperationPurpose.PASSKEY_REPLACE,
            proof=TotpCode(_code(HELD_SEED)), session_nonce=_nonce(user_id),
        )

    assert refused.value.category == "unknown_purpose"
    assert CredentialOperation.query.count() == 0


def test_totp_code_opens_passkey_enrollment_and_a_wrong_code_does_not(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(CredentialOperationRefused) as refused:
        open_credential_operation(
            user_id=user_id, purpose="passkey_enroll", proof=TotpCode(_wrong_code(HELD_SEED)),
            session_nonce=_nonce(user_id),
        )
    assert refused.value.category == "proof_rejected"

    operation_id = open_credential_operation(
        user_id=user_id, purpose="passkey_enroll", proof=TotpCode(_code(HELD_SEED)),
        session_nonce=_nonce(user_id),
    )
    assert _operation(operation_id).purpose is CredentialOperationPurpose.PASSKEY_ENROLL


def test_open_operation_records_exactly_the_authorized_state(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    nonce = _nonce(user_id)
    started = temporal.now()

    with temporal.pinned_clock(started):
        operation_id = _open_replacement(user_id, fake_passwordless)

    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.AUTHORIZED
    assert operation.purpose is CredentialOperationPurpose.TOTP_REPLACE
    assert operation.authorized_generation == _user(user_id).credential_generation == 1
    assert operation.deadline_at == temporal.shifted(started, minutes=10)
    assert operation.session_binding_hash == lifecycle.session_binding_digest(operation.purpose, nonce)
    assert nonce not in operation.session_binding_hash
    assert operation.pending_totp_encrypted is None
    assert operation.attempt_count == 0


def test_evidence_for_a_foreign_unknown_or_unactivated_credential_authorizes_nothing(client, app, fake_passwordless):
    other = initialize("biology_block_a", app)
    _add_passkey(other.teacher_user.id, "cred-other")
    fake_passwordless.credentials["cred-other"] = passkey_external_id(other.teacher_user.id)
    _, user_id = _enrolled_teacher(client, app, fake_passwordless, key="chemistry_p1")
    # Registered at the provider for this principal but never activated locally.
    fake_passwordless.credentials["cred-pending"] = passkey_external_id(user_id)
    # Held by this principal at the provider, recorded locally for no one.
    fake_passwordless.credentials["cred-unknown"] = passkey_external_id(user_id)
    # A foreign credential presented as this principal's.
    fake_passwordless.credentials["cred-foreign"] = passkey_external_id(user_id)

    for credential in ("cred-pending", "cred-unknown", "cred-foreign"):
        with pytest.raises(CredentialOperationRefused) as refused:
            _open_replacement(user_id, fake_passwordless, credential=credential)
        assert refused.value.category == "step_up_credential"
    # A real activated credential belonging to someone else, named as someone else.
    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_id, fake_passwordless, credential="cred-other")
    assert refused.value.category == "step_up_principal"

    assert _live_operations() and all(
        o.stage is CredentialOperationStage.AWAITING_STEP_UP for o in _live_operations())


def test_a_sign_in_or_registration_token_of_the_wrong_type_is_refused(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_id, fake_passwordless, type_="passkey_register")

    assert refused.value.category == "step_up_type"
    assert all(o.stage is CredentialOperationStage.AWAITING_STEP_UP for o in _live_operations())


def test_open_operation_requires_the_live_session(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_id, fake_passwordless, nonce="a-session-that-is-not-current")

    assert refused.value.category == "session_not_current"
    assert CredentialOperation.query.count() == 0  # no challenge was stored for another session


def test_second_live_operation_is_refused_and_the_index_is_what_enforces_it(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    first = _open_replacement(user_id, fake_passwordless)

    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_id, fake_passwordless)
    assert refused.value.category == "operation_already_open"
    assert CredentialOperation.query.count() == 1

    # Bypass the command: only the partial unique index stands between us and a second live row.
    def insert(stage):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:op:{uuid.uuid4().hex}"):
            db.session.add(CredentialOperation(
                user_id=user_id, purpose=CredentialOperationPurpose.TOTP_REPLACE, stage=stage,
                authorized_generation=1, session_binding_hash="0" * 64, deadline_at=temporal.now(),
            ))

    with pytest.raises(IntegrityError):
        insert(CredentialOperationStage.AUTHORIZED)
    db.session.rollback()
    # Terminal rows are outside the index's predicate and may coexist.
    insert(CredentialOperationStage.COMPLETED)
    insert(CredentialOperationStage.CANCELLED)
    assert CredentialOperation.query.filter_by(id=first).one().stage is CredentialOperationStage.AUTHORIZED
    assert CredentialOperation.query.count() == 3


def test_a_cancelled_operation_frees_the_slot(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    first = _open_replacement(user_id, fake_passwordless)
    assert cancel_totp_replacement(user_id=user_id, operation_id=first, session_nonce=_nonce(user_id))

    second = _open_replacement(user_id, fake_passwordless)

    assert second != first


def test_an_expired_unswept_operation_does_not_block_a_new_one(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    first = _open_replacement(user_id, fake_passwordless)
    _hold(user_id, first)

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=11)):
        second = _open_replacement(user_id, fake_passwordless)

    assert _operation(first).stage is CredentialOperationStage.CANCELLED
    assert _operation(first).pending_totp_encrypted is None
    assert _operation(second).stage is CredentialOperationStage.AUTHORIZED


def test_a_sysadmin_holds_the_same_obligations(client, app, fake_passwordless):
    from app.services.identity_service import create_system_principal
    from app.utils.auth_username import build_hashed_username_fields

    with FEATContext("FEAT-IDEN-008", idempotency_key="seed-test:sysadmin-op"):
        create_system_principal("op_sysadmin")
    lookup = build_hashed_username_fields("op_sysadmin")[2]
    sysadmin = User.query.filter_by(username_lookup_hash=lookup).one()
    sysadmin_id = sysadmin.id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:sysadmin-session"):
        db.session.get(User, sysadmin_id).current_session_nonce = "sysadmin-session-nonce"
    _add_passkey(sysadmin_id, "cred-sys")
    fake_passwordless.credentials["cred-sys"] = passkey_external_id(sysadmin_id)

    assert decoded_secret_bits(_user(sysadmin_id)) == 160
    operation_id = _open_replacement(
        sysadmin_id, fake_passwordless, credential="cred-sys", nonce="sysadmin-session-nonce",
    )

    assert _operation(operation_id).user_id == sysadmin_id


def test_commands_refuse_to_run_outside_their_feat(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    evaluation = lifecycle.StepUpEvaluation(operation_id=str(uuid.uuid4()), credential_id="cred-1")
    for run in (
        lambda: lifecycle.open_operation(
            _user(user_id), purpose=CredentialOperationPurpose.PASSKEY_ENROLL,
            proof=TotpCode(_code(HELD_SEED)), session_nonce=_nonce(user_id)),
        lambda: lifecycle.issue_replacement_challenge(user_id, session_nonce=_nonce(user_id)),
        lambda: lifecycle.consume_step_up_evidence(
            evaluation, None, user_id=user_id, challenge="x", session_nonce=_nonce(user_id)),
    ):
        with pytest.raises(PermissionError):
            run()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:wrong-feat"):
            with pytest.raises(PermissionError):
                run()


# ---------------------------------------------------------------------------
# holding and activating the replacement
# ---------------------------------------------------------------------------

def test_holding_a_candidate_leaves_the_current_secret_and_stage_alone(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    before = _stored_seed(user_id)
    operation_id = _open_replacement(user_id, fake_passwordless)

    secret, uri = _hold(user_id, operation_id)

    assert _is_160_bit_base32(secret)
    assert secret in uri and uri.startswith("otpauth://totp/")
    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.AUTHORIZED
    assert decrypt_totp(operation.pending_totp_encrypted) == secret
    assert secret not in operation.pending_totp_encrypted
    assert _stored_seed(user_id) == before
    # A refresh shows the same seed rather than minting another.
    assert _hold(user_id, operation_id)[0] == secret


def test_wrong_code_changes_nothing_and_the_operation_stays_open(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    before_seed, before_nonce = _stored_seed(user_id), _nonce(user_id)
    wrong = _wrong_code(secret)

    assert _activate(user_id, operation_id, wrong) is False

    assert _stored_seed(user_id) == before_seed
    assert _user(user_id).credential_generation == 1
    assert _nonce(user_id) == before_nonce
    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.AUTHORIZED
    assert operation.pending_totp_encrypted is not None
    assert operation.attempt_count == 0
    assert _outcome_events() == []
    # The right code still works afterwards.
    assert _activate(user_id, operation_id, _code(secret)) is True


def test_a_code_for_the_old_secret_does_not_activate_the_candidate(client, app, fake_passwordless, monkeypatch):
    assert not _accepted(HELD_SEED, FIXED_INSTANT) & _accepted(SEED_32, FIXED_INSTANT)
    monkeypatch.setattr(lifecycle, "mint_totp_secret", lambda: SEED_32)
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    _hold(user_id, operation_id)

    with temporal.pinned_clock(FIXED_INSTANT):
        assert _activate(user_id, operation_id, _code(HELD_SEED)) is False
    assert decrypt_totp(_stored_seed(user_id)) == HELD_SEED


def test_repeated_wrong_codes_never_cancel_the_operation_or_touch_attempt_count(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    wrong = _wrong_code(secret)
    before = _stored_seed(user_id)

    for _ in range(10):
        assert _activate(user_id, operation_id, wrong) is False

    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.AUTHORIZED
    assert operation.pending_totp_encrypted is not None
    assert operation.attempt_count == 0
    assert _stored_seed(user_id) == before
    assert not hasattr(lifecycle, "MAX_CODE_ATTEMPTS")
    assert _activate(user_id, operation_id, _code(secret)) is True


def test_correct_code_activates_the_new_seed_once(client, app, fake_passwordless, monkeypatch):
    monkeypatch.setattr(lifecycle, "mint_totp_secret", lambda: SEED_32)
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    old_nonce = _nonce(user_id)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)

    assert _activate(user_id, operation_id, _code(secret)) is True

    user = _user(user_id)
    assert decrypt_totp(user.totp_secret_encrypted) == secret
    assert decoded_secret_bits(user) == 160
    assert user.credential_generation == 2
    assert user.current_session_nonce != old_nonce
    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.COMPLETED
    assert operation.pending_totp_encrypted is None
    assert credential_compliance(user) is CredentialCompliance.COMPLIANT
    # The new authenticator is the only secret now.
    with temporal.pinned_clock(FIXED_INSTANT):
        assert lifecycle.evaluate_totp_code(user, _code(secret))
        assert not lifecycle.evaluate_totp_code(user, _code(HELD_SEED))


def test_activation_emits_one_non_identifying_outcome_event(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    nonce = _nonce(user_id)

    _activate(user_id, operation_id, _code(secret))

    (event,) = _outcome_events()
    assert event.operation == "TRANSITION"
    assert event.chain_scope == "system"
    assert event.feat_id == "FEAT-IDEN-106"
    assert event.actor_type == "teacher"
    assert event.class_id is None and event.seat_id is None and event.actor_id_hash is None
    assert event.idempotency_key is None
    identifying = (user_id, operation_id, nonce, secret)
    for value in (event.row_pk, event.correlation_id, event.request_id):
        assert value is None or all(item not in value for item in identifying)
    uuid.UUID(event.row_pk)  # an independently generated id, not a row key


def test_replay_after_completion_is_refused_and_generation_does_not_advance_twice(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    code = _code(secret)
    assert _activate(user_id, operation_id, code) is True
    after_first = _stored_seed(user_id)
    session_nonce = _nonce(user_id)

    for nonce in (session_nonce, "the-old-session"):
        with pytest.raises(CredentialOperationRefused) as refused:
            _activate(user_id, operation_id, code, nonce=nonce)
        assert refused.value.category == "operation_not_open"

    user = _user(user_id)
    assert user.credential_generation == 2
    assert user.totp_secret_encrypted == after_first
    assert user.current_session_nonce == session_nonce
    assert len(_outcome_events()) == 1


def test_stale_generation_fails_closed(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    before = _stored_seed(user_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:advance"):
        db.session.get(User, user_id).credential_generation = 2

    with pytest.raises(CredentialOperationRefused) as refused:
        _activate(user_id, operation_id, _code(secret))
    assert refused.value.category == "stale_generation"
    with pytest.raises(CredentialOperationRefused):
        _hold(user_id, operation_id)

    assert _stored_seed(user_id) == before
    assert _user(user_id).credential_generation == 2
    assert _operation(operation_id).stage is CredentialOperationStage.AUTHORIZED


def test_another_teacher_cannot_act_on_this_operation(client, app, fake_passwordless):
    _, user_a = _enrolled_teacher(client, app, fake_passwordless, key="chemistry_p1", credential="cred-a")
    classroom_b = initialize("biology_block_a", app)
    user_b = classroom_b.teacher_user.id
    _set_seed(user_b, HELD_SEED)
    operation_id = _open_replacement(user_a, fake_passwordless, credential="cred-a")
    secret, _ = _hold(user_a, operation_id)
    seed_a, seed_b = _stored_seed(user_a), _stored_seed(user_b)
    code = _code(secret)
    nonce_b = _nonce(user_b) or "b-has-no-session"

    # Through the FEAT entries: B's id never reaches A's row.
    for attempt in (
        lambda: _activate(user_b, operation_id, code, nonce=nonce_b),
        lambda: _hold(user_b, operation_id, nonce=nonce_b),
        lambda: cancel_totp_replacement(user_id=user_b, operation_id=operation_id, session_nonce=nonce_b),
    ):
        with pytest.raises(CredentialOperationRefused) as refused:
            attempt()
        assert refused.value.category == "operation_not_found"

    # Directly against the command, with B's own session: the binding refuses.
    with FEATContext("FEAT-IDEN-106", idempotency_key="seed-test:cross-teacher"):
        with pytest.raises(CredentialOperationRefused) as refused:
            lifecycle.activate_totp(_operation(operation_id), code, session_nonce=nonce_b)
    assert refused.value.category == "session_not_current"

    assert _stored_seed(user_a) == seed_a and _stored_seed(user_b) == seed_b
    assert _operation(operation_id).stage is CredentialOperationStage.AUTHORIZED
    assert _user(user_a).credential_generation == 1 and _user(user_b).credential_generation == 1


def test_a_different_session_of_the_same_teacher_cannot_activate(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)

    with pytest.raises(CredentialOperationRefused) as refused:
        _activate(user_id, operation_id, _code(secret), nonce="a-second-browser-session")

    assert refused.value.category == "session_not_current"
    assert decrypt_totp(_stored_seed(user_id)) == HELD_SEED


def test_activation_after_the_deadline_is_refused(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    code = _code(secret)

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=10, seconds=1)):
        with pytest.raises(CredentialOperationRefused) as refused:
            _activate(user_id, operation_id, code)
    assert refused.value.category == "operation_expired"
    assert decrypt_totp(_stored_seed(user_id)) == HELD_SEED
    assert _user(user_id).credential_generation == 1


def test_cancellation_erases_the_pending_seed(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    _hold(user_id, operation_id)
    before = _stored_seed(user_id)

    with pytest.raises(CredentialOperationRefused):
        cancel_totp_replacement(user_id=user_id, operation_id=operation_id, session_nonce="not-the-session")
    assert _operation(operation_id).pending_totp_encrypted is not None

    assert cancel_totp_replacement(user_id=user_id, operation_id=operation_id, session_nonce=_nonce(user_id))

    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.CANCELLED
    assert operation.pending_totp_encrypted is None
    assert _stored_seed(user_id) == before
    assert not cancel_totp_replacement(user_id=user_id, operation_id=operation_id, session_nonce=_nonce(user_id))


# ---------------------------------------------------------------------------
# pure evaluation and sign-in
# ---------------------------------------------------------------------------

def test_pure_assertion_evaluation_writes_nothing_and_sign_in_still_stamps_last_used(client, app, fake_passwordless):
    from app.services import passkey_service

    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    evaluation = lifecycle.evaluate_passkey_assertion(
        fake_passwordless.sign_in_token("cred-1"), expected_role="teacher",
        expected_user_id=user_id, purpose=lifecycle.SIGN_IN_PURPOSE,
    )
    assert evaluation.user.id == user_id and evaluation.credential_id == "cred-1"
    assert not db.session.new and not db.session.dirty
    assert PasskeyCredential.query.filter_by(credential_id="cred-1").one().last_used is None

    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:sign-in"):
        user = passkey_service.verify_sign_in(
            fake_passwordless.sign_in_token("cred-1"), expected_role="teacher", expected_user_id=user_id,
        )
    assert user.id == user_id
    assert PasskeyCredential.query.filter_by(credential_id="cred-1").one().last_used is not None


@pytest.mark.parametrize("purpose", ["passkey_revoke", "totp_replace"])
def test_an_assertion_cannot_authorize_a_purpose_it_does_not_prove(client, app, fake_passwordless, purpose):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(PasskeyError):
        lifecycle.evaluate_passkey_assertion(
            fake_passwordless.sign_in_token("cred-1"), expected_role="teacher",
            expected_user_id=user_id, purpose=purpose,
        )


def test_assertion_evaluation_rejects_a_changed_generation(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)

    with pytest.raises(PasskeyError):
        lifecycle.evaluate_passkey_assertion(
            fake_passwordless.sign_in_token("cred-1"), expected_role="teacher",
            expected_user_id=user_id, purpose=lifecycle.SIGN_IN_PURPOSE, expected_generation=7,
        )


def test_a_new_principal_starts_at_generation_one(client, app):
    classroom = initialize("chemistry_p1", app)

    assert _user(classroom.teacher_user.id).credential_generation == 1


# ---------------------------------------------------------------------------
# expiry sweep
# ---------------------------------------------------------------------------

def test_the_sweep_cancels_expired_operations_and_erases_their_seeds(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    _hold(user_id, operation_id)

    assert expire_credential_operations() == {"cancelled": 0, "erased": 0}
    assert _operation(operation_id).pending_totp_encrypted is not None

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=10, seconds=1)):
        assert expire_credential_operations() == {"cancelled": 1, "erased": 0}
        operation = _operation(operation_id)
        assert operation.stage is CredentialOperationStage.CANCELLED
        assert operation.pending_totp_encrypted is None
        # The cancelled receipt stays only until its original deadline has passed, then goes.
        assert expire_credential_operations() == {"cancelled": 0, "erased": 1}
    assert CredentialOperation.query.count() == 0


def test_the_sweep_drops_a_completed_receipt_only_after_its_deadline(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    _activate(user_id, operation_id, _code(secret))

    assert expire_credential_operations() == {"cancelled": 0, "erased": 0}
    assert _operation(operation_id).stage is CredentialOperationStage.COMPLETED
    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=11)):
        assert expire_credential_operations() == {"cancelled": 0, "erased": 1}
    assert CredentialOperation.query.count() == 0
    # An expired receipt cannot authorize re-execution.
    with pytest.raises(CredentialOperationRefused) as refused:
        _activate(user_id, operation_id, _code(secret))
    assert refused.value.category == "operation_not_found"


@pytest.mark.parametrize("stage", [
    CredentialOperationStage.RETIREMENT_COMMITTED, CredentialOperationStage.PROVIDER_UNCERTAIN,
])
def test_the_sweep_leaves_committed_retirement_and_uncertain_provider_work_alone(
    client, app, fake_passwordless, stage,
):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:stage:{uuid.uuid4().hex}"):
        db.session.get(CredentialOperation, operation_id).stage = stage

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=30)):
        assert expire_credential_operations() == {"cancelled": 0, "erased": 0}

    assert _operation(operation_id).stage is stage


def test_the_sweep_is_a_registered_hourly_job_on_its_own_minute():
    from app.scheduled_tasks import SCHEDULED_JOB_SPECS, expire_credential_operations_job

    spec = next(s for s in SCHEDULED_JOB_SPECS if s.id == "expire_credential_operations")
    assert spec.func is expire_credential_operations_job
    assert spec.trigger == "cron" and "hour" not in spec.trigger_kwargs
    minutes = [s.trigger_kwargs.get("minute") for s in SCHEDULED_JOB_SPECS if s.trigger == "cron" and "hour" not in s.trigger_kwargs]
    assert minutes.count(spec.trigger_kwargs["minute"]) == 1


def test_the_scheduled_job_runs_the_sweep(client, app, fake_passwordless):
    from app.scheduled_tasks import expire_credential_operations_job

    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    _hold(user_id, operation_id)

    with temporal.pinned_clock(temporal.shifted(temporal.now(), minutes=11)):
        assert expire_credential_operations_job() == {"cancelled": 1, "erased": 0}

    assert _operation(operation_id).pending_totp_encrypted is None


def test_deleting_the_principal_removes_its_operation(app):
    from app.services.identity_service import create_system_principal
    from app.utils.auth_username import build_hashed_username_fields

    with FEATContext("FEAT-IDEN-008", idempotency_key="seed-test:delete-principal"):
        create_system_principal("deleted_sysadmin")
    sysadmin_id = User.query.filter_by(
        username_lookup_hash=build_hashed_username_fields("deleted_sysadmin")[2]
    ).one().id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:open-then-delete"):
        db.session.add(CredentialOperation(
            user_id=sysadmin_id, purpose=CredentialOperationPurpose.TOTP_REPLACE,
            stage=CredentialOperationStage.AUTHORIZED, authorized_generation=1,
            session_binding_hash="0" * 64, deadline_at=temporal.now(),
            pending_totp_encrypted=encrypt_totp(mint_totp_secret()),
        ))
    assert CredentialOperation.query.count() == 1

    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:delete-user"):
        db.session.execute(sa.delete(User.__table__).where(User.__table__.c.id == sysadmin_id))

    assert CredentialOperation.query.count() == 0


# ---------------------------------------------------------------------------
# review findings
# ---------------------------------------------------------------------------

def test_the_provider_is_called_with_no_transaction_open(client, app, fake_passwordless):
    seen = []
    original = fake_passwordless.send  # the provider's /signin/verify round trip

    def send(request, **kwargs):
        seen.append(db.session().in_transaction())
        return original(request, **kwargs)

    fake_passwordless.send = send
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    _nonce(user_id)  # an incidental read leaves a transaction open, as a request would
    assert db.session().in_transaction()

    _open_replacement(user_id, fake_passwordless)

    # Config check (challenge), verify, config check (authorize): every provider call, no transaction open.
    assert seen == [False, False, False]


def test_a_token_naming_one_principal_with_another_principals_credential_is_refused(client, app, fake_passwordless):
    _, user_a = _enrolled_teacher(client, app, fake_passwordless)
    user_b = initialize("biology_block_a", app).teacher_user.id
    _add_passkey(user_b, "cred-b")  # activated locally, for B
    fake_passwordless.credentials["cred-b"] = passkey_external_id(user_a)  # the token names A

    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_a, fake_passwordless, credential="cred-b")

    assert refused.value.category == "step_up_credential"
    assert all(o.stage is CredentialOperationStage.AWAITING_STEP_UP for o in _live_operations())


def test_a_non_ascii_session_nonce_is_refused_not_a_crash(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    with pytest.raises(CredentialOperationRefused):
        _open_replacement(user_id, fake_passwordless, nonce="s\u00e9ssion")
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    with pytest.raises(CredentialOperationRefused) as refused:
        _activate(user_id, operation_id, _code(secret), nonce="s\u00e9ssion")
    assert refused.value.category == "session_not_current"


def test_the_totp_feat_cannot_cancel_a_passkey_operation(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = open_credential_operation(
        user_id=user_id, purpose="passkey_enroll", proof=TotpCode(_code(HELD_SEED)),
        session_nonce=_nonce(user_id),
    )

    with pytest.raises(CredentialOperationRefused) as refused:
        cancel_totp_replacement(user_id=user_id, operation_id=operation_id, session_nonce=_nonce(user_id))

    assert refused.value.category == "wrong_purpose"
    assert _operation(operation_id).stage is CredentialOperationStage.AUTHORIZED


def test_the_deadline_is_rechecked_after_the_code_is_verified(client, app, fake_passwordless, monkeypatch):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless)
    secret, _ = _hold(user_id, operation_id)
    before = _stored_seed(user_id)
    calls = iter([True, False])  # open at the first check, expired by the second
    monkeypatch.setattr(lifecycle, "_deadline_open", lambda operation: next(calls))

    with pytest.raises(CredentialOperationRefused) as refused:
        _activate(user_id, operation_id, _code(secret))

    assert refused.value.category == "operation_expired"
    assert _stored_seed(user_id) == before
    assert _user(user_id).credential_generation == 1


def test_provider_verification_is_refused_inside_an_open_transaction_with_pending_work(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    nonce = _nonce(user_id)

    db.session.begin_nested() if db.session().in_transaction() else db.session.begin()
    db.session.add(CredentialOperation(
        user_id=user_id, purpose=CredentialOperationPurpose.TOTP_REPLACE,
        stage=CredentialOperationStage.CANCELLED, authorized_generation=1,
        session_binding_hash="0" * 64, deadline_at=temporal.now(),
    ))
    try:
        with pytest.raises(CredentialOperationRefused) as refused:
            issue_totp_replacement_challenge(user_id=user_id, session_nonce=nonce)
        assert refused.value.category == "transaction_open"
        assert fake_passwordless.calls == []  # no provider call was made
        assert db.session.new  # the pending work was not rolled back
    finally:
        db.session.rollback()


# ---------------------------------------------------------------------------
# the stateless (HMAC) step-up challenge, kept for TOTP-authorized passkey work
# ---------------------------------------------------------------------------

def test_a_stateless_challenge_for_another_purpose_generation_or_session_is_refused(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    user = _user(user_id)
    nonce = _nonce(user_id)
    other_purpose = _challenge(user_id, purpose="passkey_enroll")
    stale = _challenge(user_id)
    other_session = lifecycle._step_up_value(
        user_id, CredentialOperationPurpose.TOTP_REPLACE, "another-session", user.credential_generation,
        lifecycle._step_up_bucket(),
    )
    other_user = lifecycle._step_up_value(
        "00000000-0000-0000-0000-000000000000", CredentialOperationPurpose.TOTP_REPLACE, nonce,
        user.credential_generation, lifecycle._step_up_bucket(),
    )
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:bump"):
        db.session.get(User, user_id).credential_generation = 2

    for challenge in (other_purpose, stale, other_session, other_user, "", None):
        with pytest.raises(CredentialOperationRefused) as refused:
            lifecycle.check_step_up_challenge(
                _user(user_id), purpose=CredentialOperationPurpose.TOTP_REPLACE,
                session_nonce=nonce, challenge=challenge)
        assert refused.value.category == "challenge_invalid"


def test_a_stateless_challenge_expires_after_one_further_bucket(client, app, fake_passwordless):
    _, user_id = _enrolled_teacher(client, app, fake_passwordless)
    nonce = _nonce(user_id)
    check = lambda: lifecycle.check_step_up_challenge(  # noqa: E731
        _user(user_id), purpose=CredentialOperationPurpose.TOTP_REPLACE, session_nonce=nonce, challenge=challenge)
    with temporal.pinned_clock(FIXED_INSTANT):
        challenge = _challenge(user_id)
    with temporal.pinned_clock(temporal.shifted(FIXED_INSTANT, minutes=10)):
        with pytest.raises(CredentialOperationRefused) as refused:
            check()
    assert refused.value.category == "challenge_invalid"
    with temporal.pinned_clock(temporal.shifted(FIXED_INSTANT, minutes=5)):
        check()


# ---------------------------------------------------------------------------
# recovery supersession
# ---------------------------------------------------------------------------

def _recovery_teacher_session(recovery_fixture, fake):
    user_id = recovery_fixture.teacher.id
    _set_seed(user_id, HELD_SEED)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:nonce:{uuid.uuid4().hex}"):
        db.session.get(User, user_id).current_session_nonce = f"session-{uuid.uuid4().hex}"
    fake.credentials["old-key"] = passkey_external_id(user_id)
    return user_id


def test_recovery_aggregate_success_supersedes_a_pending_replacement(app, fake_passwordless, recovery):  # noqa: F811
    user_id = _recovery_teacher_session(recovery, fake_passwordless)
    operation_id = _open_replacement(user_id, fake_passwordless, credential="old-key")
    secret, _ = _hold(user_id, operation_id)
    before_seed = _stored_seed(user_id)

    recovery_setup(recovery)

    assert _user(user_id).credential_generation == 2
    operation = _operation(operation_id)
    assert operation.stage is CredentialOperationStage.CANCELLED
    assert operation.pending_totp_encrypted is None
    with pytest.raises(CredentialOperationRefused):
        _activate(user_id, operation_id, _code(secret))
    assert _stored_seed(user_id) == before_seed


def test_a_routine_operation_cannot_open_while_a_recovery_grant_is_live(app, fake_passwordless, recovery):  # noqa: F811
    user_id = _recovery_teacher_session(recovery, fake_passwordless)
    recovery_setup(recovery)

    with pytest.raises(CredentialOperationRefused) as refused:
        _open_replacement(user_id, fake_passwordless, credential="old-key")
    assert refused.value.category == "recovery_active"
    with pytest.raises(CredentialOperationRefused) as refused:
        open_credential_operation(
            user_id=user_id, purpose="passkey_enroll", proof=TotpCode(_code(HELD_SEED)),
            session_nonce=_nonce(user_id),
        )
    assert refused.value.category == "recovery_active"
    assert CredentialOperation.query.count() == 0


def test_after_recovery_completes_the_gate_path_still_works(app, fake_passwordless, recovery):  # noqa: F811
    user_id = _recovery_teacher_session(recovery, fake_passwordless)
    grant = recovery_setup(recovery)
    recovery_finish(recovery, grant)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="seed-test:relogin"):
        db.session.get(User, user_id).current_session_nonce = "post-recovery-session"

    assert credential_compliance(_user(user_id)) is CredentialCompliance.PASSKEY_MISSING
    operation_id = open_credential_operation(
        user_id=user_id, purpose="passkey_enroll", proof=TotpCode(_code(grant["secret"])),
        session_nonce="post-recovery-session",
    )

    assert _operation(operation_id).stage is CredentialOperationStage.AUTHORIZED
