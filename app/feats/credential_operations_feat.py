"""FEAT entries for credential-lifecycle operations (FEAT-IDEN-102/106/107/108).

Each entry is the one command path of its request: it resolves the acting
principal's own operation, then composes the Identity commands in
``app.services.credential_lifecycle`` (SPEC-IDEN-002). Routes call these; they
never touch ``credential_operations`` or ``users.credential_generation`` directly.

The TOTP-replacement commands (FEAT-IDEN-106) and the expiry sweep (FEAT-IDEN-108)
live here. Passkey enrollment, replacement and revocation (FEAT-IDEN-102/107) are in
``app/feats/passkey_lifecycle_feat.py``.
"""
from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext, is_discardable_read_autobegin, requires_feat_context
from app.models import CredentialOperationPurpose, User
from app.services import credential_lifecycle as lifecycle


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
    """Authorize one operation for ``user_id`` and return its id."""
    try:
        purpose = CredentialOperationPurpose(purpose)
    except ValueError:
        raise lifecycle.CredentialOperationRefused("unknown_purpose") from None
    feat_name = lifecycle.FEAT_FOR_PURPOSE[purpose]
    key = idempotency_key or f"{feat_name.lower()}:open:{uuid.uuid4().hex}"
    with db.session.no_autoflush:  # pending intentional work is never flushed by a read here
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        if not lifecycle.proof_kind_allowed(purpose, proof):
            raise lifecycle.CredentialOperationRefused("proof_kind_mismatch")
        if isinstance(proof, lifecycle.PasskeyAssertion):
            # The challenge is checked before any provider call.
            lifecycle.check_step_up_challenge(
                user, purpose=purpose, session_nonce=session_nonce, challenge=proof.challenge,
            )
    # Provider verification runs with no transaction open.
    release_read_transaction()
    verified = lifecycle.verify_proof(proof)
    with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=key):
        user = db.session.get(User, user_id)
        if user is None:
            raise lifecycle.CredentialOperationRefused("ineligible_principal")
        operation = lifecycle.open_operation(
            user, purpose=purpose, proof=proof, session_nonce=session_nonce, verified=verified,
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


@requires_feat_context("FEAT-IDEN-108", key_per_call=True)
def expire_credential_operations(*, correlation_id=None, idempotency_key=None) -> dict:
    """Scheduled sweep: cancel operations past their deadline, drop spent receipts."""
    return lifecycle.expire_stale_operations()
