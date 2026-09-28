"""Passkey registration, sign-in and removal against passwordless.dev.

passwordless.dev holds the credentials; ``passkey_credentials`` records which
of them belong to which ``users.id`` (DOM-IDEN-003). A passwordless.dev token
proves only that *some* credential in the tenant was used. Authority comes from
matching that credential to a row here:

- Registration verifies the token on the server and records the credential id
  it names, for the signed-in principal only.
- Sign-in accepts only a ``passkey_signin`` token whose credential is recorded
  for the principal the token names.
- Removal deletes on passwordless.dev first, then here. If the remote call
  fails nothing local changes, so no local state points at a credential that
  still works remotely without our knowing.
"""

from __future__ import annotations

import logging
import os

import sqlalchemy as sa

from app.extensions import db
from app.models import User
from app.utils.canonical_temporal_resolver import utc_now
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
    from passwordless import VerifySignIn
    if not token or not isinstance(token, str):
        raise PasskeyError("missing token")
    return _client().sign_in(VerifySignIn(token))


def create_registration_token(user: User, *, alias: str, display_name: str) -> str:
    """A passwordless.dev registration token for ``user``.

    Raises ``PasskeyAliasConflict`` when passwordless.dev already binds the
    alias to another user id, which is what a registration left over from a
    deleted account looks like.
    """
    from passwordless import PasswordlessError, RegisterToken
    try:
        return _client().register_token(RegisterToken(
            user_id=passkey_external_id(user.id),
            username=display_name,
            aliases=[alias],
        )).token
    except PasswordlessError as exc:
        details = getattr(exc, "problem_details", None)
        if getattr(details, "error_code", None) == "alias_conflict":
            raise PasskeyAliasConflict("alias bound to another passwordless.dev user") from exc
        raise


def complete_registration(user: User, token: str, *, authenticator_name: str):
    """Verify a registration token and record its credential for ``user``."""
    verified = _verify(token)
    if (
        not getattr(verified, "success", False)
        or getattr(verified, "type", None) != REGISTER_TOKEN_TYPE
        or parse_passkey_external_id(getattr(verified, "user_id", None)) != str(user.id)
        or not getattr(verified, "credential_id", None)
    ):
        raise PasskeyError("registration token does not register a credential for this user")

    from app.services.admin_identity_service import create_admin_credential
    return create_admin_credential(
        user_id=user.id,
        credential_id=verified.credential_id,
        authenticator_name=(authenticator_name or "Unnamed Passkey")[:100],
    )


def verify_sign_in(token: str, *, expected_role: str, expected_user_id: str | None = None) -> User:
    """The principal a passkey sign-in token authenticates.

    The token must be a successful ``passkey_signin`` token whose credential is
    recorded for the user it names, and that user must hold ``expected_role``.
    When the sign-in began from a username, ``expected_user_id`` is that user,
    and the token must name them.
    """
    verified = _verify(token)
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

    credentials = _credentials()
    result = db.session.execute(
        sa.update(credentials)
        .where(credentials.c.user_id == user.id, credentials.c.credential_id == credential_id)
        .values(last_used=utc_now())
    )
    if not result.rowcount:
        raise PasskeyError("credential is not recorded for this principal")
    return user


def remove_passkey(user_id: str, passkey_row_id: int) -> bool:
    """Remove one recorded passkey: on passwordless.dev first, then here."""
    from app.services.admin_identity_service import delete_admin_credential, get_admin_credential
    row = get_admin_credential(passkey_row_id, user_id)
    if row is None:
        return False
    from passwordless import DeleteCredential
    try:
        _client().delete_credential(DeleteCredential(credential_id=row.credential_id))
    except Exception as exc:
        raise PasskeyServiceUnavailable("remote credential deletion failed") from exc
    return delete_admin_credential(passkey_row_id, user_id)


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
