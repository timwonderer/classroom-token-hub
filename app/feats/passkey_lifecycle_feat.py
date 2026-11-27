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

An interrupted registration (the credential verified and recorded as the candidate, the
activation or retirement intent not yet committed) is not resumed: ``finish_registration``
refuses it as ``registration_interrupted`` and the principal cancels and starts again.
FEAT-IDEN-102 §VII requires resumption only from committed retirement intent, and the
candidate holds no authority until activation, so restarting loses nothing.
"""
from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext, generate_correlation_id
from app.feats.credential_operations_feat import release_read_transaction
from app.models import CredentialOperationPurpose, CredentialOperationStage, User
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service
from app.services.credential_reconciliation import classify_inventory

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
                       replace_passkey_id=None, correlation_id=None) -> tuple[str, str]:
    """Authorize, persist the pending registration, then issue one provider token.

    ``proof`` is a fresh ``TotpCode``, the authorization for a first enrollment as for any
    other. ``replace_passkey_id`` (a local binding id) makes this a
    selected replacement, which only a TOTP code may authorize. The pending state is
    committed before the provider is asked for a token, so a registration whose
    credential id is not yet known is protected. Returns ``(token, binding)``; the binding
    ties the later finish request to this operation (``binding_mismatch`` otherwise). A failure to obtain the token cancels
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
        binding = lifecycle.registration_binding(operation)
    expires_at = lifecycle.registration_token_expiry(deadline)
    release_read_transaction()
    try:
        token = passkey_service.create_registration_token(
            user_id, alias=alias, display_name=display_name, expires_at=expires_at,
        )
        return token, binding
    except Exception:
        _cancel(user_id, operation_id, session_nonce, correlation_id)
        raise


def finish_registration(*, user_id, session_nonce, token, binding, authenticator_name,
                        correlation_id=None) -> tuple[str, bool]:
    """Verify the browser's registration and complete the enrollment or replacement.

    The provider verifies the token first (no transaction open). The verified credential
    is then recorded as the pending candidate in its own transaction. Enrollment
    activates it in the next transaction. Replacement commits retirement intent, retires
    the selected old credential remotely, and only then swaps the local bindings.
    Returns ``(outcome, replayed)`` with outcome ``"activated"`` or ``"replaced"``. A
    retry after completion (no open operation) returns the stored outcome of the operation
    the ``binding`` names, if its receipt remains, with ``replayed`` true and changes
    nothing; a binding naming no retained receipt is refused.

    An enrollment runs principal reconciliation (FEAT-IDEN-108, FEAT-IDEN-102 §VI) between
    recording the candidate and activating it, with the candidate protected. A replacement
    reconciles after its remote retirement is confirmed (``_retire_and_complete``).
    """
    correlation_id = correlation_id or generate_correlation_id()
    authenticator_name = lifecycle.normalize_authenticator_name(authenticator_name)
    purposes = (CredentialOperationPurpose.PASSKEY_ENROLL, CredentialOperationPurpose.PASSKEY_REPLACE)
    operation = lifecycle.get_open_operation(user_id)
    if operation is None:
        outcome = lifecycle.receipt_outcome_for_binding(user_id, binding, *purposes)
        if outcome is None:
            raise lifecycle.CredentialOperationRefused("operation_not_found")
        return outcome, True
    if operation.purpose not in purposes:
        raise lifecycle.CredentialOperationRefused("wrong_purpose")
    lifecycle.check_registration_binding(operation, binding)
    if operation.stage is CredentialOperationStage.CANDIDATE_VERIFIED:
        raise lifecycle.CredentialOperationRefused("registration_interrupted")
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
        _reconcile_principal(user_id, operation_id, ENROLLMENT_FEAT, correlation_id)
        with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "activate")):
            lifecycle.activate_passkey(
                _own(user_id, operation_id), authenticator_name=authenticator_name, session_nonce=session_nonce,
            )
        return "activated", False
    with FEATContext(ENROLLMENT_FEAT, correlation_id=correlation_id, idempotency_key=_key(ENROLLMENT_FEAT, "intent")):
        lifecycle.commit_retirement_intent(_own(user_id, operation_id), session_nonce=session_nonce)
    _retire_and_complete(user_id, operation_id, authenticator_name, correlation_id)
    return "replaced", False


