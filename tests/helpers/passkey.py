"""An in-memory stand-in for passwordless.dev.

Tests never reach the real tenant. The fake models only what the application
relies on, taken from passwordless.dev's server source: ``/signin/verify``
returns the token's ``userId``, ``credentialId``, ``type`` and ``success``; a
registration completes with a ``passkey_register`` token and a sign-in with a
``passkey_signin`` token; ``/users/delete`` removes a user's credentials and
aliases and succeeds for an unknown user; an alias bound to another user id
is a 409 ``alias_conflict``.

Credential ids are spelled as the real tenant spells them (confirmed on staging, 2026-11-27):
``/signin/verify`` returns ``credentialId`` in standard base64 with padding, while
``/credentials/list`` returns the same credential in unpadded base64url and
``/credentials/delete`` matches only that spelling (anything else is a 404). ``credentials``
holds the ``/signin/verify`` spelling; ``get_credentials`` and ``delete_credential`` apply the
provider's own spelling.
"""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from passwordless import PasswordlessError
from passwordless.errors import PasswordlessProblemDetails

from app.services import passkey_service
from app.utils.user_ids import passkey_external_id
from tests.helpers import temporal


def _problem(status: int, error_code: str) -> PasswordlessError:
    return PasswordlessError(PasswordlessProblemDetails(
        type=f"https://docs.passwordless.dev/guide/errors.html#{error_code}",
        title=error_code,
        status=status,
        error_code=error_code,
    ))


#: The deployment origin the suite configures (tests/conftest.py) and the fake's ceremonies report.
EXPECTED_ORIGIN = "https://cth.test"
EXPECTED_RP_ID = "cth.test"


#: Marks a body key a test wants absent from the fake's ``/signin/verify`` response.
MISSING = object()

#: ``GET /auth-configs/list`` verbatim as the staging tenant returned it on 2026-11-28 (no secrets):
#: the provider presets (user verification preferred) plus ``totp-replace`` configured as the
#: deployment requires. ``timeToLive`` is whole seconds.
VALID_AUTH_CONFIGS = {"configurations": [
    {"purpose": "sign-in", "userVerificationRequirement": "preferred", "timeToLive": 120, "hints": "",
     "createdBy": "System", "createdOn": None, "editedBy": None, "editedOn": None,
     "lastUsedOn": "2026-11-27T23:29:58.2245149+00:00"},
    {"purpose": "totp-replace", "userVerificationRequirement": "required", "timeToLive": 120, "hints": "",
     "createdBy": "staging-rehearsal-script", "createdOn": "2026-11-27T22:50:49.7992152+00:00",
     "editedBy": None, "editedOn": None, "lastUsedOn": "2026-11-27T23:29:49.9256664+00:00"},
    {"purpose": "step-up", "userVerificationRequirement": "preferred", "timeToLive": 120, "hints": "",
     "createdBy": "System", "createdOn": None, "editedBy": None, "editedOn": None, "lastUsedOn": None},
]}


def instant_text(instant, *, offset_ms: int = 0) -> str:
    """The provider's spelling of ``instant`` moved by ``offset_ms`` (a whole-millisecond offset).

    ``instant`` must be a whole second (tests pin round instants), so a sub-second offset is exact.
    """
    assert instant.microsecond == 0, "pin a whole-second instant to express millisecond offsets"
    whole, remainder = divmod(offset_ms, 1000)
    moved = temporal.shifted(instant, seconds=whole)
    return moved.strftime("%Y-%m-%dT%H:%M:%S") + f".{remainder:03d}Z"


def provider_credential_id(credential_id: str) -> str:
    """The spelling ``/credentials/list`` reports and ``/credentials/delete`` matches: base64url, no padding."""
    return credential_id.replace("+", "-").replace("/", "_").rstrip("=")


def new_standard_base64_credential_id(length: int = 16) -> str:
    """A credential id as ``/signin/verify`` returns it: standard base64, padded, ``+``/``/`` possible."""
    return base64.b64encode(secrets.token_bytes(length)).decode()


