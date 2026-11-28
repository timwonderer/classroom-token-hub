"""TOTP replacement step-up evidence (SPEC-IDEN-002 §V, §IX; FEAT-IDEN-106).

A TOTP replacement is authorized only by dedicated provider step-up evidence (purpose
``totp-replace``), consumed once against a stored single-use challenge on the principal's one
TOTP_REPLACE operation. This module proves the pure evaluation rules, the consumption order, token
replay refusal and retention, the provider configuration check and the deletion guard. The races
(two connections) are in ``test_totp_step_up_concurrency.py``.

Four kinds of assurance stay distinct here as in the specification: provider-authenticated
evidence, CTH-enforced operation authorization, provider-dependent user verification (never
asserted by these tests: CTH cannot observe it) and cryptographic operation binding (not
supported; nothing here claims it).

Every instant is the resolver's, pinned per step (``tests/helpers/temporal.py``). Instants are
written as millisecond offsets from ``BASE`` so the boundaries (exactly ``t0``, exactly ``c``,
exactly ``now + S``, exactly ``L``) are exact, and one millisecond past each is refused.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest
import sqlalchemy as sa

from app import db
from app.feats.base import FEATContext
from app.feats.credential_operations_feat import (
    activate_totp_replacement,
    authorize_totp_replacement,
    cancel_totp_replacement,
    expire_credential_operations,
    hold_totp_candidate,
    issue_totp_replacement_challenge,
)
from app.models import CredentialOperation, CredentialOperationStage, PasskeyCredential, User
from app.services import credential_lifecycle as lifecycle
from app.services.credential_lifecycle import CredentialOperationRefused
from app.services.passkey_service import PasskeyError
from app.utils.encryption import decrypt_totp
from app.utils.passwordless_client import StepUpEvidenceMalformed, parse_step_up_evidence
from app.utils.user_ids import passkey_external_id
from tests.helpers import temporal
from tests.helpers.canonical_classroom import _teacher_key_for
from tests.helpers.canonical_identities import TEACHERS
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.passkey import (  # noqa: F401  (fixture)
    HELD_SEED, MISSING, VALID_AUTH_CONFIGS, fake_passwordless, give_totp_seed, instant_text, record_passkey,
)

AWAITING = CredentialOperationStage.AWAITING_STEP_UP
W = lifecycle.STEP_UP_CHALLENGE_SECONDS * 1000   # the challenge window, in ms
L = lifecycle.STEP_UP_MAX_LIFETIME_SECONDS * 1000
S = lifecycle.STEP_UP_SKEW_SECONDS * 1000


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------

@pytest.fixture
def base():
    """A whole-second instant inside the teacher's live sign-in window."""
    return temporal.now().replace(microsecond=0)


