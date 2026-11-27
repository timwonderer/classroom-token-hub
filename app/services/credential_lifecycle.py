"""Identity-owned credential lifecycle: seed generation, compliance, TOTP replacement and passkeys.

Governed by SPEC-IDEN-002 (protocol and state inventory), DOM-IDEN-003 §VII.A
(mandatory dual enrollment, credential compliance gate), SPEC-SEC-001 §V.1 item 7
(seed-length floor and the single generator), FEAT-IDEN-106 (TOTP replacement),
FEAT-IDEN-102 (passkey enrollment) and FEAT-IDEN-107
(passkey revocation).

Two kinds of function live here and the split is deliberate:

* **Pure** functions (``decoded_secret_bits``, ``credential_compliance``,
  ``evaluate_verified_assertion``, ``evaluate_passkey_assertion``,
  ``evaluate_totp_code``) read state and decide. They write nothing: no credential,
  ``last_used``, session, challenge or audit row (SPEC-IDEN-002 §V "Proof and
  activation"). Compliance is derived from live credential state on every call;
  no completion flag is stored.
* **Commands** (``open_operation``, ``hold_totp_candidate``, ``activate_totp``,
  ``hold_pending_registration``, ``record_registered_credential``,
  ``activate_passkey``, ``commit_retirement_intent``, ``complete_retirement``,
  ``cancel_operation``, ``expire_stale_operations``) mutate and may only run inside
  the Identity FEAT that owns them (``app/feats/credential_operations_feat.py`` and
  ``app/feats/passkey_lifecycle_feat.py``). Each rechecks, at the mutation boundary,
  everything it relies on.

This module issues no provider call except the single read-only verification
of an assertion token, made before any row lock is taken. Registration tokens,
verification of a registration and remote credential deletion are made by the
orchestrating FEAT between its short local transactions (SPEC-IDEN-002 §V
"Transactions and provider I/O").
"""

from __future__ import annotations

import base64
import binascii
import hmac
import re
import secrets
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256

import pyotp
import sqlalchemy as sa
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import get_active_feat_name
from app.models import (
    CREDENTIAL_OPERATION_TERMINAL_STAGES,
    CredentialOperation,
    CredentialOperationPurpose,
    CredentialOperationStage,
    PasskeyCredential,
    User,
    UserRole,
)
from app.services import passkey_service
from app.services.passkey_service import PasskeyError, REGISTER_TOKEN_TYPE, SIGNIN_TOKEN_TYPE
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
from app.utils.encryption import decrypt_totp, encrypt_totp
from app.utils.user_ids import parse_passkey_external_id

# ---------------------------------------------------------------------------
# Seed length (SPEC-SEC-001 §V.1 item 7)
# ---------------------------------------------------------------------------

#: A stored TOTP seed below this many bits is noncompliant. pyotp >= 2.12 refuses
#: to verify against anything shorter, so a noncompliant seed is also a latent
#: lockout the moment that dependency is raised.
TOTP_MIN_SEED_BITS = 112
#: Every newly generated seed carries this many bits (32 base32 characters).
TOTP_GENERATED_SEED_BITS = 160
_BITS_PER_BASE32_CHAR = 5
TOTP_GENERATED_SEED_CHARS = TOTP_GENERATED_SEED_BITS // _BITS_PER_BASE32_CHAR

TOTP_ISSUER_NAME = "Classroom Economy Admin"


def mint_totp_secret() -> str:
    """The single TOTP seed generator: 160 bits, 32 base32 characters.

    No other code path generates a seed (SPEC-SEC-001 §V.1 item 7). Calling
    ``pyotp.random_base32()`` without a length yields only 80 bits.
    """
    return pyotp.random_base32(TOTP_GENERATED_SEED_CHARS)


def decoded_secret_bits(user: User) -> int:
    """Bit length of ``user``'s stored TOTP seed; ``0`` when there is nothing usable.

    The length is the entropy the base32 text carries: five bits per character, so
    16 characters are 80 bits, 20 are 100 and 32 are 160. A missing, undecryptable
    or non-base32 seed returns ``0`` (fail closed: it is below the floor). Pure.
    """
    encrypted = getattr(user, "totp_secret_encrypted", None)
    if not encrypted:
        return 0
    try:
        secret = decrypt_totp(encrypted)
    except (TypeError, ValueError):
        return 0
    if not secret:
        return 0
    text = "".join(secret.split()).rstrip("=").upper()
    if not text:
        return 0
    try:
        base64.b32decode(text + "=" * (-len(text) % 8))
    except (binascii.Error, ValueError):
        return 0
    return len(text) * _BITS_PER_BASE32_CHAR


# ---------------------------------------------------------------------------
# Credential compliance gate (DOM-IDEN-003 §VII.A)
# ---------------------------------------------------------------------------

class CredentialCompliance(str, Enum):
    COMPLIANT = "compliant"
    PASSKEY_MISSING = "passkey_missing"
    TOTP_NONCOMPLIANT = "totp_noncompliant"


def has_activated_passkey(user: User) -> bool:
    """Whether ``user`` holds at least one activated passkey.

    ``passkey_credentials`` holds only lawful, activated bindings (SPEC-IDEN-002 §V
    "registry contains only lawful activated bindings"); pending material lives on
    the operation row. A row is therefore activation. Pure.
    """
    return db.session.query(
        db.session.query(PasskeyCredential.id).filter_by(user_id=user.id).exists()
    ).scalar()


def credential_compliance(user: User) -> CredentialCompliance:
    """The principal's compliance, from live state, in precedence order.

    A missing passkey is reported before a short seed, so the gate always directs
    to enrollment first (a passkey is the proof TOTP replacement requires).
    Meaningful for teacher and sysadmin principals only. Pure.
    """
    if not has_activated_passkey(user):
        return CredentialCompliance.PASSKEY_MISSING
    if decoded_secret_bits(user) < TOTP_MIN_SEED_BITS:
        return CredentialCompliance.TOTP_NONCOMPLIANT
    return CredentialCompliance.COMPLIANT


# ---------------------------------------------------------------------------
# Typed proofs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PasskeyAssertion:
    """A fresh passwordless.dev assertion token and the step-up challenge it answers.

    A plain sign-in token is login proof and never operation authorization
    (SPEC-IDEN-002 §V): ``challenge`` must be one ``issue_step_up_challenge`` issued
    for this principal, purpose, session and generation.
    """
    token: str = field(repr=False)
    challenge: str = field(repr=False)


@dataclass(frozen=True)
class TotpCode:
    """A fresh code from the principal's current authenticator."""
    code: str = field(repr=False)


