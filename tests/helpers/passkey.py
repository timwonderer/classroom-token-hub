"""An in-memory stand-in for passwordless.dev.

Tests never reach the real tenant. The fake models only what the application
relies on, taken from passwordless.dev's server source: ``/signin/verify``
returns the token's ``userId``, ``credentialId``, ``type`` and ``success``; a
registration completes with a ``passkey_register`` token and a sign-in with a
``passkey_signin`` token; ``/users/delete`` removes a user's credentials and
aliases and succeeds for an unknown user; an alias bound to another user id
is a 409 ``alias_conflict``.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from passwordless import PasswordlessError
from passwordless.errors import PasswordlessProblemDetails

from app.utils.user_ids import passkey_external_id


def _problem(status: int, error_code: str) -> PasswordlessError:
    return PasswordlessError(PasswordlessProblemDetails(
        type=f"https://docs.passwordless.dev/guide/errors.html#{error_code}",
        title=error_code,
        status=status,
        error_code=error_code,
    ))


@dataclass
class FakePasswordless:
    credentials: dict = field(default_factory=dict)  # credential_id -> external user id
    aliases: dict = field(default_factory=dict)      # alias -> external user id
    tokens: dict = field(default_factory=dict)       # token -> verified payload
    calls: list = field(default_factory=list)
    fail_deletes: bool = False

    # ---- what tests use to simulate the browser ceremony ----

    def complete_registration(self, user_id, *, external_id=None) -> str:
        """A registration the browser finished: a new credential and its token."""
        external_id = external_id or passkey_external_id(user_id)
        credential_id = f"cred-{secrets.token_hex(4)}"
        self.credentials[credential_id] = external_id
        return self._token(external_id, credential_id, "passkey_register")

    def sign_in_token(self, credential_id, *, type_="passkey_signin", success=True) -> str:
        return self._token(self.credentials[credential_id], credential_id, type_, success)

    def token_for(self, external_id, credential_id, *, type_="passkey_signin") -> str:
        return self._token(external_id, credential_id, type_)

    def _token(self, external_id, credential_id, type_, success=True) -> str:
        token = f"verify_{secrets.token_hex(8)}"
        self.tokens[token] = SimpleNamespace(
            success=success, user_id=external_id, credential_id=credential_id, type=type_,
        )
        return token

    # ---- the PasswordlessClient surface ----

    def register_token(self, register_token):
        self.calls.append(("register_token", register_token.user_id))
        for alias in register_token.aliases or []:
            owner = self.aliases.get(alias)
            if owner is not None and owner != register_token.user_id:
                raise _problem(409, "alias_conflict")
            self.aliases[alias] = register_token.user_id
        return SimpleNamespace(token=f"register_{secrets.token_hex(8)}")

    def sign_in(self, verify_sign_in):
        payload = self.tokens.pop(verify_sign_in.token, None)  # tokens are single use
        if payload is None:
            raise _problem(400, "invalid_token")
        return payload

    def delete_credential(self, delete_credential):
        self.calls.append(("delete_credential", delete_credential.credential_id))
        if self.fail_deletes:
            raise _problem(500, "unavailable")
        self.credentials.pop(delete_credential.credential_id, None)

    def delete_user(self, delete_user):
        self.calls.append(("delete_user", delete_user.user_id))
        if self.fail_deletes:
            raise _problem(500, "unavailable")
        for key in [k for k, v in self.credentials.items() if v == delete_user.user_id]:
            del self.credentials[key]
        for key in [k for k, v in self.aliases.items() if v == delete_user.user_id]:
            del self.aliases[key]


@pytest.fixture
def fake_passwordless(monkeypatch):
    fake = FakePasswordless()
    monkeypatch.setenv("PASSWORDLESS_API_KEY", "test-secret-not-real")
    monkeypatch.setenv("PASSWORDLESS_API_PUBLIC", "test-public-not-real")
    monkeypatch.setattr("app.services.passkey_service._client", lambda: fake)
    monkeypatch.setattr(
        "app.utils.passwordless_client.get_passwordless_client",
        lambda: pytest.fail("a test reached the real passwordless.dev client"),
    )
    return fake
