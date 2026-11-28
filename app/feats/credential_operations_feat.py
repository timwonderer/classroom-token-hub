"""FEAT entries for credential-lifecycle operations (FEAT-IDEN-102/106/107/108).

Each entry is the one command path of its request: it resolves the acting
principal's own operation, then composes the Identity commands in
``app.services.credential_lifecycle`` (SPEC-IDEN-002). Routes call these; they
never touch ``credential_operations`` or ``users.credential_generation`` directly.

The TOTP-replacement commands (FEAT-IDEN-106) and the expiry sweep (FEAT-IDEN-108)
live here. Passkey enrollment and revocation (FEAT-IDEN-102/107) are in
``app/feats/passkey_lifecycle_feat.py``.
"""
from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext, is_discardable_read_autobegin, requires_feat_context
from app.models import CredentialOperationPurpose, User
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service


def release_read_transaction() -> None:
    """Leave no database transaction open, so a provider call can run.

    Drops an incidental read-only transaction (the request's canonical-context read).
    Intentional work (an explicit transaction, a savepoint, pending writes) is never
    rolled back and never held open across a provider call: it is refused.
    """
    if db.session().in_transaction() and is_discardable_read_autobegin(db.session):
        db.session.rollback()
    if db.session().in_transaction():
        raise lifecycle.CredentialOperationRefused("transaction_open")


def _own_operation(user_id, operation_id):
    operation = lifecycle.get_operation_for_user(operation_id, user_id)
    if operation is None:
        raise lifecycle.CredentialOperationRefused("operation_not_found")
    return operation


def open_credential_operation(*, user_id, purpose, proof, session_nonce,
                              correlation_id=None, idempotency_key=None) -> str:
    """Authorize one TOTP-proven passkey operation for ``user_id`` and return its id.

    TOTP replacement is not opened here: it takes a stored step-up challenge and is authorized by
    consuming provider step-up evidence (``issue_totp_replacement_challenge``,
    ``authorize_totp_replacement``).
    """
    try:
        purpose = CredentialOperationPurpose(purpose)
    except ValueError:
        raise lifecycle.CredentialOperationRefused("unknown_purpose") from None
    if purpose not in lifecycle.FEAT_FOR_PURPOSE:  # the retired ``passkey_replace`` opens nothing
        raise lifecycle.CredentialOperationRefused("unknown_purpose")
    feat_name = lifecycle.FEAT_FOR_PURPOSE[purpose]
    key = idempotency_key or f"{feat_name.lower()}:open:{uuid.uuid4().hex}"
    with db.session.no_autoflush:  # pending intentional work is never flushed by a read here
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        if not lifecycle.proof_kind_allowed(purpose, proof):
            raise lifecycle.CredentialOperationRefused("proof_kind_mismatch")
    release_read_transaction()
    with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=key):
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        operation = lifecycle.open_operation(
            user, purpose=purpose, proof=proof, session_nonce=session_nonce,
        )
        return operation.id


@requires_feat_context("FEAT-IDEN-106", key_per_call=True)
def hold_totp_candidate(*, user_id, operation_id, session_nonce, account_name,
                        correlation_id=None, idempotency_key=None):
    """Hold (or re-read) the pending seed; returns ``(secret, provisioning_uri)``."""
    return lifecycle.hold_totp_candidate(
        _own_operation(user_id, operation_id), session_nonce=session_nonce, account_name=account_name,
    )


@requires_feat_context("FEAT-IDEN-106", key_per_call=True)
def activate_totp_replacement(*, user_id, operation_id, code, session_nonce,
                              correlation_id=None, idempotency_key=None) -> bool:
    """Activate the held seed when ``code`` proves it; ``False`` for a wrong code."""
    return lifecycle.activate_totp(
        _own_operation(user_id, operation_id), code, session_nonce=session_nonce,
    )


@requires_feat_context("FEAT-IDEN-106", key_per_call=True)
def cancel_totp_replacement(*, user_id, operation_id, session_nonce,
                            correlation_id=None, idempotency_key=None) -> bool:
    """Cancel the principal's own operation, erasing the pending seed."""
    operation = _own_operation(user_id, operation_id)
    if not lifecycle.operation_matches_session(operation, session_nonce):
        raise lifecycle.CredentialOperationRefused("session_not_current")
    return lifecycle.cancel_operation(operation, purpose=CredentialOperationPurpose.TOTP_REPLACE)


def _require_step_up_config() -> None:
    """The provider configuration check, as a refusal. Outside any transaction; fails closed."""
    release_read_transaction()
    try:
        passkey_service.require_step_up_provider_config()
    except passkey_service.StepUpConfigUnavailable:
        raise lifecycle.CredentialOperationRefused("step_up_unavailable") from None