#: Which proof kinds may open which operation (DOM-IDEN-003 §VII.A).
_PROOFS_FOR_PURPOSE = {
    CredentialOperationPurpose.TOTP_REPLACE: (PasskeyAssertion,),
    CredentialOperationPurpose.PASSKEY_ENROLL: (TotpCode,),
    CredentialOperationPurpose.PASSKEY_REVOKE: (TotpCode,),
}

#: The FEAT that executes each purpose's commands (FEAT-IDEN-102/106/107).
FEAT_FOR_PURPOSE = {
    CredentialOperationPurpose.TOTP_REPLACE: "FEAT-IDEN-106",
    CredentialOperationPurpose.PASSKEY_ENROLL: "FEAT-IDEN-102",
    CredentialOperationPurpose.PASSKEY_REVOKE: "FEAT-IDEN-107",
}

def proof_kind_allowed(purpose: CredentialOperationPurpose, proof) -> bool:
    """Whether ``proof`` is a kind that may authorize ``purpose``. Pure."""
    # A purpose with no entry (the retired ``passkey_replace``) accepts no proof: nothing opens.
    return isinstance(proof, _PROOFS_FOR_PURPOSE.get(CredentialOperationPurpose(purpose), ()))


# ---------------------------------------------------------------------------
# Pure assertion evaluation (SPEC-IDEN-002 §V)
# ---------------------------------------------------------------------------

SIGN_IN_PURPOSE = "sign_in"
#: Purposes a passkey assertion may satisfy. Passkey maintenance is TOTP-proven.
_ASSERTION_PURPOSES = frozenset({SIGN_IN_PURPOSE, CredentialOperationPurpose.TOTP_REPLACE.value})


@dataclass(frozen=True)
class AssertionEvaluation:
    user: User
    credential_id: str


def evaluate_verified_assertion(
    verified,
    *,
    expected_role: str,
    expected_user_id: str | None,
    purpose: str,
    expected_generation: int | None = None,
) -> AssertionEvaluation:
    """Decide whether an already provider-verified token is lawful authority. Pure.

    ``verified`` is the payload ``passkey_service.verify_token`` returned. The token
    must be a successful ``passkey_signin`` assertion naming a current principal who
    holds ``expected_role`` (and is ``expected_user_id`` when the flow began from a
    known principal), and whose exact credential is an activated local binding for
    that principal. A valid provider assertion for a pending, unknown, revoked or
    foreign credential fails closed. When ``expected_generation`` is given, the
    principal's current credential generation must equal it. ``purpose`` must be one
    an assertion may satisfy. Writes nothing and consumes no challenge.
    """
    if purpose not in _ASSERTION_PURPOSES:
        raise PasskeyError("a passkey assertion cannot authorize this purpose")
    if not getattr(verified, "success", False) or getattr(verified, "type", None) != SIGNIN_TOKEN_TYPE:
        raise PasskeyError("not a successful passkey sign-in token")

    user_id = parse_passkey_external_id(getattr(verified, "user_id", None))
    credential_id = getattr(verified, "credential_id", None)
    if user_id is None or not credential_id:
        raise PasskeyError("token names no current principal")
    if expected_user_id is not None and str(expected_user_id) != user_id:
        raise PasskeyError("token names a different principal than the username entered")

    user = db.session.get(User, user_id)
    if user is None or getattr(user.user_role, "value", user.user_role) != expected_role:
        raise PasskeyError("principal missing or wrong role")
    if expected_generation is not None and user.credential_generation != expected_generation:
        raise PasskeyError("credential generation changed")

    owned = db.session.query(
        db.session.query(PasskeyCredential.id)
        .filter_by(user_id=user.id, credential_id=credential_id)
        .exists()
    ).scalar()
    if not owned:
        raise PasskeyError("credential is not recorded for this principal")
    return AssertionEvaluation(user=user, credential_id=credential_id)


def evaluate_passkey_assertion(
    token: str,
    *,
    expected_role: str,
    expected_user_id: str | None,
    purpose: str,
    expected_generation: int | None = None,
) -> AssertionEvaluation:
    """Verify ``token`` with the provider, then ``evaluate_verified_assertion``.

    Provider tokens are single use, so a command that must hold a row lock while it
    decides verifies first (``passkey_service.verify_token``), takes its lock, and
    calls ``evaluate_verified_assertion`` on the result instead of this function.
    """
    verified = passkey_service.verify_token(token)
    return evaluate_verified_assertion(
        verified, expected_role=expected_role, expected_user_id=expected_user_id,
        purpose=purpose, expected_generation=expected_generation,
    )


def evaluate_totp_code(user: User, code: str) -> bool:
    """Whether ``code`` is valid for the principal's current activated seed. Pure."""
    if not isinstance(code, str) or not user.totp_secret_encrypted:
        return False
    try:
        secret = decrypt_totp(user.totp_secret_encrypted)
        return bool(secret) and pyotp.TOTP(secret).verify(code.strip(), for_time=_now(), valid_window=1)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Step-up challenge (purpose binding for assertions)
# ---------------------------------------------------------------------------

#: Validity of a step-up challenge: the bucket it was issued in and the next one.
STEP_UP_BUCKET_SECONDS = 5 * 60
_STEP_UP_EPOCH = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def _step_up_bucket() -> int:
    elapsed = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="time_since", start=_STEP_UP_EPOCH,
    ).elapsed_seconds
    return elapsed // STEP_UP_BUCKET_SECONDS


def _step_up_value(user_id, purpose: CredentialOperationPurpose, session_nonce, generation, bucket) -> str:
    key = current_app.config["SECRET_KEY"]
    key = key.encode("utf-8") if isinstance(key, str) else key
    message = "\0".join(["credential-step-up:v1", str(user_id), purpose.value, session_nonce,
                         str(generation), str(bucket)])
    return hmac.new(key, message.encode("utf-8"), sha256).hexdigest()


def issue_step_up_challenge(user: User, *, purpose: CredentialOperationPurpose, session_nonce: str) -> str:
    """A short-lived opaque challenge binding an assertion to one purpose. Stores nothing.

    Derived by a purpose-separated HMAC over the principal, purpose, current session,
    credential generation and a five-minute time bucket, so it fails once any of them
    changes. The caller mints it when it renders the replacement step; the user's
    passkey ceremony then answers it.
    """
    purpose = CredentialOperationPurpose(purpose)
    if not isinstance(session_nonce, str) or not session_nonce or not _digests_equal(
        user.current_session_nonce, session_nonce
    ):
        raise CredentialOperationRefused("session_not_current")
    return _step_up_value(user.id, purpose, session_nonce, user.credential_generation, _step_up_bucket())


