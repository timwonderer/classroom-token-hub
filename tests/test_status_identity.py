"""Operator identity: IAP signed-assertion verification and the trusted-header fallback."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from google.auth import jwt
from google.auth.crypt import es256

from status_service import identity


AUDIENCE = "/projects/123456789012/locations/us-west2/services/cth-status-operator"
OPERATOR = "operator@example.com"
KEY_ID = "test-iap-key"
IAP_KEY = ec.generate_private_key(ec.SECP256R1())


def _public_pem(key):
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": identity.IAP_ISSUER, "aud": AUDIENCE, "email": OPERATOR,
        "sub": "accounts.google.com:1234567890", "iat": now, "exp": now + 600,
    }
    claims.update(overrides)
    return claims


def _sign(claims, key=IAP_KEY, key_id=KEY_ID):
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return jwt.encode(es256.ES256Signer.from_string(private_pem, key_id), claims).decode()


def _b64(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.data = body
        self.headers = {}


class _IapKeyEndpoint:
    """Stands in for the HTTP transport; serves IAP's ``{kid: PEM}`` key set."""

    def __init__(self, keys, status=200):
        self.body = json.dumps(keys).encode()
        self.status = status
        self.urls = []

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        self.urls.append(url)
        return _Response(self.status, self.body)


@pytest.fixture
def operator_env(monkeypatch):
    monkeypatch.setenv("IAP_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("STATUS_OPERATOR_ALLOWLIST", f"{OPERATOR}, second@example.com")
    monkeypatch.delenv("IAP_TRUSTED_EMAIL_HEADER", raising=False)


@pytest.fixture
def iap_keys(monkeypatch):
    endpoint = _IapKeyEndpoint({KEY_ID: _public_pem(IAP_KEY)})
    monkeypatch.setattr(identity.requests, "Request", lambda *args, **kwargs: endpoint)
    return endpoint


def _assert_rejected(assertion):
    # A verifier that rejects everything passes every negative case by itself,
    # so each one first proves an untampered assertion is accepted in the same
    # setup. Only the tampered field then separates acceptance from rejection.
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert identity.authenticated_operator_email(assertion) is None


def test_status_identity_valid_assertion_for_allowlisted_operator_authenticates(operator_env, iap_keys):
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert iap_keys.urls == [identity.IAP_CERTS_URL]


def test_status_identity_wrong_audience_is_rejected(operator_env, iap_keys):
    _assert_rejected(_sign(_claims(aud="/projects/999/locations/us-west2/services/other-service")))


def test_status_identity_wrong_issuer_is_rejected(operator_env, iap_keys):
    _assert_rejected(_sign(_claims(iss="https://accounts.google.com")))


def test_status_identity_operator_not_on_allowlist_is_rejected(operator_env, iap_keys):
    _assert_rejected(_sign(_claims(email="intruder@example.com")))


def test_status_identity_expired_assertion_is_rejected(operator_env, iap_keys):
    now = int(time.time())
    _assert_rejected(_sign(_claims(iat=now - 1200, exp=now - 600)))


@pytest.mark.parametrize(
    "assertion",
    ["not-a-jwt", "a.b.c", "a.b.c.d", f"{_b64([])}.{_b64({})}.c2ln"],
    ids=["no-segments", "undecodable-segments", "four-segments", "non-object-header"],
)
def test_status_identity_malformed_assertion_is_rejected(operator_env, iap_keys, assertion):
    _assert_rejected(assertion)


def test_status_identity_assertion_signed_by_another_key_is_rejected(operator_env, iap_keys):
    forger = ec.generate_private_key(ec.SECP256R1())
    _assert_rejected(_sign(_claims(), key=forger))


def test_status_identity_assertion_naming_another_algorithm_is_rejected(operator_env, iap_keys):
    # A header claiming RS256 would otherwise reach an RSA verifier holding an
    # EC key, which raises TypeError instead of rejecting.
    _, payload, signature = _sign(_claims()).split(".")
    header = _b64({"alg": "RS256", "typ": "JWT", "kid": KEY_ID})
    _assert_rejected(f"{header}.{payload}.{signature}")


def test_status_identity_unreachable_key_endpoint_is_rejected(operator_env, monkeypatch):
    endpoint = _IapKeyEndpoint({}, status=503)
    monkeypatch.setattr(identity.requests, "Request", lambda *args, **kwargs: endpoint)
    assert identity.authenticated_operator_email(_sign(_claims())) is None
    assert endpoint.urls == [identity.IAP_CERTS_URL]


def test_status_identity_programming_errors_are_not_read_as_rejection(operator_env, iap_keys, monkeypatch):
    def broken_verify(*args, **kwargs):
        raise TypeError("defect in the verification call")

    monkeypatch.setattr(identity.id_token, "verify_token", broken_verify)
    with pytest.raises(TypeError):
        identity.authenticated_operator_email(_sign(_claims()))


def test_status_identity_trusted_header_authenticates_when_enabled(operator_env, monkeypatch):
    monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", "true")
    assert identity.authenticated_operator_email(None, f"accounts.google.com:{OPERATOR}") == OPERATOR


def test_status_identity_trusted_header_still_enforces_allowlist(operator_env, monkeypatch):
    monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", "true")
    assert identity.authenticated_operator_email(None, "accounts.google.com:intruder@example.com") is None


@pytest.mark.parametrize("setting", [None, "false"], ids=["unset", "false"])
def test_status_identity_trusted_header_is_ignored_when_disabled(operator_env, monkeypatch, setting):
    if setting is not None:
        monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", setting)
    assert identity.authenticated_operator_email(None, f"accounts.google.com:{OPERATOR}") is None
