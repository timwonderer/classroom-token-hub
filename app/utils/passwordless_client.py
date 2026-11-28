"""
Passwordless.dev Client Wrapper

Official SDK implementation following Bitwarden Passwordless.dev documentation.
https://github.com/bitwarden/passwordless-python
https://docs.passwordless.dev/guide/get-started.html
"""

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

from marshmallow import fields, post_load
from passwordless import (
    PasswordlessClient,
    PasswordlessClientBuilder,
    PasswordlessOptions,
    RegisterToken,
    RegisteredToken,
    VerifiedUser,
    VerifySignIn,
)
from passwordless.client import handle_response_error
from passwordless.serialization import VerifiedUserSchema, VerifySignInSchema
from requests import Request


def get_passwordless_client() -> PasswordlessClient:
    """
    Get Passwordless.dev client instance.

    Initializes the official Bitwarden Passwordless Python SDK client.

    Returns:
        PasswordlessClient: Configured client instance

    Raises:
        ValueError: If PASSWORDLESS_API_KEY is not configured
    """
    api_key = os.environ.get("PASSWORDLESS_API_KEY")

    if not api_key:
        raise ValueError(
            "PASSWORDLESS_API_KEY environment variable is required. "
            "Get your API key from https://admin.passwordless.dev"
        )

    # Optional: Custom API URL for self-hosted deployments
    api_url = os.environ.get("PASSWORDLESS_API_URL")

    if api_url:
        options = PasswordlessOptions(api_key, api_url)
    else:
        options = PasswordlessOptions(api_key)

    return PasswordlessClientBuilder(options).build()


def create_register_token(user_id: str, username: str, displayname: str) -> str:
    """
    Create a registration token for passkey registration.

    Args:
        user_id: Unique user identifier (e.g., "admin_123" or "sysadmin_456")
        username: Username for alias-based signin
        displayname: Display name shown in browser UI

    Returns:
        Registration token string to send to frontend

    Raises:
        Exception: If token generation fails
    """
    client = get_passwordless_client()

    register_token = RegisterToken(
        user_id=user_id,
        username=displayname,
        aliases=[username]
    )

    response: RegisteredToken = client.register_token(register_token)
    return response.token


def get_public_api_key() -> str:
    """
    Get the public API key for frontend use.

    Returns:
        Public API key string

    Raises:
        ValueError: If PASSWORDLESS_API_PUBLIC is not configured
    """
    api_public = os.environ.get("PASSWORDLESS_API_PUBLIC")

    if not api_public:
        raise ValueError(
            "PASSWORDLESS_API_PUBLIC environment variable is required. "
            "Get your public API key from https://admin.passwordless.dev"
        )

    return api_public


class _SigninVerifyResponseSchema(VerifiedUserSchema):
    """``/signin/verify``'s response, whose RP ID key is ``rpId``.

    passwordless==2.0.0 reads ``rpid`` (the key ``/credentials/list`` uses) and, with unknown
    keys excluded, silently yields ``rp_id=None`` here. Only this one field differs.
    """

    rp_id = fields.Str(data_key="rpId")

    @post_load
    def make(self, data: Any, **kwargs: Any) -> VerifiedUser:
        # A body lacking ``origin`` or ``rpId`` must reach the ceremony check as a missing value
        # (a refusal), not fail here as a construction error.
        missing = {name: None for name in VerifiedUser.__dataclass_fields__}
        return VerifiedUser(**{**missing, **data})


def parse_signin_verify_response(text: str) -> VerifiedUser:
    """The verified user in a raw ``/signin/verify`` JSON body."""
    return _SigninVerifyResponseSchema().loads(text)


def _post_signin_verify(client: PasswordlessClient, token: str) -> str:
    """POST ``token`` to ``/signin/verify`` through ``client``'s configuration; the raw response text.

    Same request, session and error handling as the SDK's ``sign_in``. Raises
    ``PasswordlessError`` for a refused token.
    """
    request = Request(
        method="POST",
        url=client.options.api_url + "/signin/verify",
        headers={"ApiSecret": client.options.api_secret, "Content-Type": "application/json; charset=UTF-8"},
        data=VerifySignInSchema().dumps(VerifySignIn(token)),
    )
    response = client.session.send(client.session.prepare_request(request), allow_redirects=True, timeout=30)
    if response.status_code >= 400:
        handle_response_error(response)
    return response.text


def verify_signin_token(client: PasswordlessClient, token: str) -> VerifiedUser:
    """POST ``token`` to ``/signin/verify`` and parse the verified user (``rpId`` read correctly).

    Raises ``PasswordlessError`` for a refused token.
    """
    return parse_signin_verify_response(_post_signin_verify(client, token))


def verify_step_up_token(client: PasswordlessClient, token: str) -> "StepUpEvidence":
    """POST ``token`` to ``/signin/verify`` and parse it as step-up evidence, strictly.

    Raises ``PasswordlessError`` for a refused token and ``StepUpEvidenceMalformed`` for a
    response that is not well formed evidence (SPEC-IDEN-002 §V, TOTP replacement step-up).
    """
    return parse_step_up_evidence(_post_signin_verify(client, token))


# ---------------------------------------------------------------------------
# Step-up evidence (raw JSON; the SDK's ``VerifiedUser`` drops ``purpose`` and the token fields)
# ---------------------------------------------------------------------------

class StepUpEvidenceMalformed(ValueError):
    """The ``/signin/verify`` body is not well formed step-up evidence. Carries no response content."""