def check_step_up_challenge(
    user: User, *, purpose: CredentialOperationPurpose, session_nonce, challenge,
) -> None:
    """Refuse (``challenge_invalid``) unless ``challenge`` recomputes for this state. Pure.

    The current and the previous time bucket are accepted.
    """
    if not isinstance(session_nonce, str) or not _digests_equal(user.current_session_nonce, session_nonce):
        raise CredentialOperationRefused("session_not_current")
    if not isinstance(challenge, str):
        raise CredentialOperationRefused("challenge_invalid")
    bucket = _step_up_bucket()
    accepted = [
        _digests_equal(challenge, _step_up_value(
            user.id, purpose, session_nonce, user.credential_generation, candidate))
        for candidate in (bucket, bucket - 1)
    ]
    if not any(accepted):
        raise CredentialOperationRefused("challenge_invalid")


# ---------------------------------------------------------------------------
# Operations: errors, helpers
# ---------------------------------------------------------------------------

#: Fixed interactive lifetime (SPEC-IDEN-002 §V): ten minutes, capped by the session.
OPERATION_LIFETIME_SECONDS = 10 * 60

#: Stages a sweep may cancel after the deadline. A committed retirement and an
#: uncertain provider result are exempt from the deadline (SPEC-IDEN-002 §V) and
#: belong to their own completion workflow.
_DEADLINE_CANCELLABLE_STAGES = (
    CredentialOperationStage.AUTHORIZED,
    CredentialOperationStage.REGISTRATION_PENDING,
    CredentialOperationStage.CANDIDATE_VERIFIED,
)

_AUDIT_CATEGORY = "credential_lifecycle_outcome"


class CredentialOperationRefused(Exception):
    """A credential command was refused. ``category`` is a coarse, non-identifying reason."""

    public_message = "This credential change could not be completed."

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def _require_feat(*feat_names: str) -> None:
    active = get_active_feat_name()
    if active not in feat_names:
        raise PermissionError(
            f"Credential operation command requires one of {feat_names!r}, active={active!r}."
        )


def _now():
    return canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc


def _is_later(candidate, reference) -> bool:
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="later_than", candidate=candidate, reference=reference,
    ).is_later


def _is_earlier(candidate, reference) -> bool:
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="earlier_than", candidate=candidate, reference=reference,
    ).is_earlier


def _deadline_open(operation: CredentialOperation) -> bool:
    return _is_later(operation.deadline_at, _now())


def session_binding_digest(purpose: CredentialOperationPurpose, session_nonce: str) -> str:
    """Purpose-separated, nonreversible verifier of the browser session nonce."""
    return sha256(f"credential-operation:{purpose.value}:v1\0{session_nonce}".encode()).hexdigest()


def _session_matches(operation: CredentialOperation, user: User, session_nonce) -> bool:
    if not isinstance(session_nonce, str) or not session_nonce or not user.current_session_nonce:
        return False
    return (
        _digests_equal(operation.session_binding_hash,
                       session_binding_digest(operation.purpose, session_nonce))
        and _digests_equal(user.current_session_nonce, session_nonce)
    )


def operation_matches_session(operation: CredentialOperation, session_nonce: str) -> bool:
    """Whether ``session_nonce`` is the live session this operation was authorized for. Pure."""
    principal = db.session.get(User, operation.user_id)
    return principal is not None and _session_matches(operation, principal, session_nonce)


def _lock_user(user_id: str) -> User | None:
    return (
        db.session.query(User)
        .filter(User.id == user_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )


def _lock_operation(operation_id: str) -> CredentialOperation | None:
    return (
        db.session.query(CredentialOperation)
        .filter(CredentialOperation.id == operation_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )


def _digests_equal(left, right) -> bool:
    """Constant-time equality that tolerates non-ASCII text (``compare_digest`` on ``str`` does not)."""
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _is_open(operation: CredentialOperation) -> bool:
    return operation.stage not in CREDENTIAL_OPERATION_TERMINAL_STAGES


def get_operation_for_user(operation_id: str, user_id: str) -> CredentialOperation | None:
    """The operation, only when it belongs to ``user_id``. Pure read."""
    if not operation_id or not user_id:
        return None
    try:
        uuid.UUID(str(operation_id))
    except ValueError:
        return None
    return db.session.query(CredentialOperation).filter_by(id=str(operation_id), user_id=user_id).one_or_none()


def _erase_and_cancel(operation: CredentialOperation) -> None:
    operation.pending_totp_encrypted = None
    operation.stage = CredentialOperationStage.CANCELLED


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def verify_proof(proof):
    """Provider verification of a passkey assertion, for the caller to run *before* its transaction.

    Returns the verified payload to pass as ``open_operation(verified=...)``, or ``None``
    for proofs that need no provider call. This is the only provider I/O in the module;
    no transaction or row lock may be open while it runs (SPEC-IDEN-002 §V).
    """
    if isinstance(proof, PasskeyAssertion):
        return passkey_service.verify_token(proof.token)
    return None


def open_operation(
    user: User,
    *,
    purpose: CredentialOperationPurpose,
    proof,
    session_nonce: str,
    verified=None,
) -> CredentialOperation:
    """Authorize one credential operation for ``user`` at stage ``authorized``.

    The command, not its caller, checks that the proof kind matches the purpose
    (a passkey assertion for ``totp_replace``, already provider-verified by
    ``verify_proof`` and passed as ``verified``; a TOTP code for passkey work) and
    evaluates the proof against current state. It refuses when the principal already has an open
    operation, which the partial unique index also enforces.

    Raises ``CredentialOperationRefused`` (and ``PasskeyError`` for a refused
    assertion); nothing is written when it raises.
    """
    try:
        purpose = CredentialOperationPurpose(purpose)
    except ValueError:
        raise CredentialOperationRefused("unknown_purpose") from None
    _require_feat(FEAT_FOR_PURPOSE[purpose])
    if not proof_kind_allowed(purpose, proof):
        raise CredentialOperationRefused("proof_kind_mismatch")

    if isinstance(proof, PasskeyAssertion):
        check_step_up_challenge(user, purpose=purpose, session_nonce=session_nonce, challenge=proof.challenge)
    if isinstance(proof, PasskeyAssertion) and verified is None:
        # Provider I/O never runs inside this transaction; the caller verifies first.
        raise CredentialOperationRefused("proof_unverified")

    principal = _lock_user(user.id)
    if principal is None or principal.user_role not in (UserRole.TEACHER, UserRole.SYSADMIN):
        raise CredentialOperationRefused("ineligible_principal")
    if not principal.totp_secret_encrypted:
        raise CredentialOperationRefused("totp_not_activated")
    if (
        not isinstance(session_nonce, str) or not session_nonce
        or not principal.current_session_nonce
        or not _digests_equal(principal.current_session_nonce, session_nonce)
    ):
        raise CredentialOperationRefused("session_not_current")

    if recovery_setup_is_live(principal.id):
        raise CredentialOperationRefused("recovery_active")

    # Decide on the proof against current, locked state.
    if isinstance(proof, PasskeyAssertion):
        check_step_up_challenge(principal, purpose=purpose, session_nonce=session_nonce, challenge=proof.challenge)
        evaluate_verified_assertion(
            verified,
            expected_role=principal.user_role.value,
            expected_user_id=principal.id,
            purpose=purpose.value,
            expected_generation=principal.credential_generation,
        )
    elif isinstance(proof, TotpCode):
        if not evaluate_totp_code(principal, proof.code):
            raise CredentialOperationRefused("proof_rejected")
    else:
        raise CredentialOperationRefused("proof_rejected")

    live = (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.user_id == principal.id,
            CredentialOperation.stage.notin_(CREDENTIAL_OPERATION_TERMINAL_STAGES),
        )
        .populate_existing()
        .with_for_update()
        .all()
    )
    for stale in live:
        # An operation past its deadline holds no authority and must not block a new one.
        if stale.stage in _DEADLINE_CANCELLABLE_STAGES and not _deadline_open(stale):
            _erase_and_cancel(stale)
        else:
            raise CredentialOperationRefused("operation_already_open")

    now = _now()
    deadline = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=now, elapsed_seconds=OPERATION_LIFETIME_SECONDS,
    ).shifted_timestamp_utc
    session_end = principal.current_session_expires_at
    if session_end is not None:
        if not _is_later(session_end, now):
            raise CredentialOperationRefused("session_not_current")
        if _is_earlier(session_end, deadline):
            deadline = session_end

    operation = CredentialOperation(
        user_id=principal.id,
        purpose=purpose,
        stage=CredentialOperationStage.AUTHORIZED,
        authorized_generation=principal.credential_generation,
        session_binding_hash=session_binding_digest(purpose, session_nonce),
        deadline_at=deadline,
        attempt_count=0,
    )
    try:
        with db.session.begin_nested():
            db.session.add(operation)
            db.session.flush()
    except IntegrityError:
        raise CredentialOperationRefused("operation_already_open") from None
    return operation


