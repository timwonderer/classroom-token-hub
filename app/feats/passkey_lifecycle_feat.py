"""FEAT entries for passkey enrollment, selected replacement and revocation.

FEAT-IDEN-102 (enrollment and selected replacement) and FEAT-IDEN-107 (revocation),
one implementation for teacher and sysadmin principals (DOM-IDEN-003 §VII.A).

Each public function is the one command path of its request. It runs a sequence of
short, separate FEAT transactions over the Identity commands in
``app.services.credential_lifecycle`` and makes every provider call between them, with
no transaction open (SPEC-IDEN-002 §V "Transactions and provider I/O"). A FEAT never
nests another; a later autonomous continuation is FEAT-IDEN-108's, not a nested call.

The workflow is recoverable, not atomic with the provider: once retirement intent is
committed a provider or database failure leaves the fixed operation pending
(``RemoteRetirementPending``), to be finished by ``resume_retirement``; it never
restores the old credential and never removes the old local binding first.
"""
from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext, generate_correlation_id
from app.feats.credential_operations_feat import release_read_transaction
from app.models import CredentialOperationPurpose, CredentialOperationStage, User
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service

ENROLLMENT_FEAT = "FEAT-IDEN-102"
REVOCATION_FEAT = "FEAT-IDEN-107"


class RemoteRetirementPending(passkey_service.PasskeyServiceUnavailable):
    """Retirement intent is committed but the old credential is not yet confirmed gone."""

    public_message = (
        "The change is saved but the passkey service could not confirm it yet. "
        "Your authenticator app still signs you in. Try again to finish it."
    )


def _key(feat_name: str, step: str) -> str:
    return f"{feat_name.lower()}:{step}:{uuid.uuid4().hex}"


def _open_operation_for(user_id, *purposes):
    operation = lifecycle.get_open_operation(user_id)
    if operation is None:
        raise lifecycle.CredentialOperationRefused("operation_not_found")
    if operation.purpose not in purposes:
        raise lifecycle.CredentialOperationRefused("wrong_purpose")
    return operation


def start_registration(*, user_id, session_nonce, proof, alias, display_name,
                       replace_passkey_id=None, correlation_id=None) -> str:
    """Authorize, persist the pending registration, then issue one provider token.

    ``proof`` is a fresh ``TotpCode`` or, for a teacher's first passkey, the
    ``SignupCapability``. ``replace_passkey_id`` (a local binding id) makes this a
    selected replacement, which only a TOTP code may authorize. The pending state is
    committed before the provider is asked for a token, so a registration whose
    credential id is not yet known is protected. A failure to obtain the token cancels
    the operation: the token never reached the browser, so nothing can register.
    """
    purpose = (
        CredentialOperationPurpose.PASSKEY_ENROLL if replace_passkey_id is None
        else CredentialOperationPurpose.PASSKEY_REPLACE
    )
    if not lifecycle.proof_kind_allowed(purpose, proof):
        raise lifecycle.CredentialOperationRefused("proof_kind_mismatch")
    correlation_id = correlation_id or generate_correlation_id()
    release_read_transaction()
    with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "start")):
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        operation = lifecycle.open_operation(user, purpose=purpose, proof=proof, session_nonce=session_nonce)
        lifecycle.hold_pending_registration(
            operation, session_nonce=session_nonce, replace_passkey_id=replace_passkey_id,
        )
        operation_id, deadline = operation.id, operation.deadline_at
    expires_at = lifecycle.registration_token_expiry(deadline)
    release_read_transaction()
    try:
        return passkey_service.create_registration_token(
            user_id, alias=alias, display_name=display_name, expires_at=expires_at,
        )
    except Exception:
        _cancel(user_id, operation_id, session_nonce, correlation_id)
        raise


def finish_registration(*, user_id, session_nonce, token, authenticator_name, correlation_id=None) -> str:
    """Verify the browser's registration and complete the enrollment or replacement.

    The provider verifies the token first (no transaction open). The verified credential
    is then recorded as the pending candidate in its own transaction. Enrollment
    activates it in the next transaction. Replacement commits retirement intent, retires
    the selected old credential remotely, and only then swaps the local bindings.
    Returns the outcome, ``"activated"`` or ``"replaced"``.

    Principal reconciliation with the pending credential protected (FEAT-IDEN-108,
    FEAT-IDEN-102 §VI) is not part of this command: it would run between recording the
    candidate and activating it.
    """
    correlation_id = correlation_id or generate_correlation_id()
    operation = _open_operation_for(
        user_id, CredentialOperationPurpose.PASSKEY_ENROLL, CredentialOperationPurpose.PASSKEY_REPLACE,
    )
    if operation.stage is not CredentialOperationStage.REGISTRATION_PENDING:
        raise lifecycle.CredentialOperationRefused("operation_not_open")
    operation_id, purpose = operation.id, operation.purpose
    release_read_transaction()
    verified = passkey_service.verify_token(token)

    with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "record")):
        lifecycle.record_registered_credential(
            _own(user_id, operation_id), verified, session_nonce=session_nonce,
        )
    if purpose is CredentialOperationPurpose.PASSKEY_ENROLL:
        with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "activate")):
            lifecycle.activate_passkey(
                _own(user_id, operation_id), authenticator_name=authenticator_name, session_nonce=session_nonce,
            )
        return "activated"
    with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "intent")):
        lifecycle.commit_retirement_intent(_own(user_id, operation_id), session_nonce=session_nonce)
    _retire_and_complete(user_id, operation_id, authenticator_name, correlation_id)
    return "replaced"