@dataclass
class FakePasswordless:
    credentials: dict = field(default_factory=dict)  # credential_id -> external user id
    aliases: dict = field(default_factory=dict)      # alias -> external user id
    tokens: dict = field(default_factory=dict)       # token -> verified payload
    calls: list = field(default_factory=list)
    fail_deletes: bool = False
    lose_next_delete_response: bool = False  # the provider deletes, then the reply is lost
    strict_missing_deletes: bool = False  # deleting an absent credential is a 404, as the provider may answer
    generic_404_deletes: bool = False  # deletes answer a bare proxy-style 404 (no problem code), whatever is held
    fail_inventory: bool = False  # the credential listing is unavailable
    origin: str | None = EXPECTED_ORIGIN  # what the browser reported for the ceremony (the real SDK's ``origin``)
    rp_id: str | None = EXPECTED_RP_ID    # and ``rp_id``
    pending_nickname: str | None = None  # what the browser would register the next credential under
    reusable_tokens: set = field(default_factory=set)  # step-up tokens: the provider does not consume them
    auth_configs: object = field(default_factory=lambda: json.loads(json.dumps(VALID_AUTH_CONFIGS)))
    auth_configs_raw: str | None = None  # a body served verbatim instead of ``auth_configs``
    fail_auth_configs: bool = False  # the configuration listing is unreachable

    # ---- what tests use to simulate the browser ceremony ----

    def complete_registration(self, user_id, *, external_id=None, nickname=None) -> str:
        """A registration the browser finished: a new credential and its token.

        The credential's nickname is what the browser passed to ``p.register``: the binding
        of the latest start (``pending_nickname``) unless a test says otherwise.
        """
        external_id = external_id or passkey_external_id(user_id)
        credential_id = new_standard_base64_credential_id()
        self.credentials[credential_id] = external_id
        return self._token(
            external_id, credential_id, "passkey_register",
            nickname=self.pending_nickname if nickname is None else nickname,
        )

    def sign_in_token(self, credential_id, *, type_="passkey_signin", success=True) -> str:
        return self._token(self.credentials[credential_id], credential_id, type_, success)

    def token_for(self, external_id, credential_id, *, type_="passkey_signin") -> str:
        return self._token(external_id, credential_id, type_)

    def _token(self, external_id, credential_id, type_, success=True, nickname=None, purpose="sign-in",
               timestamp=None, expires_at=None, token_id=None, overrides=None) -> str:
        token = f"verify_{secrets.token_hex(8)}"
        issued = temporal.now()
        # The JSON body /signin/verify returns, with its real key spellings (``rpId``, not ``rpid``).
        body = {
            "success": success, "userId": external_id, "credentialId": credential_id, "type": type_,
            "nickname": nickname, "origin": self.origin, "rpId": self.rp_id,
            "timestamp": timestamp or issued.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "expiresAt": expires_at or temporal.shifted(issued, seconds=60).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "tokenId": token_id or str(uuid.uuid4()), "device": "Chrome", "country": "US",
            "purpose": purpose,
        }
        body = {k: v for k, v in body.items() if v is not None or k == "nickname"}
        body.update(overrides or {})  # an override may set an explicit null or remove a key (MISSING)
        self.tokens[token] = {k: v for k, v in body.items() if v is not MISSING}
        return token

    def step_up_token(self, credential_id, *, purpose="totp-replace", timestamp=None, expires_at=None,
                      token_id=None, overrides=None, external_id=None, **kwargs) -> str:
        """A ``totp-replace`` step-up token, as the provider returns it: not consumed by verification."""
        token = self._token(
            external_id or self.credentials[credential_id], credential_id, kwargs.pop("type_", "passkey_signin"),
            purpose=purpose, timestamp=timestamp, expires_at=expires_at, token_id=token_id,
            overrides=overrides, **kwargs,
        )
        self.reusable_tokens.add(token)
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

    # The SDK's HTTP layer: ``verify_signin_token`` POSTs through ``options`` and ``session``.
    @property
    def options(self):
        from passwordless import PasswordlessOptions
        return PasswordlessOptions("test-secret-not-real")

    @property
    def session(self):
        return self

    def prepare_request(self, request):
        return request

    def send(self, request, **kwargs):
        if request.url.endswith("/auth-configs/list"):
            assert request.method == "GET", request.method
            self.calls.append(("auth_configs", None))
            if self.fail_auth_configs:
                raise ConnectionError("provider unreachable")
            text = self.auth_configs_raw if self.auth_configs_raw is not None else json.dumps(self.auth_configs)
            return SimpleNamespace(status_code=200, text=text, headers={})
        assert request.url.endswith("/signin/verify"), request.url
        self.calls.append(("signin_verify", None))
        token = json.loads(request.data)["token"]
        # Tokens are not single use at the provider; the fake consumes only the ones it was not told to keep.
        payload = self.tokens.get(token) if token in self.reusable_tokens else self.tokens.pop(token, None)
        if payload is None:
            problem = {"type": "https://docs.passwordless.dev/guide/errors.html#invalid_token",
                       "title": "invalid_token", "status": 400, "errorCode": "invalid_token"}
            return SimpleNamespace(status_code=400, text=json.dumps(problem), headers={}, json=lambda: problem)
        return SimpleNamespace(status_code=200, text=json.dumps(payload), headers={})

    def delete_credential(self, delete_credential):
        self.calls.append(("delete_credential", delete_credential.credential_id))
        if self.fail_deletes:
            raise _problem(500, "unavailable")
        if self.generic_404_deletes:
            raise PasswordlessError(PasswordlessProblemDetails(
                type="https://docs.passwordless.dev/guide/errors.html", title="Unexpected error",
                status=404, detail="<html>Not Found</html>",
            ))
        # The provider matches the id it lists (base64url), not the one /signin/verify returned.
        held = {provider_credential_id(key): key for key in self.credentials}
        match = held.get(delete_credential.credential_id)
        if match is None:
            raise _problem(404, "credential_not_found")
        self.credentials.pop(match)
        if self.lose_next_delete_response:
            self.lose_next_delete_response = False
            raise _problem(504, "timeout")

    def get_credentials(self, user_id):
        self.calls.append(("get_credentials", user_id))
        if self.fail_inventory:
            raise _problem(500, "unavailable")
        return [
            SimpleNamespace(descriptor=SimpleNamespace(type="public-key", id=provider_credential_id(credential_id)), user_id=owner)
            for credential_id, owner in self.credentials.items() if owner == user_id
        ]

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