def hold_totp_candidate(
    operation: CredentialOperation,
    *,
    session_nonce: str,
    account_name: str,
    issuer_name: str = TOTP_ISSUER_NAME,
) -> tuple[str, str]:
    """Hold a new 160-bit seed on the operation and return ``(secret, provisioning_uri)``.

    The seed is stored Fernet-encrypted on the operation only; the principal's
    current secret is untouched and the stage stays ``authorized``. Calling again
    returns the seed already held (a page refresh), never a second seed.
    ``account_name`` appears only in the returned URI; it is not persisted.
    """
    _require_feat(FEAT_FOR_PURPOSE[CredentialOperationPurpose.TOTP_REPLACE])
    principal = _lock_user(operation.user_id)
    locked = _lock_operation(operation.id)
    _recheck_open_totp_operation(principal, locked, session_nonce)
    if locked.pending_totp_encrypted:
        secret = decrypt_totp(locked.pending_totp_encrypted)
    else:
        secret = mint_totp_secret()
        locked.pending_totp_encrypted = encrypt_totp(secret)
        db.session.flush()
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer_name)
    return secret, uri


def _recheck_open_totp_operation(principal, operation, session_nonce) -> None:
    """The mutation-boundary rechecks every TOTP-replacement command repeats."""
    if principal is None or operation is None or operation.user_id != principal.id:
        raise CredentialOperationRefused("operation_not_found")
    if operation.purpose is not CredentialOperationPurpose.TOTP_REPLACE:
        raise CredentialOperationRefused("wrong_purpose")
    if operation.stage is not CredentialOperationStage.AUTHORIZED:
        raise CredentialOperationRefused("operation_not_open")
    if principal.credential_generation != operation.authorized_generation:
        raise CredentialOperationRefused("stale_generation")
    if not _deadline_open(operation):
        raise CredentialOperationRefused("operation_expired")
    if not _session_matches(operation, principal, session_nonce):
        raise CredentialOperationRefused("session_not_current")


def activate_totp(operation: CredentialOperation, code: str, *, session_nonce: str) -> bool:
    """Activate the held seed if ``code`` proves it, in one transaction.

    Locks the principal and the operation, then rechecks stage, generation,
    deadline and session binding. ``code`` is verified against the seed held on the
    operation, never a browser-supplied value. On success the principal's seed is
    overwritten, ``credential_generation`` advances, the sign-in is voided by
    rotating ``current_session_nonce``, the operation completes, the pending seed
    is erased and ACT-IDEN-106 is emitted. Returns ``True``.

    A wrong code returns ``False`` having changed nothing: the principal's secret is
    byte-identical and the operation stays open until its deadline. Every other
    refusal raises ``CredentialOperationRefused`` and rolls the command back.
    """
    _require_feat(FEAT_FOR_PURPOSE[CredentialOperationPurpose.TOTP_REPLACE])
    principal = _lock_user(operation.user_id)
    locked = _lock_operation(operation.id)
    _recheck_open_totp_operation(principal, locked, session_nonce)
    if not locked.pending_totp_encrypted:
        raise CredentialOperationRefused("no_candidate_held")

    try:
        pending = decrypt_totp(locked.pending_totp_encrypted)
        accepted = (
            isinstance(code, str) and bool(pending)
            and pyotp.TOTP(pending).verify(code.strip(), for_time=_now(), valid_window=1)
        )
    except (TypeError, ValueError):
        accepted = False
    if not accepted:
        return False

    # Time passed during verification; recheck before any mutation.
    if not _deadline_open(locked):
        raise CredentialOperationRefused("operation_expired")

    principal.totp_secret_encrypted = locked.pending_totp_encrypted
    principal.credential_generation = principal.credential_generation + 1
    principal.current_session_nonce = secrets.token_hex(32)
    locked.pending_totp_encrypted = None
    locked.stage = CredentialOperationStage.COMPLETED
    db.session.flush()
    _emit_outcome(
        action="ACT-IDEN-106",
        actor_type=principal.user_role.value,
        stage_before=CredentialOperationStage.AUTHORIZED.value,
        stage_after=CredentialOperationStage.COMPLETED.value,
        outcome="activated",
    )
    return True