def at(base, offset_ms):
    """``base`` plus a whole-second millisecond offset, as a pinned-clock instant."""
    assert offset_ms % 1000 == 0
    return temporal.shifted(base, seconds=offset_ms // 1000)


def text(base, offset_ms):
    """The provider's spelling of ``base + offset_ms`` (millisecond-exact)."""
    return instant_text(base, offset_ms=offset_ms)


class Rig:
    def __init__(self, client, app, fake, classroom, user_id):
        self.client, self.app, self.fake, self.classroom, self.user_id = client, app, fake, classroom, user_id

    def user(self):
        return db.session.query(User).filter_by(id=self.user_id).populate_existing().one()

    @property
    def nonce(self):
        return self.user().current_session_nonce

    def snapshot(self):
        user = self.user()
        return user.totp_secret_encrypted, user.credential_generation, user.current_session_nonce

    def operations(self):
        db.session.expire_all()
        return CredentialOperation.query.filter_by(user_id=self.user_id).all()

    def live(self):
        return [o for o in self.operations() if o.stage not in (
            CredentialOperationStage.COMPLETED, CredentialOperationStage.CANCELLED)]

    def issue(self, base, offset_ms=0, nonce=None):
        with temporal.pinned_clock(at(base, offset_ms)):
            return issue_totp_replacement_challenge(user_id=self.user_id, session_nonce=nonce or self.nonce)

    def token(self, ts_ms, exp_ms, base, credential="cred-1", **options):
        return self.fake.step_up_token(
            credential, timestamp=text(base, ts_ms), expires_at=text(base, exp_ms), **options)

    def authorize(self, base, now_ms, token, challenge, nonce=None):
        with temporal.pinned_clock(at(base, now_ms)):
            return authorize_totp_replacement(
                user_id=self.user_id, session_nonce=nonce or self.nonce, token=token, challenge=challenge)

    def reset(self, base, offset_ms=0):
        """Drop any open operation and store a fresh challenge issued at ``base + offset_ms``."""
        for operation in self.live():
            cancel_totp_replacement(
                user_id=self.user_id, operation_id=operation.id, session_nonce=self.nonce)
        return self.issue(base, offset_ms)


def refusal(call):
    """The category a call is refused with, ``"malformed"`` for evidence that does not parse, else None."""
    try:
        call()
    except CredentialOperationRefused as refused:
        return refused.category
    except PasskeyError as refused:
        return "malformed" if "well formed" in str(refused) else f"provider:{refused}"
    return None


@pytest.fixture
def rig(client, app, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    user_id = classroom.teacher_user.id
    give_totp_seed(user_id)
    record_passkey(user_id, "cred-1", fake_passwordless)
    return Rig(client, app, fake_passwordless, classroom, user_id)


# ---------------------------------------------------------------------------
# 1. valid evidence authorizes; the TOTP is unchanged until FEAT-IDEN-106 activation
# ---------------------------------------------------------------------------

def test_FEAT_IDEN_106__valid_step_up_evidence_authorizes_and_changes_nothing_else(rig, base):
    before = rig.snapshot()
    challenge = rig.issue(base)
    (operation,) = rig.live()
    assert operation.stage is AWAITING and operation.step_up_challenge_hash
    assert challenge not in operation.step_up_challenge_hash
    assert operation.step_up_issued_at == base
    assert operation.step_up_challenge_expires_at == at(base, W)  # c = min(t0 + W, deadline)

    token = rig.token(10_000, 70_000, base)
    operation_id = rig.authorize(base, 30_000, token, challenge)

    (operation,) = rig.live()
    assert operation.id == operation_id and operation.stage is CredentialOperationStage.AUTHORIZED
    assert operation.step_up_challenge_hash is None  # single use: the verifier is erased
    assert operation.step_up_token_id and operation.step_up_retain_until == at(base, 70_000 + S)
    # Authorization alone changes no credential, generation or session.
    assert rig.snapshot() == before
    assert lifecycle.evaluate_totp_code(rig.user(), pyotp.TOTP(HELD_SEED).at(base))

    # Only FEAT-IDEN-106 activation replaces the TOTP.
    with temporal.pinned_clock(at(base, 40_000)):
        secret, _ = hold_totp_candidate(
            user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce, account_name="t")
        assert rig.snapshot() == before
        assert activate_totp_replacement(
            user_id=rig.user_id, operation_id=operation_id, code=pyotp.TOTP(secret).at(temporal.now()),
            session_nonce=rig.nonce)
    user = rig.user()
    assert decrypt_totp(user.totp_secret_encrypted) == secret and user.credential_generation == before[1] + 1


def test_the_deadline_caps_the_challenge_window(rig, base):
    """c = min(t0 + W, operation deadline): a challenge issued late in the operation is cut short."""
    rig.issue(base)
    (operation,) = rig.live()
    assert operation.deadline_at == at(base, 600_000)
    rig.issue(base, 570_000)  # refreshed 30 s before the deadline: the window ends at the deadline, not at t0 + 120 s
    (operation,) = rig.live()
    assert operation.step_up_challenge_expires_at == at(base, 600_000)


# ---------------------------------------------------------------------------
# 2. refusals leave the TOTP, generation and sessions unchanged
# ---------------------------------------------------------------------------

def _malformed_cases():
    cases = {}
    for key in ("success", "purpose", "type", "userId", "credentialId", "origin", "rpId",
                "timestamp", "expiresAt", "tokenId"):
        cases[f"{key} missing"] = {key: MISSING}
        cases[f"{key} null"] = {key: None}
        cases[f"{key} mistyped"] = {key: 5}
    cases["success as text"] = {"success": "true"}
    cases["purpose empty"] = {"purpose": ""}
    cases["timestamp unparseable"] = {"timestamp": "not a time"}
    cases["timestamp date only"] = {"timestamp": "2026-11-27"}
    cases["timestamp without zone"] = {"timestamp": "2026-11-27T12:00:00"}
    cases["expiresAt unparseable"] = {"expiresAt": "tomorrow"}
    cases["tokenId not a uuid"] = {"tokenId": "tid-1234"}
    return cases


def test_FEAT_IDEN_106__evidence_that_does_not_parse_is_refused(rig, base):
    challenge = rig.issue(base)
    before = rig.snapshot()
    unrefused = []
    for name, overrides in _malformed_cases().items():
        token = rig.token(10_000, 70_000, base, overrides=overrides)
        if refusal(lambda: rig.authorize(base, 30_000, token, challenge)) != "malformed":
            unrefused.append(name)
    assert not unrefused, unrefused
    assert rig.snapshot() == before
    (operation,) = rig.live()
    assert operation.stage is AWAITING and operation.step_up_challenge_hash and operation.step_up_token_id is None


def test_the_evidence_parser_names_a_field_but_never_a_value():
    body = '{"success": true, "userId": "SECRET-USER"}'
    with pytest.raises(StepUpEvidenceMalformed) as raised:
        parse_step_up_evidence(body)
    assert "SECRET-USER" not in str(raised.value)
    for garbage in ("", "null", "[]", "{", "42"):
        with pytest.raises(StepUpEvidenceMalformed):
            parse_step_up_evidence(garbage)


def test_FEAT_IDEN_106__only_totp_replace_step_up_evidence_qualifies(rig, base):
    challenge = rig.issue(base)
    before = rig.snapshot()
    expected = {
        # An ordinary sign-in token, however recent, never authorizes; nor does the generic step-up preset.
        "fresh sign-in token": ({"purpose": "sign-in"}, "step_up_purpose"),
        "step-up preset": ({"purpose": "step-up"}, "step_up_purpose"),
        "unknown purpose": ({"purpose": "totp-replace-2"}, "step_up_purpose"),
        "purpose case": ({"purpose": "TOTP-REPLACE"}, "step_up_purpose"),
        "purpose spelled with an underscore": ({"purpose": "totp_replace"}, "step_up_purpose"),
        "registration token": ({"type_": "passkey_register"}, "step_up_type"),
        "unsuccessful": ({"success": False}, "step_up_not_successful"),
        "origin": ({"overrides": {"origin": "https://evil.test"}}, "step_up_origin"),
        "origin with a trailing slash": ({"overrides": {"origin": "https://cth.test/"}}, "step_up_origin"),
        "rp id": ({"overrides": {"rpId": "evil.test"}}, "step_up_rp_id"),
        "rp id case": ({"overrides": {"rpId": "CTH.TEST"}}, "step_up_rp_id"),
        "another provider user": ({"external_id": passkey_external_id(str(uuid.uuid4()))}, "step_up_principal"),
    }
    failures = {}
    for name, (options, category) in expected.items():
        token = rig.token(10_000, 70_000, base, **options)
        got = refusal(lambda: rig.authorize(base, 30_000, token, challenge))
        if got != category:
            failures[name] = got
    assert not failures, failures
    assert rig.snapshot() == before


def test_FEAT_IDEN_106__the_credential_must_be_an_activated_passkey_of_the_principal(rig, base, fake_passwordless):
    other = initialize("biology_block_a", rig.app).teacher_user.id
    record_passkey(other, "cred-other", fake_passwordless)
    # The provider holds these for this principal; nothing local activates them.
    fake_passwordless.credentials["cred-pending"] = passkey_external_id(rig.user_id)
    challenge = rig.issue(base)
    before = rig.snapshot()

    for credential, category in (
        ("cred-pending", "step_up_credential"), ("cred-other", "step_up_principal"),
    ):
        token = rig.token(10_000, 70_000, base, credential=credential)
        assert refusal(lambda: rig.authorize(base, 30_000, token, challenge)) == category, credential
    # An activated credential locally owned by someone else, claimed at the provider as this principal's.
    fake_passwordless.credentials["cred-other"] = passkey_external_id(rig.user_id)
    token = rig.token(10_000, 70_000, base, credential="cred-other")
    assert refusal(lambda: rig.authorize(base, 30_000, token, challenge)) == "step_up_credential"
    assert rig.snapshot() == before


def test_FEAT_IDEN_106__a_credential_spelled_two_ways_is_one_credential(rig, base):
    """``/signin/verify`` returns standard base64 and the registry may hold either spelling."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:respell:{uuid.uuid4().hex}"):
        row = PasskeyCredential.query.filter_by(user_id=rig.user_id).one()
        row.credential_id = "ab+/cd=="
    rig.fake.credentials["ab+/cd=="] = passkey_external_id(rig.user_id)
    challenge = rig.issue(base)
    token = rig.token(10_000, 70_000, base, credential="ab+/cd==", overrides={"credentialId": "ab-_cd"})
    assert rig.authorize(base, 30_000, token, challenge)


def test_FEAT_IDEN_106__the_session_and_challenge_must_be_the_issued_ones(rig, base):
    challenge = rig.issue(base)
    before = rig.snapshot()
    token = rig.token(10_000, 70_000, base)

    assert refusal(lambda: rig.authorize(base, 30_000, token, challenge, nonce="another-session")) == "session_not_current"
    assert refusal(lambda: rig.authorize(base, 30_000, token, "x" * 43)) == "challenge_invalid"
    assert refusal(lambda: rig.authorize(base, 30_000, token, "")) == "challenge_invalid"
    assert refusal(lambda: rig.authorize(base, 30_000, token, None)) == "challenge_invalid"
    assert rig.snapshot() == before
    # The refusals consumed nothing: the right challenge and session still authorize.
    assert rig.authorize(base, 30_000, token, challenge)


def test_a_challenge_issued_in_another_session_cannot_be_used_in_this_one(rig, base):
    challenge = rig.issue(base)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:relogin:{uuid.uuid4().hex}"):
        rig.user().current_session_nonce = "a-new-sign-in"
    token = rig.token(10_000, 70_000, base)

    assert refusal(lambda: rig.authorize(base, 30_000, token, challenge, nonce="a-new-sign-in")) == "session_not_current"
    # A new challenge in the new session replaces the old session's operation.
    new_challenge = rig.issue(base, 20_000, nonce="a-new-sign-in")
    assert rig.authorize(base, 30_000, rig.token(25_000, 85_000, base), new_challenge, nonce="a-new-sign-in")
    assert len(rig.live()) == 1


# (name, issue offset, ts, expires, now) -> category or None (accepted). All in ms from BASE; t0 = issue, c = t0 + W.
WINDOW_CASES = {
    "ts one ms before t0": (0, -1, 59_999, 30_000, "step_up_before_challenge"),
    "ts exactly t0": (0, 0, 60_000, 30_000, None),
    "ts exactly c": (0, W, W + 60_000, W - 5_000, None),
    "ts one ms after c": (0, W + 1, W + 60_001, W - 5_000, "step_up_after_window"),
    "ts exactly now + S": (0, 40_000, 100_000, 40_000 - S, None),
    "ts one ms after now + S": (0, 40_001, 100_001, 40_000 - S, "step_up_clock"),
    "lifetime exactly L": (0, 10_000, 10_000 + L, 30_000, None),
    "lifetime L + 1 ms": (0, 10_000, 10_000 + L + 1, 30_000, "step_up_lifetime"),
    "lifetime zero": (0, 10_000, 10_000, 30_000, "step_up_lifetime"),
    "lifetime negative": (0, 10_000, 9_000, 30_000, "step_up_lifetime"),
    "now exactly expiresAt": (0, 10_000, 70_000, 70_000, "step_up_expired"),
    "now one second before expiresAt": (0, 10_000, 70_000, 69_000, None),
    "now exactly c": (0, 100_000, 100_000 + 60_000, W, "step_up_expired"),
    "now one second before c": (0, 100_000, 100_000 + 60_000, W - 1_000, None),
}


@pytest.mark.parametrize("name", sorted(WINDOW_CASES))
def test_FEAT_IDEN_106__the_timing_boundaries_are_exact(rig, base, name):
    issue_ms, ts_ms, exp_ms, now_ms, expected = WINDOW_CASES[name]
    challenge = rig.reset(base, issue_ms)
    before = rig.snapshot()
    token = rig.token(ts_ms, exp_ms, base)

    got = refusal(lambda: rig.authorize(base, now_ms, token, challenge))

    assert got == expected, name
    assert rig.snapshot() == before  # authorization alone never touches the TOTP, generation or session
    (operation,) = rig.live()
    if expected is None:
        assert operation.stage is CredentialOperationStage.AUTHORIZED and operation.step_up_token_id
    else:
        assert operation.stage is AWAITING and operation.step_up_challenge_hash and operation.step_up_token_id is None


# ---------------------------------------------------------------------------
# 3. expiry between evaluation and consumption (the clock moves after the pure evaluation)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("boundary", ["expiresAt", "c"])
def test_FEAT_IDEN_106__evidence_that_expires_after_evaluation_is_refused_at_consumption(rig, base, monkeypatch, boundary):
    challenge = rig.issue(base)
    before = rig.snapshot()
    # expiresAt = base + 70 s and c = base + 120 s: land the clock exactly on the boundary under test.
    token = rig.token(10_000, 70_000, base) if boundary == "expiresAt" else rig.token(10_000, 130_000, base)
    landing = at(base, 70_000 if boundary == "expiresAt" else W)
    real = lifecycle.evaluate_step_up_evidence

    with temporal.movable_clock(at(base, 30_000)) as clock:
        def evaluate_then_the_clock_moves(*args, **kwargs):
            evaluation = real(*args, **kwargs)  # passes at base + 30 s
            clock.now = landing
            return evaluation

        monkeypatch.setattr(lifecycle, "evaluate_step_up_evidence", evaluate_then_the_clock_moves)
        got = refusal(lambda: authorize_totp_replacement(
            user_id=rig.user_id, session_nonce=rig.nonce, token=token, challenge=challenge))

    assert got == "step_up_expired"
    assert rig.snapshot() == before
    (operation,) = rig.live()
    assert operation.stage is AWAITING and operation.step_up_token_id is None


# ---------------------------------------------------------------------------
# 4. replay: the first failing check decides
# ---------------------------------------------------------------------------

def test_FEAT_IDEN_106__a_replay_on_the_same_operation_fails_on_the_stage(rig, base):
    challenge = rig.issue(base)
    token = rig.token(10_000, 70_000, base)
    assert rig.authorize(base, 30_000, token, challenge)

    assert refusal(lambda: rig.authorize(base, 31_000, token, challenge)) == "operation_not_open"


def test_FEAT_IDEN_106__a_consumed_or_replaced_challenge_with_a_new_token_fails_on_the_challenge(rig, base):
    first = rig.issue(base)
    second = rig.issue(base, 5_000)  # replaces the first: it is dead
    assert refusal(lambda: rig.authorize(base, 30_000, rig.token(10_000, 70_000, base), first)) == "challenge_invalid"

    # After consumption and cancellation the old challenge is gone for good, whatever new challenge exists.
    assert rig.authorize(base, 30_000, rig.token(10_000, 70_000, base), second)
    third = rig.reset(base, 35_000)
    got = refusal(lambda: rig.authorize(base, 40_000, rig.token(36_000, 96_000, base), second))
    assert got == "challenge_invalid" and third


def _consume_then(rig, base, finish):
    """Consume a token on a first operation, end that operation by ``finish``, return the spent token."""
    challenge = rig.issue(base)
    token = rig.token(10_000, 70_000, base)
    operation_id = rig.authorize(base, 30_000, token, challenge)
    finish(operation_id)
    return token


@pytest.mark.parametrize("ending", ["completed", "cancelled"])
def test_FEAT_IDEN_106__the_same_token_on_a_new_operation_precedes_its_challenge(rig, base, ending):
    def finish(operation_id):
        with temporal.pinned_clock(at(base, 35_000)):
            if ending == "completed":
                secret, _ = hold_totp_candidate(
                    user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce, account_name="t")
                activate_totp_replacement(
                    user_id=rig.user_id, operation_id=operation_id, code=pyotp.TOTP(secret).at(temporal.now()),
                    session_nonce=rig.nonce)
            else:
                cancel_totp_replacement(user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce)

    token = _consume_then(rig, base, finish)
    if ending == "completed":  # activation voids the sign-in; sign in again
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:relogin:{uuid.uuid4().hex}"):
            rig.user().current_session_nonce = "second-sign-in"
    nonce = rig.nonce
    new_challenge = rig.issue(base, 40_000, nonce=nonce)

    assert refusal(lambda: rig.authorize(base, 45_000, token, new_challenge, nonce=nonce)) == "step_up_before_challenge"


def _short_session(rig, base, seconds):
    """End the current sign-in ``seconds`` after ``base`` (the operation deadline is capped by it)."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:session:{uuid.uuid4().hex}"):
        rig.user().current_session_expires_at = at(base, seconds * 1000)


def _sign_in_again(rig, base, nonce="second-sign-in"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:relogin:{uuid.uuid4().hex}"):
        user = rig.user()
        user.current_session_nonce = nonce
        user.current_session_expires_at = at(base, 3_000_000)
    return nonce


def test_FEAT_IDEN_106__the_same_token_after_the_operation_expired_precedes_its_challenge(rig, base):
    _short_session(rig, base, 30)  # the operation's deadline is the end of the sign-in: base + 30 s
    challenge = rig.issue(base)
    token = rig.token(5_000, 125_000, base)  # a long-lived token: it outlives the operation
    assert rig.authorize(base, 10_000, token, challenge)
    (first,) = rig.live()
    assert first.deadline_at == at(base, 30_000)

    nonce = _sign_in_again(rig, base)
    new_challenge = rig.issue(base, 50_000, nonce=nonce)  # the expired first operation is cancelled, not kept live
    db.session.expire_all()
    assert db.session.get(CredentialOperation, first.id).stage is CredentialOperationStage.CANCELLED

    assert refusal(lambda: rig.authorize(base, 55_000, token, new_challenge, nonce=nonce)) == "step_up_before_challenge"


def test_FEAT_IDEN_106__a_sweep_before_retention_ends_keeps_the_row_and_the_same_first_failure(rig, base):
    _short_session(rig, base, 30)
    challenge = rig.issue(base)
    token = rig.token(5_000, 125_000, base)  # retain_until = base + 135 s
    operation_id = rig.authorize(base, 10_000, token, challenge)
    cancel_totp_replacement(user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce)
    nonce = _sign_in_again(rig, base)

    with temporal.pinned_clock(at(base, 60_000)):  # the deadline (base + 30 s) is past; retention is not
        swept = expire_credential_operations()
    assert swept["erased"] == 0
    db.session.expire_all()
    spent = db.session.get(CredentialOperation, operation_id)
    assert spent is not None and spent.step_up_retain_until == at(base, 125_000 + S)

    new_challenge = rig.issue(base, 61_000, nonce=nonce)
    assert refusal(lambda: rig.authorize(base, 62_000, token, new_challenge, nonce=nonce)) == "step_up_before_challenge"
    # After expiresAt the first failure is the expiry, and the row is still there.
    new_challenge = rig.reset(base, 126_000)
    assert refusal(lambda: rig.authorize(base, 128_000, token, new_challenge, nonce=nonce)) == "step_up_expired"
    assert db.session.get(CredentialOperation, operation_id) is not None


# ---------------------------------------------------------------------------
# 5. the unique index, independently of every other check
# ---------------------------------------------------------------------------

def _spent_token_on_a_new_operation(rig, base):
    """A token consumed by a first operation, then offered again, otherwise qualifying, to a second.

    The evidence is crafted to pass every pure and consumption check (its timestamp is not before
    the new ``t0``): only the consumed token id can refuse it.
    """
    _short_session(rig, base, 30)
    challenge = rig.issue(base)
    token_id = str(uuid.uuid4())
    first = rig.token(5_000, 125_000, base, token_id=token_id)
    operation_id = rig.authorize(base, 10_000, first, challenge)
    cancel_totp_replacement(user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce)
    nonce = _sign_in_again(rig, base)
    new_challenge = rig.issue(base, 40_000, nonce=nonce)
    replay = rig.token(45_000, 105_000, base, token_id=token_id)  # same id, qualifying timing
    return nonce, new_challenge, replay, token_id


def test_FEAT_IDEN_106__a_consumed_token_id_is_refused_by_the_unique_index_alone(rig, base):
    nonce, new_challenge, replay, _ = _spent_token_on_a_new_operation(rig, base)

    assert refusal(lambda: rig.authorize(base, 50_000, replay, new_challenge, nonce=nonce)) == "step_up_replayed"
    (operation,) = rig.live()
    assert operation.stage is AWAITING and operation.step_up_token_id is None and operation.step_up_challenge_hash


def test_mutation_proof__without_the_unique_index_the_spent_token_authorizes_again(rig, base):
    """SOP-TEST-003 §IX.A: the index is what refuses it. Remove it and the same evidence is accepted."""
    nonce, new_challenge, replay, _ = _spent_token_on_a_new_operation(rig, base)
    db.session.rollback()
    db.session.execute(sa.text("DROP INDEX uq_credential_operations_step_up_token_id"))
    db.session.commit()

    assert refusal(lambda: rig.authorize(base, 50_000, replay, new_challenge, nonce=nonce)) is None


# ---------------------------------------------------------------------------
# 6. the sweep honors retention
# ---------------------------------------------------------------------------

def test_FEAT_IDEN_106__the_sweep_deletes_a_spent_row_only_after_its_retention_time(rig, base):
    _short_session(rig, base, 30)
    challenge = rig.issue(base)
    operation_id = rig.authorize(base, 10_000, rig.token(5_000, 125_000, base), challenge)
    cancel_totp_replacement(user_id=rig.user_id, operation_id=operation_id, session_nonce=rig.nonce)
    retain_until = 125_000 + S

    def sweep(offset_ms):
        with temporal.pinned_clock(at(base, offset_ms)):
            return expire_credential_operations()["erased"]

    def present():
        db.session.expire_all()
        return db.session.get(CredentialOperation, operation_id) is not None

    assert sweep(100_000) == 0 and present()           # deadline long past, retention not
    assert sweep(retain_until - 1_000) == 0 and present()
    assert sweep(retain_until) == 1 and not present()  # retain_until <= now deletes


def test_a_terminal_row_that_consumed_no_evidence_is_swept_at_its_deadline(rig, base):
    rig.issue(base)
    (operation,) = rig.live()
    cancel_totp_replacement(user_id=rig.user_id, operation_id=operation.id, session_nonce=rig.nonce)

    with temporal.pinned_clock(at(base, 599_000)):
        assert expire_credential_operations()["erased"] == 0
    with temporal.pinned_clock(at(base, 600_000)):
        assert expire_credential_operations()["erased"] == 1


def test_the_sweep_cancels_an_expired_challenge_and_erases_its_verifier(rig, base):
    rig.issue(base)
    with temporal.pinned_clock(at(base, 601_000)):
        assert expire_credential_operations()["cancelled"] == 1
    (operation,) = rig.operations()
    assert operation.stage is CredentialOperationStage.CANCELLED and operation.step_up_challenge_hash is None


def test_a_challenge_does_not_outlive_its_window_or_operation(rig, base):
    challenge = rig.issue(base)
    token = rig.token(10_000, 130_000, base)
    assert refusal(lambda: rig.authorize(base, W, token, challenge)) == "step_up_expired"  # now == c


def test_the_principals_deletion_cascades_to_its_operation_rows(rig, base):
    """Principal destruction removes the rows by ON DELETE CASCADE; no sweep or retention applies."""
    rule = db.session.execute(sa.text(
        "SELECT confdeltype FROM pg_constraint WHERE conrelid = 'credential_operations'::regclass "
        "AND contype = 'f' AND confrelid = 'users'::regclass")).scalar_one()
    assert rule == "c"


# ---------------------------------------------------------------------------
# 8. the provider configuration check
# ---------------------------------------------------------------------------

def _configs(**changes):
    import copy
    base_configs = copy.deepcopy(VALID_AUTH_CONFIGS)
    entry = next(e for e in base_configs["configurations"] if e["purpose"] == "totp-replace")
    entry.update(changes)
    return base_configs


BROKEN_CONFIGS = {
    "missing": {"configurations": [e for e in VALID_AUTH_CONFIGS["configurations"] if e["purpose"] != "totp-replace"]},
    "duplicated": {"configurations": VALID_AUTH_CONFIGS["configurations"] + [VALID_AUTH_CONFIGS["configurations"][1]]},
    "user verification preferred": _configs(userVerificationRequirement="preferred"),
    "user verification discouraged": _configs(userVerificationRequirement="discouraged"),
    "user verification absent": _configs(userVerificationRequirement=None),
    "ttl above L": _configs(timeToLive=121),
    "ttl zero": _configs(timeToLive=0),
    "ttl as text": _configs(timeToLive="120"),
    "ttl absent": _configs(timeToLive=None),
    "an entry without a purpose": {"configurations": VALID_AUTH_CONFIGS["configurations"] + [{"timeToLive": 5}]},
    "no envelope": {"unexpected": []},
    "a bare list without the envelope": VALID_AUTH_CONFIGS["configurations"],
    "entries not objects": {"configurations": ["totp-replace"]},
}


@pytest.mark.parametrize("name", sorted(BROKEN_CONFIGS))
def test_FEAT_IDEN_106__a_broken_provider_config_refuses_a_replacement_and_sign_in_still_works(rig, base, name):
    rig.fake.auth_configs = BROKEN_CONFIGS[name]
    self_check_replacement_is_refused_and_sign_in_works(rig, base)


def test_FEAT_IDEN_106__an_unreachable_provider_config_refuses_a_replacement(rig, base):
    rig.fake.fail_auth_configs = True
    self_check_replacement_is_refused_and_sign_in_works(rig, base)


@pytest.mark.parametrize("raw", ["not json", "", "null", "[1, 2]", "{"])
def test_FEAT_IDEN_106__an_unparseable_provider_config_refuses_a_replacement(rig, base, raw):
    rig.fake.auth_configs_raw = raw
    self_check_replacement_is_refused_and_sign_in_works(rig, base)


def self_check_replacement_is_refused_and_sign_in_works(rig, base):
    before = rig.snapshot()
    assert refusal(lambda: rig.issue(base)) == "step_up_unavailable"
    assert rig.operations() == []  # no challenge was issued
    assert rig.snapshot() == before
    response = rig.client.post("/admin/totp/replace/challenge")
    assert response.status_code == 503 and response.get_json()["code"] == "step_up_unavailable"
    # No identifier or provider content in the refusal.
    assert rig.user_id not in response.get_data(as_text=True)

    # Ordinary sign-in is unaffected: the same provider configuration is not consulted for it.
    username = TEACHERS[_teacher_key_for(rig.classroom)]["username"]
    other_client = rig.app.test_client()
    signed_in = other_client.post(
        "/admin/login", data={"username": username, "totp_code": pyotp.TOTP(HELD_SEED).at(temporal.now())})
    assert signed_in.status_code == 302
    with other_client.session_transaction() as sess:
        assert sess["user_id"] == rig.user_id


def test_FEAT_IDEN_106__the_config_is_checked_again_after_verification_and_nothing_is_consumed(rig, base):
    challenge = rig.issue(base)  # the config was valid when the challenge was issued
    before = rig.snapshot()
    token = rig.token(10_000, 70_000, base)
    rig.fake.auth_configs = _configs(userVerificationRequirement="preferred")  # relaxed before consumption

    assert refusal(lambda: rig.authorize(base, 30_000, token, challenge)) == "step_up_unavailable"

    assert rig.snapshot() == before
    (operation,) = rig.live()
    assert operation.stage is AWAITING and operation.step_up_token_id is None
    # Restored: the same evidence now qualifies (the challenge was not consumed by the refusal).
    rig.fake.auth_configs = _configs()
    assert rig.authorize(base, 31_000, token, challenge)


def test_FEAT_IDEN_106__the_config_is_read_at_the_point_of_use_twice_and_never_cached(rig, base):
    rig.fake.calls.clear()
    challenge = rig.issue(base)
    token = rig.token(10_000, 70_000, base)
    rig.authorize(base, 30_000, token, challenge)
    # One read at challenge issuance, then verification, then the second read before consumption.
    assert [c[0] for c in rig.fake.calls] == ["auth_configs", "signin_verify", "auth_configs"]


def test_FEAT_IDEN_106__the_http_challenge_and_start_use_the_stored_challenge(rig, base):
    response = rig.client.post("/admin/totp/replace/challenge")
    assert response.status_code == 200 and response.get_json()["userId"] == passkey_external_id(rig.user_id)
    started = rig.client.post("/admin/totp/replace/start", json={
        "token": rig.fake.step_up_token("cred-1"), "challenge": response.get_json()["challenge"]})
    assert started.status_code == 200 and started.get_json()["secret"]
    # The ordinary sign-in token is refused over HTTP too, with a generic answer.
    rig.client.post("/admin/totp/replace/cancel")
    fresh = rig.client.post("/admin/totp/replace/challenge").get_json()["challenge"]
    refused = rig.client.post("/admin/totp/replace/start", json={
        "token": rig.fake.sign_in_token("cred-1"), "challenge": fresh})
    assert refused.status_code == 403 and refused.get_json()["code"] == "proof_rejected"
