"""
Passwordless.dev Client Wrapper

Official SDK implementation following Bitwarden Passwordless.dev documentation.
https://github.com/bitwarden/passwordless-python
https://docs.passwordless.dev/guide/get-started.html
"""

import os
from typing import Dict, Any

from passwordless import (
    PasswordlessClient,
    PasswordlessClientBuilder,
    PasswordlessOptions,
    RegisterToken,
    RegisteredToken,
    VerifySignIn,
    VerifiedUser,
)


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


def verify_signin_token(token: str) -> VerifiedUser:
    """
    Verify a sign-in token from the frontend.

    Args:
        token: The authentication token from frontend

    Returns:
        VerifiedUser object containing user_id and metadata

    Raises:
        Exception: If verification fails
    """
    client = get_passwordless_client()

    verify_signin = VerifySignIn(token)
    return client.sign_in(verify_signin)


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