def cancel_operation(
    operation: CredentialOperation, *, purpose: CredentialOperationPurpose | None = None,
) -> bool:
    """Erase pending material and mark the operation cancelled.

    When ``purpose`` is given the operation must have it. Returns ``False`` without effect when it is already terminal. The caller (a
    FEAT entry) is responsible for the actor's authority; this command only
    performs the erasure.
    """
    _require_feat("FEAT-IDEN-102", "FEAT-IDEN-106", "FEAT-IDEN-107", "FEAT-IDEN-108")
    locked = _lock_operation(operation.id)
    if purpose is not None and locked is not None and locked.purpose is not purpose:
        # A FEAT may cancel only the kind of operation it owns.
        raise CredentialOperationRefused("wrong_purpose")
    return _cancel_locked(locked)


def _cancel_locked(locked: CredentialOperation | None) -> bool:
    if locked is None or not _is_open(locked):
        return False
    _erase_and_cancel(locked)
    db.session.flush()
    return True


def expire_stale_operations() -> dict[str, int]:
    """Drop spent receipts, then cancel open operations past their deadline.

    Cancelling erases the pending seed. A completed or cancelled operation is kept
    only as a receipt until its original interactive deadline has passed
    (SPEC-IDEN-002 §V), after which a sweep deletes it, so a replay then fails closed
    on a missing row. Receipts are dropped before this run's cancellations are made,
    so a newly cancelled operation is visible as ``cancelled`` until the next sweep.
    Operations in ``retirement_committed`` or ``provider_uncertain`` are exempt from
    the deadline and left to their own completion workflow. Returns the counts.
    """
    _require_feat("FEAT-IDEN-108")
    now = _now()
    erased = (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.stage.in_(CREDENTIAL_OPERATION_TERMINAL_STAGES),
            CredentialOperation.deadline_at <= now,
        )
        .delete(synchronize_session=False)
    )
    cancelled = 0
    candidates = (
        db.session.query(CredentialOperation.id)
        .filter(
            CredentialOperation.stage.in_(_DEADLINE_CANCELLABLE_STAGES),
            CredentialOperation.deadline_at <= now,
        )
        .all()
    )
    for (operation_id,) in candidates:
        locked = _lock_operation(operation_id)
        if (
            locked is not None
            and locked.stage in _DEADLINE_CANCELLABLE_STAGES
            and not _deadline_open(locked)
            and _cancel_locked(locked)
        ):
            cancelled += 1
    return {"cancelled": cancelled, "erased": erased}


def recovery_setup_is_live(user_id: str) -> bool:
    """Whether the principal holds a live SATAR setup grant (an unexpired pending recovery). Pure."""
    requests = db.metadata.tables["recovery_requests"]
    rows = db.session.execute(
        sa.select(requests.c.expires_at).where(
            requests.c.user_id == user_id,
            requests.c.status == "pending",
            requests.c.completed_at.is_(None),
            requests.c.setup_nonce_hash.isnot(None),
        )
    ).all()
    return any(_is_later(row.expires_at, _now()) for row in rows)


def supersede_for_recovery(user: User) -> int:
    """SATAR aggregate success supersedes routine maintenance (DOM-IDEN-003 §VII.A).

    Advances ``credential_generation`` and cancels the principal's open operations,
    erasing pending material, so no stale continuation can activate. ``user`` must be
    row-locked by the caller (FEAT-IDEN-105's recovery lock). Returns the number cancelled.
    """
    _require_feat("FEAT-IDEN-105")
    user.credential_generation = user.credential_generation + 1
    cancelled = 0
    for operation in (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.user_id == user.id,
            CredentialOperation.stage.notin_(CREDENTIAL_OPERATION_TERMINAL_STAGES),
        )
        .populate_existing()
        .with_for_update()
        .all()
    ):
        _erase_and_cancel(operation)
        cancelled += 1
    db.session.flush()
    return cancelled


def _emit_outcome(*, action: str, actor_type: str, stage_before: str, stage_after: str, outcome: str) -> None:
    """DOM-OPS-002 §2.5 outcome envelope: fixed values only, nothing that names a principal."""
    from app.services.audit_service import emit_audit_event

    fields = {
        "action": action,
        "execution_mode": "interactive",
        "stage_before": stage_before,
        "stage_after": stage_after,
        "outcome": outcome,
    }
    emit_audit_event(
        _AUDIT_CATEGORY, str(uuid.uuid4()), "TRANSITION", fields, actor_type=actor_type,
    )


# ---------------------------------------------------------------------------
# Passkey operations: enrollment and revocation
# (FEAT-IDEN-102, FEAT-IDEN-107; SPEC-IDEN-002 §V workflow stages)
# ---------------------------------------------------------------------------

#: Stands in for the session binding verifier once it is consumed into a retirement
#: intent (SPEC-IDEN-002 §VI: erase on consumption). It is not the digest of any nonce.
ERASED_SESSION_BINDING = "0" * 64

PASSKEY_PURPOSES = (
    CredentialOperationPurpose.PASSKEY_ENROLL,
    CredentialOperationPurpose.PASSKEY_REVOKE,
)
#: Stages before interactive authorization is consumed; they obey the deadline and session.
PRE_INTENT_STAGES = _DEADLINE_CANCELLABLE_STAGES
#: Stages after retirement intent; only the fixed operation may finish (SPEC-IDEN-002 §V).
RETIREMENT_STAGES = (
    CredentialOperationStage.RETIREMENT_COMMITTED,
    CredentialOperationStage.PROVIDER_UNCERTAIN,
)

COMPLETED = "completed"
ALREADY_COMPLETED = "already_completed"

_ACTION_FOR_PURPOSE = {
    CredentialOperationPurpose.PASSKEY_ENROLL: "ACT-IDEN-102",
    CredentialOperationPurpose.PASSKEY_REVOKE: "ACT-IDEN-107",
}
_OUTCOME_FOR_PURPOSE = {
    CredentialOperationPurpose.PASSKEY_ENROLL: "activated",
    CredentialOperationPurpose.PASSKEY_REVOKE: "revoked",
}


def get_open_operation(user_id: str) -> CredentialOperation | None:
    """The principal's one open operation, if any. Pure read."""
    if not user_id:
        return None
    return (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.user_id == user_id,
            CredentialOperation.stage.notin_(CREDENTIAL_OPERATION_TERMINAL_STAGES),
        )
        .one_or_none()
    )


#: A provider registration token's own lifetime; the SDK default, stated so it is not implicit.
REGISTRATION_TOKEN_SECONDS = 2 * 60


def registration_token_expiry(deadline_at):
    """When a registration token issued now must expire: two minutes, never past ``deadline_at``.

    SPEC-IDEN-002 §V: a new provider token must not outlive the registration deadline. Pure.
    """
    expiry = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=_now(), elapsed_seconds=REGISTRATION_TOKEN_SECONDS,
    ).shifted_timestamp_utc
    return deadline_at if _is_earlier(deadline_at, expiry) else expiry


