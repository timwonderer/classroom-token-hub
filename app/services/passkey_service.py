"""Passkey registration, sign-in and removal against passwordless.dev.

passwordless.dev holds the credentials; ``passkey_credentials`` records which
of them belong to which ``users.id`` (DOM-IDEN-003). A passwordless.dev token
proves only that *some* credential in the tenant was used. Authority comes from
matching that credential to a row here:

- Registration tokens are issued here and the browser's result is verified here;
  recording and activating the credential it names is an Identity command
  (``credential_lifecycle``), never this adapter.
- Sign-in accepts only a ``passkey_signin`` token whose credential is recorded
  for the principal the token names.
- Retirement deletes on passwordless.dev first; the local binding is removed by
  the Identity command only after the deletion is confirmed.
"""

from __future__ import annotations

import logging
import os

import sqlalchemy as sa

from app.extensions import db
from app.models import User
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
from app.utils.user_ids import parse_passkey_external_id, passkey_external_id

logger = logging.getLogger(__name__)

REGISTER_TOKEN_TYPE = "passkey_register"
SIGNIN_TOKEN_TYPE = "passkey_signin"


class PasskeyError(Exception):
    """A passkey operation was refused. ``public_message`` is safe to show."""

    public_message = "Passkey verification failed."


class PasskeyAliasConflict(PasskeyError):
    public_message = (
        "This username is still attached to an old passkey registration. "
        "Contact support to clear it, then try again."
    )


class PasskeyServiceUnavailable(PasskeyError):
    public_message = "The passkey service could not be reached. Nothing was changed; try again."


def passkey_service_configured() -> bool:
    return bool(os.environ.get("PASSWORDLESS_API_KEY"))


def _client():
    from app.utils.passwordless_client import get_passwordless_client
    return get_passwordless_client()


def _credentials() -> sa.Table:
    return db.metadata.tables["passkey_credentials"]


def _verify(token: str):
    from passwordless import PasswordlessError, VerifySignIn
    if not token or not isinstance(token, str):
        raise PasskeyError("missing token")
    try:
        return _client().sign_in(VerifySignIn(token))
    except PasswordlessError as exc:
        # An invalid, expired or already-used token is a refused credential,
        # not a server error.
        raise PasskeyError("passwordless.dev rejected the token") from exc


def create_registration_token(user_id: str, *, alias: str, display_name: str, expires_at=None) -> str:
    """A passwordless.dev registration token for the principal ``user_id``.

    ``expires_at`` caps the token's life (the caller passes the operation's registration
    deadline); the provider default is two minutes.

    Raises ``PasskeyAliasConflict`` when passwordless.dev already binds the
    alias to another user id, which is what a registration left over from a
    deleted account looks like.
    """
    from passwordless import PasswordlessError, RegisterToken
    extra = {"expires_at": expires_at} if expires_at is not None else {}
    try:
        return _client().register_token(RegisterToken(
            user_id=passkey_external_id(user_id),
            username=display_name,
            aliases=[alias],
            **extra,
        )).token
    except PasswordlessError as exc:
        details = getattr(exc, "problem_details", None)
        if getattr(details, "error_code", None) == "alias_conflict":
            raise PasskeyAliasConflict("alias bound to another passwordless.dev user") from exc
        raise


def verify_token(token: str):
    """Ask passwordless.dev to verify ``token``: provider I/O, no local state read or written."""
    return _verify(token)


def verify_sign_in(token: str, *, expected_role: str, expected_user_id: str | None = None) -> User:
    """The principal a passkey sign-in token authenticates.

    The token must be a successful ``passkey_signin`` token whose credential is
    recorded for the user it names, and that user must hold ``expected_role``.
    When the sign-in began from a username, ``expected_user_id`` is that user,
    and the token must name them.

    The ownership and role checks are the pure evaluation in
    ``credential_lifecycle.evaluate_passkey_assertion``, shared with every other
    assertion consumer. Only the ``last_used`` stamp below is this command's own write.
    """
    from app.services.credential_lifecycle import SIGN_IN_PURPOSE, evaluate_passkey_assertion
    evaluation = evaluate_passkey_assertion(
        token, expected_role=expected_role, expected_user_id=expected_user_id,
        purpose=SIGN_IN_PURPOSE,
    )
    user = evaluation.user

    credentials = _credentials()
    result = db.session.execute(
        sa.update(credentials)
        .where(credentials.c.user_id == user.id, credentials.c.credential_id == evaluation.credential_id)
        .values(last_used=canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc)
    )
    if not result.rowcount:
        raise PasskeyError("credential is not recorded for this principal")
    return user


def retire_remote_credential(credential_id: str) -> None:
    """Delete one exact credential on passwordless.dev. Provider I/O: no transaction may be open.

    Raises ``PasskeyServiceUnavailable`` when the provider did not confirm the
    deletion. A failure never licenses removing the local binding: the caller keeps
    the fixed operation pending and retries this same credential (FEAT-IDEN-102/107).
    """
    if not credential_id or not isinstance(credential_id, str):
        raise PasskeyError("no credential to retire")
    from passwordless import DeleteCredential, PasswordlessError
    try:
        _client().delete_credential(DeleteCredential(credential_id=credential_id))
    except PasswordlessError as exc:
        # The provider reports this exact credential as already absent: the deletion
        # this call exists to achieve has happened, so a retry converges instead of looping.
        if getattr(getattr(exc, "problem_details", None), "status", None) == 404:
            return
        raise PasskeyServiceUnavailable("remote credential deletion failed") from exc
    except Exception as exc:
        raise PasskeyServiceUnavailable("remote credential deletion failed") from exc


def forget_principal_remotely(user_id: str) -> None:
    """Delete the principal and all its credentials and aliases on passwordless.dev.

    Called before an account's rows are destroyed. passwordless.dev treats an
    unknown user id as already deleted, so this is safe to repeat. A deployment
    with no passkey service configured cannot have registered any, and skips it.
    """
    if not passkey_service_configured():
        return
    from passwordless import DeleteUser
    try:
        _client().delete_user(DeleteUser(user_id=passkey_external_id(user_id)))
    except Exception as exc:
        raise PasskeyServiceUnavailable("remote principal deletion failed") from exc
