"""Identity-owned credential lifecycle: seed generation, compliance and TOTP replacement.

Governed by SPEC-IDEN-002 (protocol and state inventory), DOM-IDEN-003 §VII.A
(mandatory dual enrollment, credential compliance gate), SPEC-SEC-001 §V.1 item 7
(seed-length floor and the single generator) and FEAT-IDEN-106 (TOTP replacement).

Two kinds of function live here and the split is deliberate:

* **Pure** functions (``decoded_secret_bits``, ``credential_compliance``,
  ``evaluate_verified_assertion``, ``evaluate_passkey_assertion``,
  ``evaluate_totp_code``) read state and decide. They write nothing: no credential,
  ``last_used``, session, challenge or audit row (SPEC-IDEN-002 §V "Proof and
  activation"). Compliance is derived from live credential state on every call;
  no completion flag is stored.
* **Commands** (``open_operation``, ``hold_totp_candidate``, ``activate_totp``,
  ``cancel_operation``, ``expire_stale_operations``) mutate and may only run inside
  the Identity FEAT that owns them (``app/feats/credential_operations_feat.py``).
  Each rechecks, at the mutation boundary, everything it relies on.

Passkey workflow commands that retire or register credentials remotely are not
here. This module issues no provider call except the single read-only verification
of an assertion token, made before any row lock is taken (SPEC-IDEN-002 §V
"Transactions and provider I/O").
"""

from __future__ import annotations

import base64
import binascii
import hmac
import secrets
import uuid
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256

import pyotp
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
from app.services.passkey_service import PasskeyError, SIGNIN_TOKEN_TYPE
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
    """A fresh passwordless.dev assertion token."""
    token: str = field(repr=False)


@dataclass(frozen=True)
class TotpCode:
    """A fresh code from the principal's current authenticator."""
    code: str = field(repr=False)


@dataclass(frozen=True)
class SignupCapability:
    """The signup-derived five-minute enrollment capability (FEAT-IDEN-101)."""
    nonce: str = field(repr=False)


#: Which proof kinds may open which operation (DOM-IDEN-003 §VII.A).
_PROOFS_FOR_PURPOSE = {
    CredentialOperationPurpose.TOTP_REPLACE: (PasskeyAssertion,),
    CredentialOperationPurpose.PASSKEY_ENROLL: (TotpCode, SignupCapability),
    CredentialOperationPurpose.PASSKEY_REPLACE: (TotpCode,),
    CredentialOperationPurpose.PASSKEY_REVOKE: (TotpCode,),
}

#: The FEAT that executes each purpose's commands (FEAT-IDEN-102/106/107).
FEAT_FOR_PURPOSE = {
    CredentialOperationPurpose.TOTP_REPLACE: "FEAT-IDEN-106",
    CredentialOperationPurpose.PASSKEY_ENROLL: "FEAT-IDEN-102",
    CredentialOperationPurpose.PASSKEY_REPLACE: "FEAT-IDEN-102",
    CredentialOperationPurpose.PASSKEY_REVOKE: "FEAT-IDEN-107",
}

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
        return bool(secret) and pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Operations: errors, helpers
# ---------------------------------------------------------------------------

#: Fixed interactive lifetime (SPEC-IDEN-002 §V): ten minutes, capped by the session.
OPERATION_LIFETIME_SECONDS = 10 * 60
#: Wrong-code budget against a pending seed; the operation is cancelled when spent.
MAX_CODE_ATTEMPTS = 5

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
        hmac.compare_digest(operation.session_binding_hash,
                            session_binding_digest(operation.purpose, session_nonce))
        and hmac.compare_digest(user.current_session_nonce, session_nonce)
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

def open_operation(
    user: User,
    *,
    purpose: CredentialOperationPurpose,
    proof,
    session_nonce: str,
) -> CredentialOperation:
    """Authorize one credential operation for ``user`` at stage ``authorized``.

    The command, not its caller, checks that the proof kind matches the purpose
    (a passkey assertion for ``totp_replace``; a TOTP code, or for the first
    passkey enrollment the signup capability, for passkey work) and evaluates the
    proof against current state. It refuses when the principal already has an open
    operation, which the partial unique index also enforces.

    Raises ``CredentialOperationRefused`` (and ``PasskeyError`` for a refused
    assertion); nothing is written when it raises.
    """
    try:
        purpose = CredentialOperationPurpose(purpose)
    except ValueError:
        raise CredentialOperationRefused("unknown_purpose") from None
    _require_feat(FEAT_FOR_PURPOSE[purpose])
    if not isinstance(proof, _PROOFS_FOR_PURPOSE[purpose]):
        raise CredentialOperationRefused("proof_kind_mismatch")

    # Provider I/O first: nothing is locked while the network call runs.
    verified = passkey_service.verify_token(proof.token) if isinstance(proof, PasskeyAssertion) else None

    principal = _lock_user(user.id)
    if principal is None or principal.user_role not in (UserRole.TEACHER, UserRole.SYSADMIN):
        raise CredentialOperationRefused("ineligible_principal")
    if not principal.totp_secret_encrypted:
        raise CredentialOperationRefused("totp_not_activated")
    if (
        not isinstance(session_nonce, str) or not session_nonce
        or not principal.current_session_nonce
        or not hmac.compare_digest(principal.current_session_nonce, session_nonce)
    ):
        raise CredentialOperationRefused("session_not_current")

    # Decide on the proof against current, locked state.
    if isinstance(proof, PasskeyAssertion):
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
        # No signup capability issuer exists yet; an unverifiable capability is never accepted.
        raise CredentialOperationRefused("proof_rejected")

    live = (
        db.session.query(CredentialOperation)
        .filter(
            CredentialOperation.user_id == principal.id,
            CredentialOperation.stage.notin_(CREDENTIAL_OPERATION_TERMINAL_STAGES),
        )
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

    A wrong code returns ``False`` having changed nothing but the attempt counter:
    the principal's secret is byte-identical and the operation stays open, until
    ``MAX_CODE_ATTEMPTS`` wrong codes cancel it. Every other refusal raises
    ``CredentialOperationRefused`` and rolls the command back.
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
            and pyotp.TOTP(pending).verify(code.strip(), valid_window=1)
        )
    except (TypeError, ValueError):
        accepted = False
    if not accepted:
        locked.attempt_count += 1
        if locked.attempt_count >= MAX_CODE_ATTEMPTS:
            _erase_and_cancel(locked)
            locked.error_category = "code_attempts_exhausted"
        db.session.flush()
        return False

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


def cancel_operation(operation: CredentialOperation) -> bool:
    """Erase pending material and mark the operation cancelled.

    Returns ``False`` without effect when it is already terminal. The caller (a
    FEAT entry) is responsible for the actor's authority; this command only
    performs the erasure.
    """
    _require_feat("FEAT-IDEN-102", "FEAT-IDEN-106", "FEAT-IDEN-107", "FEAT-IDEN-108")
    locked = _lock_operation(operation.id)
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
            and cancel_operation(locked)
        ):
            cancelled += 1
    return {"cancelled": cancelled, "erased": erased}


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