def registration_binding(operation: CredentialOperation) -> str:
    """The value that ties a finish request to the operation whose start issued the token.

    A purpose-separated HMAC over the principal and the operation id, handed to the browser
    with the registration token and returned with the finished registration. A token from
    a cancelled or superseded operation carries the old operation's value and so cannot
    complete a later one. Derived, stored nowhere; the operation id is independently random.
    """
    key = current_app.config["SECRET_KEY"]
    key = key.encode("utf-8") if isinstance(key, str) else key
    message = "\0".join(["passkey-registration:v1", str(operation.user_id), str(operation.id)])
    return hmac.new(key, message.encode("utf-8"), sha256).hexdigest()


_BINDING_SHAPE = re.compile(r"[0-9a-f]{64}")


def _is_binding_shaped(value) -> bool:
    """True for exactly 64 lowercase ASCII hex characters, the only shape ``registration_binding`` yields.

    Checked before any comparison so a malformed value (for example one holding an unpaired
    surrogate, which cannot be encoded) is an ordinary refusal and never an error.
    """
    return isinstance(value, str) and _BINDING_SHAPE.fullmatch(value) is not None


def check_registration_binding(operation: CredentialOperation, binding) -> None:
    """Refuse (``binding_mismatch``) unless ``binding`` is this operation's registration binding. Pure."""
    if not _is_binding_shaped(binding) or not _digests_equal(registration_binding(operation), binding):
        raise CredentialOperationRefused("binding_mismatch")


def check_registered_nickname(operation: CredentialOperation, nickname) -> None:
    """Refuse (``binding_mismatch``) unless the provider-returned credential nickname is this operation's binding.

    The nickname is what the browser registered the credential under (the start's binding), so
    this ties the provider's own record of the registration to the operation. Pure.
    """
    check_registration_binding(operation, nickname)


def receipt_outcome_for_binding(user_id: str, binding, *purposes: CredentialOperationPurpose) -> str | None:
    """The outcome of the principal's completed operation that ``binding`` names, if its receipt remains.

    The binding identifies one operation (it is derived from the operation id), so a retry
    is answered only from the receipt of the operation it belongs to: never from another
    completed operation of the same principal and purpose. Receipts are kept only until
    the operation's original interactive deadline (SPEC-IDEN-002 §V). Pure read.
    """
    if not _is_binding_shaped(binding):
        return None
    receipts = (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.user_id == user_id,
            CredentialOperation.purpose.in_(purposes),
            CredentialOperation.stage == CredentialOperationStage.COMPLETED,
        )
        .all()
    )
    for receipt in receipts:
        # A receipt past its operation's original deadline is no longer an answer (the
        # comparison is the resolver's).
        if _deadline_open(receipt) and _digests_equal(registration_binding(receipt), binding):
            return _OUTCOME_FOR_PURPOSE[receipt.purpose]
    return None


def require_current_generation(operation: CredentialOperation) -> None:
    """Refuse (``stale_generation``) unless the principal's generation is the one recorded at authorization.

    Run before any provider call for committed work: a recovery or destruction that
    superseded the operation must not be followed by a remote deletion. Pure.
    """
    current = (
        db.session.query(User.credential_generation)
        .filter(User.id == operation.user_id)
        .scalar()
    )
    if current is None or current != operation.authorized_generation:
        raise CredentialOperationRefused("stale_generation")


def open_passkey_operation_state(user_id: str) -> str | None:
    """How the principal's open passkey operation presents: ``"registering"``,
    ``"retirement_pending"`` or ``None``. Pure read, for rendering the settings page."""
    return open_passkey_operation_presentation(user_id)[0]


def open_passkey_operation_presentation(user_id: str) -> tuple[str | None, str | None]:
    """The open passkey operation's ``(state, binding)`` from one lookup, so a page renders both from the same row.

    ``state`` is as ``open_passkey_operation_state``; ``binding`` is the registration binding
    of that operation (for the retry and cancel controls), ``None`` whenever there is no state.
    Pure read.
    """
    operation = get_open_operation(user_id)
    if operation is None or operation.purpose not in PASSKEY_PURPOSES:
        return None, None
    if operation.stage in RETIREMENT_STAGES:
        return "retirement_pending", registration_binding(operation)
    if _deadline_open(operation):
        return "registering", registration_binding(operation)
    return None, None


def _lock_passkey_operation(operation: CredentialOperation, *purposes: CredentialOperationPurpose):
    principal = _lock_user(operation.user_id)
    locked = _lock_operation(operation.id)
    if (
        principal is None or locked is None or locked.user_id != principal.id
        or principal.user_role not in (UserRole.TEACHER, UserRole.SYSADMIN)
    ):
        raise CredentialOperationRefused("operation_not_found")
    if locked.purpose not in purposes:
        raise CredentialOperationRefused("wrong_purpose")
    _require_feat(FEAT_FOR_PURPOSE[locked.purpose])
    return principal, locked


def _recheck_pre_intent(principal, operation, stage, session_nonce) -> None:
    """Mutation-boundary rechecks for every step before retirement intent is committed."""
    if operation.stage is not stage:
        raise CredentialOperationRefused("operation_not_open")
    if principal.credential_generation != operation.authorized_generation:
        raise CredentialOperationRefused("stale_generation")
    if not _deadline_open(operation):
        raise CredentialOperationRefused("operation_expired")
    if not _session_matches(operation, principal, session_nonce):
        raise CredentialOperationRefused("session_not_current")


def hold_pending_registration(operation: CredentialOperation, *, session_nonce: str) -> CredentialOperation:
    """Persist the pending registration, before any provider token is issued (FEAT-IDEN-102 §V).

    Moves an ``authorized`` enrollment to ``registration_pending``.
    """
    principal, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_ENROLL)
    _recheck_pre_intent(principal, locked, CredentialOperationStage.AUTHORIZED, session_nonce)
    locked.stage = CredentialOperationStage.REGISTRATION_PENDING
    db.session.flush()
    return locked


def _owned_binding(principal: User, passkey_row_id) -> PasskeyCredential:
    """The activated binding ``passkey_row_id`` names, only when ``principal`` owns it."""
    try:
        row_id = int(passkey_row_id)
    except (TypeError, ValueError):
        raise CredentialOperationRefused("credential_not_found") from None
    row = db.session.query(PasskeyCredential).filter_by(id=row_id, user_id=principal.id).one_or_none()
    if row is None:
        raise CredentialOperationRefused("credential_not_found")
    return row