# ---- a teacher or sysadmin who can pass the fresh-TOTP gate ----------------

#: A 160-bit seed (SPEC-SEC-001 §V.1 item 7); the TOTP the tests below prove with.
HELD_SEED = "KRSXG5CTMVRXEZLUKN2XAZLSMRSXGZLT"


def totp_code(seed=HELD_SEED):
    """The current code for ``seed`` at the resolver's instant (never the wall clock)."""
    import pyotp
    from tests.helpers import temporal
    return pyotp.TOTP(seed).at(temporal.now())


def give_totp_seed(user_id, seed=HELD_SEED):
    from app import db
    from app.feats.base import FEATContext
    from app.models import User
    from app.utils.encryption import encrypt_totp
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:seed:{uuid.uuid4().hex}"):
        db.session.get(User, user_id).totp_secret_encrypted = encrypt_totp(seed)


def record_passkey(user_id, credential_id, fake=None, name="Key"):
    """An activated binding for ``user_id`` (and, given ``fake``, the provider's copy of it)."""
    from app import db
    from app.feats.base import FEATContext
    from app.models import PasskeyCredential
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:passkey:{uuid.uuid4().hex}"):
        db.session.add(PasskeyCredential(user_id=user_id, credential_id=credential_id, authenticator_name=name))
    if fake is not None:
        fake.credentials[credential_id] = passkey_external_id(user_id)


def start_registration(client, *, prefix="/admin", code=None, **body):
    """POST the start step with a fresh TOTP code (the current one unless ``code`` is given)."""
    payload = {"totp_code": totp_code() if code is None else code, **body}
    response = client.post(f"{prefix}/passkey/register/start", json=payload)
    if response.status_code == 200:
        # What the browser would hold for the finish step.
        client.last_registration_binding = response.get_json()["binding"]
        passkey_service._client().pending_nickname = client.last_registration_binding
    return response


def finish_registration(client, token, *, binding=None, prefix="/admin", name="Key"):
    """POST the finish step with the binding the last successful start returned, unless given."""
    if binding is None:
        binding = getattr(client, "last_registration_binding", None)
    return client.post(
        f"{prefix}/passkey/register/finish",
        json={"token": token, "binding": binding, "authenticatorName": name},
    )
