"""
Passwordless.dev Client Wrapper

Official SDK implementation following Bitwarden Passwordless.dev documentation.
https://github.com/bitwarden/passwordless-python
https://docs.passwordless.dev/guide/get-started.html
"""

import os
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


def verify_signin_token(client: PasswordlessClient, token: str) -> VerifiedUser:
    """POST ``token`` to ``/signin/verify`` through ``client``'s configuration.

    Same request, session and error handling as the SDK's ``sign_in``; only the response is
    parsed with the correct ``rpId`` key. Raises ``PasswordlessError`` for a refused token.
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
    return parse_signin_verify_response(response.text)