@dataclass(frozen=True)
class StepUpEvidence:
    """The provider-authenticated fields a TOTP replacement consumes, read from the raw JSON body.

    Every field is required and typed; none is inferred from stored metadata. ``timestamp`` and
    ``expires_at`` are timezone-aware instants. This is provider evidence only: CTH's own
    authorization decision is made by ``credential_lifecycle.evaluate_step_up_evidence``.
    """

    success: bool
    purpose: str
    type: str
    user_id: str
    credential_id: str
    origin: str
    rp_id: str
    timestamp: datetime
    expires_at: datetime
    token_id: str


_PROVIDER_INSTANT = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$"
)


def _parse_provider_instant(value: Any) -> datetime:
    """An ISO-8601 instant with an explicit ``Z`` or offset, as an aware datetime; else ``StepUpEvidenceMalformed``.

    The provider writes a variable number of fractional digits (``45.30Z`` and seven-digit
    forms both occur); the fraction is carried to microseconds and anything finer is dropped.
    """
    if not isinstance(value, str):
        raise StepUpEvidenceMalformed("instant")
    match = _PROVIDER_INSTANT.match(value)
    if match is None:
        raise StepUpEvidenceMalformed("instant")
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    micro = ((fraction or "") + "000000")[:6]
    zone = "+00:00" if zone == "Z" else zone
    try:
        return datetime.fromisoformat(f"{year}-{month}-{day}T{hour}:{minute}:{second}.{micro}{zone}")
    except ValueError:
        raise StepUpEvidenceMalformed("instant") from None


def _required_text(body: dict, key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise StepUpEvidenceMalformed(key)
    return value


def parse_step_up_evidence(text: str) -> StepUpEvidence:
    """The step-up evidence in a raw ``/signin/verify`` JSON body; fail closed on any defect.

    A missing, null, mistyped or unparseable ``success``, ``purpose``, ``type``, ``userId``,
    ``credentialId``, ``origin``, ``rpId``, ``timestamp``, ``expiresAt`` or ``tokenId`` raises
    ``StepUpEvidenceMalformed`` (a body that is not a JSON object does too). The exception names
    only the field's key, never a value.
    """
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        raise StepUpEvidenceMalformed("json") from None
    if not isinstance(body, dict):
        raise StepUpEvidenceMalformed("json")
    success = body.get("success")
    if not isinstance(success, bool):
        raise StepUpEvidenceMalformed("success")
    token_id = _required_text(body, "tokenId")
    try:
        token_id = str(uuid.UUID(token_id))
    except ValueError:
        raise StepUpEvidenceMalformed("tokenId") from None
    return StepUpEvidence(
        success=success,
        purpose=_required_text(body, "purpose"),
        type=_required_text(body, "type"),
        user_id=_required_text(body, "userId"),
        credential_id=_required_text(body, "credentialId"),
        origin=_required_text(body, "origin"),
        rp_id=_required_text(body, "rpId"),
        timestamp=_parse_provider_instant(body.get("timestamp")),
        expires_at=_parse_provider_instant(body.get("expiresAt")),
        token_id=token_id,
    )


# ---------------------------------------------------------------------------
# Provider authentication-configuration check
# ---------------------------------------------------------------------------

class AuthConfigUnusable(Exception):
    """The provider's authentication configurations could not be read or are not as required.

    ``category`` is a fixed, coarse label (never a response value or an identifier).
    """

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def _fetch_auth_configs_text(client: PasswordlessClient) -> str:
    request = Request(
        method="GET",
        url=client.options.api_url + "/auth-configs/list",
        headers={"ApiSecret": client.options.api_secret},
    )
    response = client.session.send(client.session.prepare_request(request), allow_redirects=True, timeout=30)
    if response.status_code >= 400:
        raise AuthConfigUnusable("provider_refused")
    return response.text


def require_auth_config(client: PasswordlessClient, *, purpose: str, max_time_to_live: int) -> None:
    """Fail closed unless exactly one ``purpose`` config exists with UV required and a bounded lifetime.

    Reads ``GET /auth-configs/list`` with the secret key; nothing is cached. The response is a list
    of configurations, bare or under ``configurations``. A transport failure, an unparseable or
    unexpected reply, a malformed entry, no matching entry, more than one, a
    ``userVerificationRequirement`` other than ``required`` or a ``timeToLive`` that is not a
    positive integer of at most ``max_time_to_live`` seconds raises ``AuthConfigUnusable``.
    """
    try:
        text = _fetch_auth_configs_text(client)
    except AuthConfigUnusable:
        raise
    except Exception:
        raise AuthConfigUnusable("unreachable") from None
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        raise AuthConfigUnusable("malformed") from None
    entries = body.get("configurations") if isinstance(body, dict) else body
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise AuthConfigUnusable("malformed")
    if not all(isinstance(entry.get("purpose"), str) for entry in entries):
        raise AuthConfigUnusable("malformed")
    matching = [entry for entry in entries if entry["purpose"] == purpose]
    if not matching:
        raise AuthConfigUnusable("missing")
    if len(matching) > 1:
        raise AuthConfigUnusable("duplicate")
    entry = matching[0]
    if entry.get("userVerificationRequirement") != "required":
        raise AuthConfigUnusable("user_verification")
    ttl = entry.get("timeToLive")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 0 < ttl <= max_time_to_live:
        raise AuthConfigUnusable("time_to_live")