def revoke_passkey(*, user_id, session_nonce, totp_code, passkey_id, correlation_id=None) -> tuple[str, bool]:
    """Revoke exactly one owned passkey after fresh TOTP, remote-first.

    One transaction authorizes the operation and commits the retirement intent (and
    refuses to revoke the only activated passkey); the provider deletion and the atomic
    local completion follow. Returns ``("revoked", False)``.
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
    return "revoked", False


def resume_retirement(*, user_id, binding, authenticator_name=None, correlation_id=None) -> tuple[str, bool]:
    """Finish the principal's committed retirement: the exact recorded work, nothing new.

    Needs no fresh proof, session or deadline: the interactive authorization was
    consumed when the intent was committed (SPEC-IDEN-002 §V). It only retries the
    recorded deletion and the local completion. ``authenticator_name`` is the optional label
    for a replacement's new passkey (the registration-time label is not retained). Returns
    ``(outcome, replayed)``: the operation's outcome, ``"replaced"`` or ``"revoked"``; a
    retry after completion replays the retained receipt's outcome with ``replayed`` true.
    ``binding`` names the operation being finished (the settings page carries it); it must
    be the open operation's, or, with none open, one whose receipt remains.
    """
    correlation_id = correlation_id or generate_correlation_id()
    purposes = (CredentialOperationPurpose.PASSKEY_REPLACE, CredentialOperationPurpose.PASSKEY_REVOKE)
    if lifecycle.get_open_operation(user_id) is None:
        outcome = lifecycle.receipt_outcome_for_binding(user_id, binding, *purposes)
        if outcome is None:
            raise lifecycle.CredentialOperationRefused("operation_not_found")
        return outcome, True
    operation = _open_operation_for(user_id, *purposes)
    lifecycle.check_registration_binding(operation, binding)
    if operation.stage not in lifecycle.RETIREMENT_STAGES:
        raise lifecycle.CredentialOperationRefused("operation_not_open")
    outcome = "revoked" if operation.purpose is CredentialOperationPurpose.PASSKEY_REVOKE else "replaced"
    result = _retire_and_complete(
        user_id, operation.id,
        lifecycle.normalize_authenticator_name(authenticator_name), correlation_id,
    )
    if result == lifecycle.ALREADY_COMPLETED:
        # A concurrent request committed this retirement while this one was at the provider:
        # this is a replay of its receipt (within the receipt's deadline), not a new change.
        replayed = lifecycle.receipt_outcome_for_binding(user_id, binding, *purposes)
        if replayed is None:
            raise lifecycle.CredentialOperationRefused("operation_not_found")
        return replayed, True
    return outcome, False


def cancel_registration(*, user_id, session_nonce, binding=None, correlation_id=None) -> bool:
    """Cancel the principal's passkey operation while it can still be cancelled.

    The old credential is untouched. Refused once retirement intent is committed. When
    ``binding`` is supplied it names the attempt being cancelled and must be the open
    operation's (``binding_mismatch`` otherwise, nothing cancelled), so a late cancel from
    a superseded attempt cannot cancel a newer one. Without it the open operation is cancelled.
    """
    correlation_id = correlation_id or generate_correlation_id()
    operation = lifecycle.get_open_operation(user_id)
    if operation is None:
        return False
    if operation.purpose not in lifecycle.PASSKEY_PURPOSES:
        raise lifecycle.CredentialOperationRefused("wrong_purpose")
    if binding is not None:
        lifecycle.check_registration_binding(operation, binding)
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


def _retire_and_complete(user_id, operation_id, authenticator_name, correlation_id) -> str:
    """Retire the recorded old credential remotely, then complete locally.

    No transaction is open during the provider call. A provider failure records the
    attempt on the operation and raises ``RemoteRetirementPending``; nothing local
    changes. A local failure after a confirmed deletion propagates and leaves the
    operation at its retirement stage for ``resume_retirement``. Returns the locked
    completion's result: ``COMPLETED`` for the request that committed, ``ALREADY_COMPLETED``
    when a concurrent request finished the operation first.
    """
    operation = _own(user_id, operation_id)
    if operation.stage not in lifecycle.RETIREMENT_STAGES:
        raise lifecycle.CredentialOperationRefused("operation_not_open")
    old_credential_id = operation.old_credential_id
    feat_name = lifecycle.FEAT_FOR_PURPOSE[operation.purpose]
    # A recovery or destruction that bumped the generation supersedes this operation: no
    # remote deletion may follow it (SPEC-IDEN-002 §V).
    lifecycle.require_current_generation(operation)
    release_read_transaction()
    try:
        passkey_service.retire_remote_credential(old_credential_id, user_id)
    except passkey_service.PasskeyError as exc:
        with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "uncertain")):
            lifecycle.record_provider_uncertain(_own(user_id, operation_id))
        raise RemoteRetirementPending("remote retirement not confirmed") from exc
    _reconcile_principal(user_id, operation_id, feat_name, correlation_id)
    with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "complete")):
        return lifecycle.complete_retirement(_own(user_id, operation_id), authenticator_name=authenticator_name)


def _reconcile_principal(user_id, operation_id, feat_name, correlation_id) -> None:
    """Principal-mode credential reconciliation (FEAT-IDEN-108 §VI), composed by the lifecycle FEATs.

    Compares the provider's exact inventory for this one principal with its local authority
    and retires only credentials that are provider-only. It never blocks the lifecycle step
    that invoked it: it can only withhold or exercise deletion authority, so every provider
    failure ends in an outcome and a normal return.

    * The inventory is read with no transaction open. A failed, thrown or malformed
      inventory grants no deletion authority; the unusable inventory is reported.
    * Each provider-only credential is revalidated against current local state (generation,
      stage, bindings, candidate) in a short read, then deleted exactly, with no transaction
      open. An unconfirmed delete is reported and not assumed to have succeeded.
    * An activated binding the provider does not list is reported only; the local binding is
      never deleted or recreated and the inventory is never imported.

    A superseded operation (stale generation) is refused here, before any deletion. Outcomes
    are the DOM-OPS-002 §2.5 non-identifying envelope; a clean reconciliation emits none.
    A reconciliation needs no durable reservation of its targets: the principal's single
    open operation is this one, and it can adopt no provider-only credential.
    """
    operation = _own(user_id, operation_id)
    scope = lifecycle.reconciliation_scope(operation)
    release_read_transaction()
    if scope is None:
        return
    outcomes: list[str] = []
    try:
        provider_ids = passkey_service.list_credential_ids(user_id)
    except passkey_service.PasskeyError:
        outcomes.append("reconciliation_inventory_unusable")
    else:
        classification = classify_inventory(
            provider_ids=provider_ids, active_ids=scope.active_ids, pending_id=scope.pending_id,
            retiring_id=scope.retiring_id, pending_registration_unknown=scope.pending_registration_unknown,
        )
        outcomes.extend("reconciliation_active_absent_remotely" for _ in classification.unexpectedly_absent)
        for credential_id in classification.provider_only:
            operation = _own(user_id, operation_id)
            allowed = lifecycle.reconciliation_target_is_still_provider_only(operation, credential_id)
            release_read_transaction()
            if not allowed:
                continue
            try:
                passkey_service.retire_remote_credential(credential_id, user_id)
            except passkey_service.PasskeyError:
                outcomes.append("reconciliation_delete_unconfirmed")
            else:
                outcomes.append("reconciliation_provider_only_retired")
    if outcomes:
        with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=_key(feat_name, "reconcile")):
            for outcome in outcomes:
                lifecycle.emit_reconciliation_outcome(scope, outcome=outcome)
