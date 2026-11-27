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
from flask import current_app

from app.extensions import db
from app.models import User
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
from app.utils.user_ids import passkey_external_id

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


class PasskeyOriginConfigError(ValueError):
    """``PASSKEY_EXPECTED_ORIGIN`` is not a bare ``http(s)://host[:port]`` origin."""


def parse_expected_origin(raw: str) -> tuple[str, str]:
    """``(origin, rp_id)`` from the configured deployment origin; raises ``PasskeyOriginConfigError``.

    The origin is ``scheme://host[:port]`` with no userinfo, path, query or fragment, returned
    canonicalized as a browser serializes it (lowercase, default port dropped). The RP ID is
    the canonical hostname, without the port.
    """
    from urllib.parse import urlsplit
    value = (raw or "").strip()
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port  # raises ValueError on a malformed port
    except ValueError as exc:
        raise PasskeyOriginConfigError("PASSKEY_EXPECTED_ORIGIN is not a valid origin") from exc
    if (
        parts.scheme not in ("http", "https") or not host or "@" in parts.netloc
        or parts.path or parts.query or parts.fragment or value.endswith(("?", "#"))
        or any(c.isspace() for c in value)
    ):
        raise PasskeyOriginConfigError(
            "PASSKEY_EXPECTED_ORIGIN must be https://host[:port] or http://host[:port] with no path, "
            "query, fragment or userinfo"
        )
    # WHATWG origin serialization, which is what a browser reports: lowercase scheme and host,
    # an explicit default port dropped, a non-default port kept, no trailing slash.
    host = host.lower()
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != {"https": 443, "http": 80}[parts.scheme]:
        authority = f"{authority}:{port}"
    return f"{parts.scheme}://{authority}", host


class PasskeyOriginNotConfigured(PasskeyError):
    public_message = "Passkeys are unavailable until this installation's origin is configured. Contact your administrator."


def require_ceremony_configuration() -> None:
    """Refuse (fail closed) while the deployment origin is not configured. No identifiers are logged."""
    config = current_app.config
    if not (config.get("PASSKEY_EXPECTED_ORIGIN") and config.get("PASSKEY_EXPECTED_RP_ID")):
        current_app.logger.error("passkey ceremony refused: PASSKEY_EXPECTED_ORIGIN is not configured")
        raise PasskeyOriginNotConfigured("PASSKEY_EXPECTED_ORIGIN is not configured")


def check_ceremony_binding(verified) -> None:
    """Refuse a verified ceremony whose origin or RP ID is not this deployment's.

    passwordless.dev records the origin and RP ID the browser supplied; it keeps no allowed
    list, so this compares what it echoes with the configured ``PASSKEY_EXPECTED_ORIGIN`` and
    its hostname (FEAT-IDEN-102 §VI). The expectation comes only from configuration, never
    from the request. The origin match is case-sensitive; the RP ID is a case-insensitive
    hostname match. A missing value, or no configured expectation, is a refusal.
    """
    require_ceremony_configuration()
    config = current_app.config
    expected_origin = config["PASSKEY_EXPECTED_ORIGIN"]
    expected_rp_id = config["PASSKEY_EXPECTED_RP_ID"]
    origin = getattr(verified, "origin", None)
    rp_id = getattr(verified, "rp_id", None)
    if (
        not isinstance(origin, str) or not isinstance(rp_id, str)
        or origin.rstrip("/") != expected_origin.rstrip("/")
        or rp_id.lower() != expected_rp_id.lower()
    ):
        raise PasskeyError("ceremony origin or RP ID does not match this deployment")


def _verify(token: str):
    from passwordless import PasswordlessError, VerifySignIn
    if not token or not isinstance(token, str):
        raise PasskeyError("missing token")
    try:
        verified = _client().sign_in(VerifySignIn(token))
    except PasswordlessError as exc:
        # An invalid, expired or already-used token is a refused credential,
        # not a server error.
        raise PasskeyError("passwordless.dev rejected the token") from exc
    # Every verification (registration, sign-in, step-up, TOTP replacement) passes here.
    check_ceremony_binding(verified)
    return verified


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


def _normalized_credential_id(value) -> str:
    """A credential id compared without base64 alphabet or padding differences."""
    return str(value).replace("+", "-").replace("/", "_").rstrip("=")


#: The comparison key reconciliation uses for credential ids (see ``credential_reconciliation``).
credential_match_key = _normalized_credential_id


class InventoryUnusable(PasskeyServiceUnavailable):
    """The provider's credential inventory could not be read or was not well formed."""


def list_credential_ids(user_id: str) -> list[str]:
    """The exact credential ids the provider lists for the principal. Provider I/O: no transaction may be open.

    Any failure, a reply that is not a list of entries each naming a non-empty id, or a
    missing principal raises ``InventoryUnusable``: an unusable inventory is never an empty
    one, and grants no deletion authority (FEAT-IDEN-108 §VI.1).
    """
    if not user_id:
        raise InventoryUnusable("no principal to list")
    try:
        listed = list(_client().get_credentials(passkey_external_id(user_id)))
        ids = [item.descriptor.id for item in listed]
    except Exception as exc:
        raise InventoryUnusable("credential inventory unavailable") from exc
    if not all(isinstance(i, str) and i for i in ids):
        raise InventoryUnusable("credential inventory malformed")
    return ids


def _credential_absent_from_inventory(credential_id: str, user_id: str | None) -> bool:
    """True only when the provider lists the principal's credentials and this one is not among them.

    Any failure to read the inventory, a malformed one (an entry with no usable id) or a
    missing principal is "not confirmed".
    """
    if not user_id:
        return False
    try:
        wanted = _normalized_credential_id(credential_id)
        return all(_normalized_credential_id(listed_id) != wanted for listed_id in list_credential_ids(user_id))
    except Exception:
        return False


def retire_remote_credential(credential_id: str, user_id: str | None = None) -> None:
    """Delete one exact credential on passwordless.dev. Provider I/O: no transaction may be open.

    Raises ``PasskeyServiceUnavailable`` when the provider did not confirm the
    deletion. A failure never licenses removing the local binding: the caller keeps
    the fixed operation pending and retries this same credential (FEAT-IDEN-102/107).
    ``user_id`` (the principal) lets a provider 404 be confirmed against the credential inventory.
    """
    if not credential_id or not isinstance(credential_id, str):
        raise PasskeyError("no credential to retire")
    from passwordless import DeleteCredential, PasswordlessError
    try:
        _client().delete_credential(DeleteCredential(credential_id=credential_id))
    except PasswordlessError as exc:
        # A 404 alone is not proof: a proxy or a wrong self-hosted path answers 404 too. It
        # counts as deletion only when the provider's own credential inventory for the
        # principal no longer lists this exact credential.
        if getattr(getattr(exc, "problem_details", None), "status", None) == 404 and (
            _credential_absent_from_inventory(credential_id, user_id)
        ):
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