def record_registered_credential(operation: CredentialOperation, verified, *, session_nonce: str) -> CredentialOperation:
    """Durably record the provider-verified registration as the pending candidate.

    ``verified`` is the payload ``passkey_service.verify_token`` returned for the token
    ``p.register()`` produced. It must be a successful ``passkey_register`` token naming
    this principal and a credential id that no local binding holds. The candidate is recorded on the operation only; the
    registry gains nothing and the candidate cannot sign in.
    """
    principal, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_ENROLL)
    _recheck_pre_intent(principal, locked, CredentialOperationStage.REGISTRATION_PENDING, session_nonce)
    if not getattr(verified, "success", False) or getattr(verified, "type", None) != REGISTER_TOKEN_TYPE:
        raise CredentialOperationRefused("registration_rejected")
    if parse_passkey_external_id(getattr(verified, "user_id", None)) != str(principal.id):
        raise CredentialOperationRefused("registration_rejected")
    # The registration carries the issuing operation's binding as the credential nickname the
    # provider stores and returns on verification, so a registration made under another
    # (cancelled or superseded) operation cannot be recorded under this one.
    check_registered_nickname(locked, getattr(verified, "nickname", None))
    credential_id = getattr(verified, "credential_id", None)
    if not credential_id or not isinstance(credential_id, str):
        raise CredentialOperationRefused("registration_rejected")
    if db.session.query(db.session.query(PasskeyCredential.id).filter_by(credential_id=credential_id).exists()).scalar():
        raise CredentialOperationRefused("registration_rejected")
    locked.new_credential_id = credential_id
    locked.stage = CredentialOperationStage.CANDIDATE_VERIFIED
    db.session.flush()
    return locked


def _complete_locked(principal: User, operation: CredentialOperation, *, stage_before: CredentialOperationStage) -> None:
    """The one place a passkey operation completes: generation, sign-in, receipt, outcome."""
    purpose = operation.purpose
    principal.credential_generation = principal.credential_generation + 1
    principal.current_session_nonce = secrets.token_hex(32)
    operation.stage = CredentialOperationStage.COMPLETED
    operation.old_credential_id = None
    operation.new_credential_id = None
    operation.session_binding_hash = ERASED_SESSION_BINDING
    operation.retry_after_at = None
    operation.error_category = None
    db.session.flush()
    _emit_outcome(
        action=_ACTION_FOR_PURPOSE[purpose],
        actor_type=principal.user_role.value,
        stage_before=stage_before.value,
        stage_after=CredentialOperationStage.COMPLETED.value,
        outcome=_OUTCOME_FOR_PURPOSE[purpose],
    )


AUTHENTICATOR_NAME_FALLBACK = "Unnamed Passkey"
AUTHENTICATOR_NAME_MAX = 100


def normalize_authenticator_name(name) -> str:
    """A display label safe to store: control characters dropped, trimmed, at most 100 characters.

    NUL and every other Unicode control, format or separator-line character is removed
    (a label is display text and never authority); a blank result is the fallback. Pure.
    """
    if not isinstance(name, str):
        return AUTHENTICATOR_NAME_FALLBACK
    kept = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))
    return kept.strip()[:AUTHENTICATOR_NAME_MAX].strip() or AUTHENTICATOR_NAME_FALLBACK


def _bind(principal: User, credential_id: str, authenticator_name) -> None:
    """Activate ``credential_id`` as a binding of ``principal``: the registry's only writer."""
    name = normalize_authenticator_name(authenticator_name)
    try:
        with db.session.begin_nested():
            db.session.add(PasskeyCredential(
                user_id=principal.id, credential_id=credential_id, authenticator_name=name,
            ))
            db.session.flush()
    except IntegrityError:
        raise CredentialOperationRefused("registration_rejected") from None


def activate_passkey(operation: CredentialOperation, *, authenticator_name: str, session_nonce: str) -> str:
    """Activate the verified candidate of an enrollment, once.

    Locks the principal and the operation and rechecks stage, generation, deadline and
    session. Writes the binding, advances ``credential_generation``, voids the sign-in
    (which also voids every step-up challenge), completes the operation, erases its
    credential ids and emits ACT-IDEN-102. A completed operation returns
    ``ALREADY_COMPLETED`` with none of those effects.
    """
    principal, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_ENROLL)
    if locked.stage is CredentialOperationStage.COMPLETED:
        return ALREADY_COMPLETED
    _recheck_pre_intent(principal, locked, CredentialOperationStage.CANDIDATE_VERIFIED, session_nonce)
    _bind(principal, locked.new_credential_id, authenticator_name)
    _complete_locked(principal, locked, stage_before=CredentialOperationStage.CANDIDATE_VERIFIED)
    return COMPLETED


def _commit_intent(operation: CredentialOperation, old_credential_id: str) -> None:
    operation.old_credential_id = old_credential_id
    operation.stage = CredentialOperationStage.RETIREMENT_COMMITTED
    operation.retirement_intent_at = _now()
    operation.session_binding_hash = ERASED_SESSION_BINDING
    db.session.flush()


def commit_revocation_intent(
    operation: CredentialOperation, *, passkey_id: int, session_nonce: str,
) -> CredentialOperation:
    """Record the exact credential a revocation retires and commit its retirement intent.

    The selected binding must be this principal's and activated, TOTP must still be
    available, and the principal must hold another activated passkey: revoking the only
    one is refused (FEAT-IDEN-107 §V; enroll a new passkey first, then revoke the old one).
    """
    principal, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_REVOKE)
    _recheck_pre_intent(principal, locked, CredentialOperationStage.AUTHORIZED, session_nonce)
    selected = _owned_binding(principal, passkey_id)
    if not principal.totp_secret_encrypted:
        raise CredentialOperationRefused("totp_not_activated")
    held = db.session.query(PasskeyCredential).filter_by(user_id=principal.id).count()
    if held < 2:
        raise CredentialOperationRefused("only_passkey")
    _commit_intent(locked, selected.credential_id)
    return locked


def record_provider_uncertain(operation: CredentialOperation) -> bool:
    """Record that remote retirement was attempted and not confirmed; the fixed work stays pending.

    Keeps only a bounded counter and a coarse category (SPEC-IDEN-002 §VI). Returns
    ``False`` without effect when the operation is no longer awaiting retirement.
    """
    _, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_REVOKE)
    if locked.stage not in RETIREMENT_STAGES:
        return False
    locked.stage = CredentialOperationStage.PROVIDER_UNCERTAIN
    locked.attempt_count = locked.attempt_count + 1
    locked.error_category = "provider_unavailable"
    db.session.flush()
    return True