def revoke_passkey(*, user_id, session_nonce, totp_code, passkey_id, correlation_id=None) -> str:
    """Revoke exactly one owned passkey after fresh TOTP, remote-first.

    One transaction authorizes the operation and commits the retirement intent (and
    refuses to revoke the only activated passkey); the provider deletion and the atomic
    local completion follow. Returns the outcome, ``"revoked"``.
    """
    correlation_id = correlation_id or generate_correlation_id()
    release_read_transaction()
    with FEATContext(REVOCATION_FEAT, correlation_id=correlation_id, idempotency_key=_key(REVOCATION_FEAT, "intent")):
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        operation = lifecycle.open_operation(
            user, purpose=CredentialOperationPurpose.PASSKEY_REVOKE,
            proof=lifecycle.TotpCode(totp_code), session_nonce=session_nonce,
        )
        lifecycle.commit_revocation_intent(operation, passkey_id=passkey_id, session_nonce=session_nonce)
        operation_id = operation.id
    _retire_and_complete(user_id, operation_id, None, correlation_id)
    return "revoked"


def resume_retirement(*, user_id, correlation_id=None) -> str:
    """Finish the principal's committed retirement: the exact recorded work, nothing new.

    Needs no fresh proof, session or deadline: the interactive authorization was
    consumed when the intent was committed (SPEC-IDEN-002 §V). It only retries the
    recorded deletion and the local completion. Returns the operation's outcome,
    ``"replaced"`` or ``"revoked"``.
    """
    correlation_id = correlation_id or generate_correlation_id()
    operation = _open_operation_for(
        user_id, CredentialOperationPurpose.PASSKEY_REPLACE, CredentialOperationPurpose.PASSKEY_REVOKE,
    )
    if operation.stage not in lifecycle.RETIREMENT_STAGES:
        raise lifecycle.CredentialOperationRefused("operation_not_open")
    outcome = "revoked" if operation.purpose is CredentialOperationPurpose.PASSKEY_REVOKE else "replaced"
    _retire_and_complete(user_id, operation.id, None, correlation_id)
    return outcome


def cancel_registration(*, user_id, session_nonce, correlation_id=None) -> bool:
    """Cancel the principal's passkey operation while it can still be cancelled.

    The old credential is untouched. Refused once retirement intent is committed.
    """
    correlation_id = correlation_id or generate_correlation_id()
    operation = lifecycle.get_open_operation(user_id)
    if operation is None:
        return False
    if operation.purpose not in lifecycle.PASSKEY_PURPOSES:
        raise lifecycle.CredentialOperationRefused("wrong_purpose")
    return _cancel(user_id, operation.id, session_nonce, correlation_id, raise_refusal=True)


def _own(user_id, operation_id):
    operation = lifecycle.get_operation_for_user(operation_id, user_id)
    if operation is None:
        raise lifecycle.CredentialOperationRefused("operation_not_found")
    return operation


def _cancel(user_id, operation_id, session_nonce, correlation_id, *, raise_refusal=False) -> bool:
    release_read_transaction()
    operation = _own(user_id, operation_id)
    feat_name = lifecycle.FEAT_FOR_PURPOSE[operation.purpose]
    try:
        with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "cancel")):
            return lifecycle.cancel_before_retirement(_own(user_id, operation_id), session_nonce=session_nonce)
    except lifecycle.CredentialOperationRefused:
        if raise_refusal:
            raise
        return False


def _retire_and_complete(user_id, operation_id, authenticator_name, correlation_id) -> None:
    """Retire the recorded old credential remotely, then complete locally.

    No transaction is open during the provider call. A provider failure records the
    attempt on the operation and raises ``RemoteRetirementPending``; nothing local
    changes. A local failure after a confirmed deletion propagates and leaves the
    operation at its retirement stage for ``resume_retirement``.
    """
    operation = _own(user_id, operation_id)
    if operation.stage not in lifecycle.RETIREMENT_STAGES:
        raise lifecycle.CredentialOperationRefused("operation_not_open")
    old_credential_id = operation.old_credential_id
    feat_name = lifecycle.FEAT_FOR_PURPOSE[operation.purpose]
    release_read_transaction()
    try:
        passkey_service.retire_remote_credential(old_credential_id)
    except passkey_service.PasskeyError as exc:
        with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "uncertain")):
            lifecycle.record_provider_uncertain(_own(user_id, operation_id))
        raise RemoteRetirementPending("remote retirement not confirmed") from exc
    with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "complete")):
        lifecycle.complete_retirement(_own(user_id, operation_id), authenticator_name=authenticator_name)