def issue_totp_replacement_challenge(*, user_id, session_nonce, correlation_id=None) -> str:
    """Store a single-use challenge on the principal's TOTP_REPLACE operation and return it.

    The provider configuration check runs first and outside any transaction; if it fails no
    challenge is issued. The returned value is what the browser sends back with its step-up token.
    """
    _require_step_up_config()
    with FEATContext("FEAT-IDEN-106", correlation_id=correlation_id,
                     idempotency_key=f"feat-iden-106:challenge:{uuid.uuid4().hex}"):
        return lifecycle.issue_replacement_challenge(user_id, session_nonce=session_nonce)


def authorize_totp_replacement(*, user_id, session_nonce, token, challenge, correlation_id=None) -> str:
    """Consume provider step-up evidence to authorize the principal's replacement; its operation id.

    Provider verification and the second configuration check run with no transaction open; the
    pure evaluation reads the stored window; then one local transaction, opened after the provider
    calls, takes the locks and consumes the evidence (``lifecycle.consume_step_up_evidence``).
    """
    release_read_transaction()
    evidence = passkey_service.verify_step_up_token(token)
    _require_step_up_config()
    evaluation = lifecycle.evaluate_step_up_evidence(evidence, user_id=user_id)
    release_read_transaction()
    with FEATContext("FEAT-IDEN-106", correlation_id=correlation_id,
                     idempotency_key=f"feat-iden-106:authorize:{uuid.uuid4().hex}"):
        return lifecycle.consume_step_up_evidence(
            evaluation, evidence, user_id=user_id, challenge=challenge, session_nonce=session_nonce,
        ).id


def begin_totp_replacement(*, user_id, session_nonce, token, challenge, account_name, correlation_id=None):
    """Authorize a replacement with step-up evidence, then stage the pending seed.

    Returns ``(secret, provisioning_uri, binding)``; ``binding`` names this replacement for its Cancel
    control (``abandon_totp_replacement``). The principal's current secret is untouched. If
    staging fails after the operation was authorized, the operation is cancelled so nothing is
    left holding the principal's single operation slot.
    """
    operation_id = authorize_totp_replacement(
        user_id=user_id, session_nonce=session_nonce, token=token, challenge=challenge,
        correlation_id=correlation_id,
    )
    try:
        secret, uri = hold_totp_candidate(
            user_id=user_id, operation_id=operation_id, session_nonce=session_nonce,
            account_name=account_name, correlation_id=correlation_id,
        )
        binding = lifecycle.registration_binding(_own_operation(user_id, operation_id))
        return secret, uri, binding
    except Exception:
        db.session.rollback()
        try:
            cancel_totp_replacement(user_id=user_id, operation_id=operation_id, session_nonce=session_nonce)
        except Exception:
            pass  # the original failure is the one to report; the operation still expires on its own
        raise


def _open_replacement_id(user_id, binding=None) -> str:
    operation = lifecycle.get_open_operation(user_id)
    if operation is None:
        raise lifecycle.CredentialOperationRefused("operation_not_found")
    if operation.purpose is not CredentialOperationPurpose.TOTP_REPLACE:
        raise lifecycle.CredentialOperationRefused("wrong_purpose")
    if binding is not None:
        lifecycle.check_registration_binding(operation, binding)
    operation_id = operation.id
    release_read_transaction()
    return operation_id


def confirm_totp_replacement(*, user_id, session_nonce, code) -> bool:
    """Activate the principal's own open replacement with ``code``; ``False`` for a wrong code."""
    return activate_totp_replacement(
        user_id=user_id, operation_id=_open_replacement_id(user_id), code=code, session_nonce=session_nonce,
    )


def abandon_totp_replacement(*, user_id, session_nonce, binding=None) -> bool:
    """Cancel the principal's own open replacement, keeping the existing TOTP.

    When ``binding`` is supplied it names the replacement being cancelled and must be the open
    operation's (``binding_mismatch`` otherwise, nothing cancelled), so a late Cancel from a
    superseded attempt cannot cancel a newer one; as for passkey changes, omitting it cancels
    the open replacement.
    """
    return cancel_totp_replacement(
        user_id=user_id, operation_id=_open_replacement_id(user_id, binding), session_nonce=session_nonce,
    )


@requires_feat_context("FEAT-IDEN-108", key_per_call=True)
def expire_credential_operations(*, correlation_id=None, idempotency_key=None) -> dict:
    """Scheduled sweep: cancel operations past their deadline, drop spent receipts."""
    return lifecycle.expire_stale_operations()
