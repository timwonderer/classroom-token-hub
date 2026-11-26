"""FEAT entries for credential-lifecycle operations (FEAT-IDEN-102/106/107/108).

Each entry is the one command path of its request: it resolves the acting
principal's own operation, then composes the Identity commands in
``app.services.credential_lifecycle`` (SPEC-IDEN-002). Routes call these; they
never touch ``credential_operations`` or ``users.credential_generation`` directly.

Only the TOTP-replacement commands (FEAT-IDEN-106) and the expiry sweep
(FEAT-IDEN-108) exist so far. Passkey enrollment, replacement and revocation
completion are separate commands.
"""
from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext, is_discardable_read_autobegin, requires_feat_context
from app.models import CredentialOperationPurpose, User
from app.services import credential_lifecycle as lifecycle


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
    # Provider verification runs with no transaction open: drop an incidental read
    # transaction first, verify, then begin the FEAT transaction and revalidate.
    if db.session().in_transaction() and is_discardable_read_autobegin(db.session):
        db.session.rollback()
    if db.session().in_transaction():
        # Intentional work (explicit transaction, savepoint, pending writes): never roll it
        # back, and never hold it open across a provider call.
        raise lifecycle.CredentialOperationRefused("transaction_open")
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