def complete_retirement(operation: CredentialOperation) -> str:
    """Finish a revocation after the credential is confirmed gone remotely.

    Locks the principal and the operation and rechecks the recorded stage and the
    generation (a recovery or any other credential change advances it and supersedes
    the work). The deadline and the session are deliberately not consulted: retirement
    intent was committed inside them. Atomically hard-deletes only the selected local
    binding, advances ``credential_generation``, voids the sign-in, completes the
    operation and emits ACT-IDEN-107. A completed operation returns ``ALREADY_COMPLETED`` with
    none of those effects.
    """
    principal, locked = _lock_passkey_operation(operation, CredentialOperationPurpose.PASSKEY_REVOKE)
    if locked.stage is CredentialOperationStage.COMPLETED:
        return ALREADY_COMPLETED
    if locked.stage not in RETIREMENT_STAGES:
        raise CredentialOperationRefused("operation_not_open")
    if principal.credential_generation != locked.authorized_generation:
        raise CredentialOperationRefused("stale_generation")
    stage_before = locked.stage
    old = (
        db.session.query(PasskeyCredential)
        .filter_by(user_id=principal.id, credential_id=locked.old_credential_id)
        .one_or_none()
    )
    if old is None:
        raise CredentialOperationRefused("credential_not_found")
    db.session.delete(old)
    db.session.flush()
    _complete_locked(principal, locked, stage_before=stage_before)
    return COMPLETED


# ---------------------------------------------------------------------------
# Principal reconciliation: local scope, revalidation and outcome (FEAT-IDEN-108 §V-§VI)
# ---------------------------------------------------------------------------

#: The stages at which each passkey purpose may be reconciled: an enrollment between
#: recording and activating its candidate, a revocation between confirmed
#: remote retirement and local completion. ``registration_pending`` (a lawful registration
#: whose credential id is not yet known) is scoped too, so that any caller reconciling then
#: has every provider-only entry protected rather than refused or guessed at.
_RECONCILIATION_STAGES = {
    CredentialOperationPurpose.PASSKEY_ENROLL: (
        CredentialOperationStage.REGISTRATION_PENDING, CredentialOperationStage.CANDIDATE_VERIFIED,
    ),
    CredentialOperationPurpose.PASSKEY_REVOKE: RETIREMENT_STAGES,
}


@dataclass(frozen=True)
class ReconciliationScope:
    """What the principal's local state lawfully holds at a reconciliation boundary.

    Exact credential ids only, kept in memory for the one reconciliation and never persisted
    or emitted. ``pending_registration_unknown`` is true when a lawful registration is in
    flight whose credential id is not recorded.
    """

    actor_type: str
    stage: str
    active_ids: tuple[str, ...]
    pending_id: str | None
    retiring_id: str | None
    pending_registration_unknown: bool


def reconciliation_scope(operation: CredentialOperation) -> ReconciliationScope | None:
    """The principal's local authority for reconciliation, read from current state. Pure read.

    ``None`` when the operation already completed (a concurrent request finished it: there
    is nothing left to reconcile and the caller's own completion is then a replay). Refuses
    ``operation_not_found`` for another principal's or an absent operation, ``stale_generation``
    when a recovery or destruction superseded it, and ``operation_not_open`` at any stage
    other than the purpose's reconciliation boundary. Reads only principal eligibility,
    activated credentials and the operation's own recorded ids.
    """
    principal = db.session.get(User, operation.user_id)
    current = db.session.get(CredentialOperation, operation.id)
    if (
        principal is None or current is None or current.user_id != principal.id
        or principal.user_role not in (UserRole.TEACHER, UserRole.SYSADMIN)
        or current.purpose not in _RECONCILIATION_STAGES
    ):
        raise CredentialOperationRefused("operation_not_found")
    if current.stage is CredentialOperationStage.COMPLETED:
        return None
    if current.stage not in _RECONCILIATION_STAGES[current.purpose]:
        raise CredentialOperationRefused("operation_not_open")
    if principal.credential_generation != current.authorized_generation:
        raise CredentialOperationRefused("stale_generation")
    active = tuple(
        row[0] for row in db.session.query(PasskeyCredential.credential_id).filter_by(user_id=principal.id).all()
    )
    return ReconciliationScope(
        actor_type=principal.user_role.value,
        stage=current.stage.value,
        active_ids=active,
        pending_id=current.new_credential_id or None,
        retiring_id=current.old_credential_id or None,
        pending_registration_unknown=(
            current.purpose is not CredentialOperationPurpose.PASSKEY_REVOKE and not current.new_credential_id
        ),
    )


def reconciliation_target_is_still_provider_only(operation: CredentialOperation, credential_id: str) -> bool:
    """Revalidate, from current local state, that ``credential_id`` may still be retired. Pure read.

    Re-reads the scope (refusing on a superseded generation or a moved stage) and requires
    that the id is bound by no principal, is neither the recorded candidate nor the retiring
    credential, and that no registration of unknown id is in flight. ``False`` when the
    operation completed meanwhile. The caller deletes remotely only on ``True``.
    """
    scope = reconciliation_scope(operation)
    if scope is None or scope.pending_registration_unknown:
        return False
    keys = {passkey_service.credential_match_key(i) for i in (*scope.active_ids, scope.pending_id, scope.retiring_id) if i}
    if passkey_service.credential_match_key(credential_id) in keys:
        return False
    return not db.session.query(
        db.session.query(PasskeyCredential.id).filter_by(credential_id=credential_id).exists()
    ).scalar()


def emit_reconciliation_outcome(scope: ReconciliationScope, *, outcome: str) -> None:
    """Emit one non-identifying principal-reconciliation outcome (DOM-OPS-002 §2.5, ACT-IDEN-108).

    Fixed action, mode, stage and outcome category only: no principal, credential, operation
    or provider value. Runs inside the lifecycle FEAT that invoked reconciliation.
    """
    _require_feat(*{FEAT_FOR_PURPOSE[p] for p in PASSKEY_PURPOSES})
    _emit_outcome(
        action="ACT-IDEN-108", actor_type=scope.actor_type,
        stage_before=scope.stage, stage_after=scope.stage, outcome=outcome,
    )


def cancel_before_retirement(operation: CredentialOperation, *, session_nonce: str) -> bool:
    """Cancel a passkey operation that has not yet committed retirement intent.

    The principal's bindings are untouched. A registration the browser already finished
    remotely is then cleanup-only (FEAT-IDEN-102 §VII); the recorded credential id stays
    on the cancelled receipt for that cleanup until the sweep erases the receipt. Refused once retirement intent is committed. Returns ``False``
    without effect when the operation is already terminal.
    """
    principal, locked = _lock_passkey_operation(operation, *PASSKEY_PURPOSES)
    if not _is_open(locked):
        return False
    if locked.stage not in PRE_INTENT_STAGES:
        raise CredentialOperationRefused("retirement_committed")
    if not _session_matches(locked, principal, session_nonce):
        raise CredentialOperationRefused("session_not_current")
    _erase_and_cancel(locked)
    db.session.flush()
    return True
