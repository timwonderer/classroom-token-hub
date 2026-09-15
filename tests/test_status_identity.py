"""Operator identity: IAP signed-assertion verification, its key cache, the trusted-header fallback, and its log line."""

import ast
import base64
import json
import logging
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# google-auth belongs to the separately deployed status service
# (status_service/requirements.txt), not to the application. Installing it
# beside requirements.txt downgrades the protobuf the application's
# OpenTelemetry exporter runs on, so environments built from requirements.txt
# alone (Full Test Suite, Schema Change Gate) skip this module rather than fail
# collection for every other test. deploy-status.yml installs both files and
# runs this module by name.
pytest.importorskip("google.auth", reason="status_service/requirements.txt is not installed")

from google.auth import jwt  # noqa: E402
from google.auth.crypt import es256  # noqa: E402

from status_service import identity, log_setup  # noqa: E402


AUDIENCE = "/projects/123456789012/locations/us-west2/services/cth-status-operator"
OTHER_AUDIENCE = "/projects/999/locations/us-west2/services/other-service"
OPERATOR = "operator@example.com"
KEY_ID = "test-iap-key"
IAP_KEY = ec.generate_private_key(ec.SECP256R1())
ROTATED_KEY_ID = "rotated-iap-key"
ROTATED_KEY = ec.generate_private_key(ec.SECP256R1())
# What IAP's key endpoint actually sends.
MAX_AGE = 3000


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


def _with_header(assertion, header):
    _, payload, signature = assertion.split(".")
    return f"{_b64(header)}.{payload}.{signature}"


class _Response:
    def __init__(self, status, body, headers):
        self.status = status
        self.data = body
        self.headers = headers


class _IapKeyEndpoint:
    """Stands in for the HTTP transport; serves IAP's ``{kid: PEM}`` key set."""

    def __init__(self, keys, status=200):
        self.keys = dict(keys)
        self.status = status
        self.headers = {"Cache-Control": f"public, max-age={MAX_AGE}"}
        self.urls = []

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        self.urls.append(url)
        return _Response(self.status, json.dumps(self.keys).encode(), self.headers)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def key_clock(monkeypatch):
    # The key cache is module state, so every test starts from an empty one.
    clock = _Clock()
    monkeypatch.setattr(identity, "_IAP_KEYS", identity._IapKeyCache(clock=clock))
    return clock


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


@pytest.fixture
def auth_log(caplog):
    caplog.set_level(logging.INFO, logger="status_service")
    return lambda: [(record.levelname, record.getMessage()) for record in caplog.records if record.name == identity.__name__]


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
    _assert_rejected(_sign(_claims(aud=OTHER_AUDIENCE)))


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
    _assert_rejected(_with_header(_sign(_claims()), {"alg": "RS256", "typ": "JWT", "kid": KEY_ID}))


@pytest.mark.parametrize("key_id", [[KEY_ID], {"kid": KEY_ID}], ids=["list", "object"])
def test_status_identity_non_string_key_id_is_rejected(operator_env, iap_keys, key_id):
    # google-auth looks the kid up in the key set, where an unhashable one
    # raises TypeError instead of rejecting.
    _assert_rejected(_with_header(_sign(_claims()), {"alg": "ES256", "typ": "JWT", "kid": key_id}))


def test_status_identity_unreachable_key_endpoint_is_rejected(operator_env, monkeypatch):
    endpoint = _IapKeyEndpoint({}, status=503)
    monkeypatch.setattr(identity.requests, "Request", lambda *args, **kwargs: endpoint)
    assert identity.authenticated_operator_email(_sign(_claims())) is None
    assert endpoint.urls == [identity.IAP_CERTS_URL]


def test_status_identity_programming_errors_are_not_read_as_rejection(operator_env, iap_keys, monkeypatch):
    def broken_decode(*args, **kwargs):
        raise TypeError("defect in the verification call")

    monkeypatch.setattr(identity.jwt, "decode", broken_decode)
    with pytest.raises(TypeError):
        identity.authenticated_operator_email(_sign(_claims()))


def test_status_identity_key_set_is_reused_while_fresh(operator_env, iap_keys, key_clock):
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    key_clock.advance(MAX_AGE - 1)
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert iap_keys.urls == [identity.IAP_CERTS_URL]


def test_status_identity_key_set_is_refetched_once_stale(operator_env, iap_keys, key_clock):
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    key_clock.advance(MAX_AGE)
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert len(iap_keys.urls) == 2


def test_status_identity_age_header_counts_against_freshness(operator_env, iap_keys, key_clock):
    # A CDN-served response that is already 1240s old has 1760s left, not 3000.
    iap_keys.headers = {"Cache-Control": f"public, max-age={MAX_AGE}", "Age": "1240"}
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    key_clock.advance(MAX_AGE - 1240)
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert len(iap_keys.urls) == 2


@pytest.mark.parametrize(
    "cache_control",
    ["no-store", f"no-cache, max-age={MAX_AGE}", "public"],
    ids=["no-store", "no-cache", "no-max-age"],
)
def test_status_identity_uncacheable_key_set_is_fetched_every_time(operator_env, iap_keys, cache_control):
    iap_keys.headers = {"Cache-Control": cache_control}
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert len(iap_keys.urls) == 2


def test_status_identity_unknown_key_id_forces_refetch(operator_env, iap_keys):
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    iap_keys.keys[ROTATED_KEY_ID] = _public_pem(ROTATED_KEY)
    # The cached set is still fresh, so only the unknown key id can explain a
    # second fetch, and without it the rotated key would be rejected.
    rotated = _sign(_claims(), key=ROTATED_KEY, key_id=ROTATED_KEY_ID)
    assert identity.authenticated_operator_email(rotated) == OPERATOR
    assert len(iap_keys.urls) == 2


def test_status_identity_key_id_still_unknown_after_refetch_is_rejected(operator_env, iap_keys):
    _assert_rejected(_sign(_claims(), key=ROTATED_KEY, key_id=ROTATED_KEY_ID))
    # One forced fetch for the unknown key id, not a retry loop.
    assert len(iap_keys.urls) == 2


def test_status_identity_failed_refresh_fails_closed_and_is_retried(operator_env, iap_keys, key_clock):
    # Starts from a cached set, so a failed refresh could otherwise be papered
    # over by serving the stale keys or by treating the failure as fresh.
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    key_clock.advance(MAX_AGE)
    iap_keys.status = 503
    assert identity.authenticated_operator_email(_sign(_claims())) is None
    iap_keys.status = 200
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert len(iap_keys.urls) == 3


def test_status_identity_key_fetch_is_bounded_by_a_short_timeout(operator_env, monkeypatch):
    timeouts = []
    endpoint = _IapKeyEndpoint({KEY_ID: _public_pem(IAP_KEY)})

    def recording_endpoint(url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        timeouts.append(timeout)
        return endpoint(url, method=method)

    monkeypatch.setattr(identity.requests, "Request", lambda *args, **kwargs: recording_endpoint)
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert timeouts == [identity.KEY_FETCH_TIMEOUT_SECONDS]


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


def test_status_identity_logs_authentication_by_signed_assertion(operator_env, iap_keys, auth_log):
    assert identity.authenticated_operator_email(_sign(_claims())) == OPERATOR
    assert auth_log() == [("INFO", "status operator authenticated via=iap_assertion")]


def test_status_identity_logs_why_the_assertion_failed_when_the_header_admits(operator_env, iap_keys, auth_log, monkeypatch):
    # The case the log line exists for: a wrong IAP_AUDIENCE is otherwise
    # invisible, because the header fallback still lets the operator in.
    monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", "true")
    assertion = _sign(_claims(aud=OTHER_AUDIENCE))
    assert identity.authenticated_operator_email(assertion, f"accounts.google.com:{OPERATOR}") == OPERATOR
    assert auth_log() == [("INFO", "status operator authenticated via=trusted_header assertion=wrong_audience")]


def _expired():
    now = int(time.time())
    return _sign(_claims(iat=now - 1200, exp=now - 600))


def _audience_not_configured(monkeypatch):
    monkeypatch.delenv("IAP_AUDIENCE")
    return _sign(_claims())


def _key_endpoint_down(iap_keys):
    iap_keys.status = 503
    return _sign(_claims())


REFUSALS = [
    ("absent", lambda keys, env: None),
    ("audience_not_configured", lambda keys, env: _audience_not_configured(env)),
    ("wrong_audience", lambda keys, env: _sign(_claims(aud=OTHER_AUDIENCE))),
    ("wrong_issuer", lambda keys, env: _sign(_claims(iss="https://accounts.google.com"))),
    ("not_allowlisted", lambda keys, env: _sign(_claims(email="intruder@example.com"))),
    ("invalid_token", lambda keys, env: _sign(_claims(), key=ec.generate_private_key(ec.SECP256R1()))),
    ("invalid_token", lambda keys, env: _expired()),
    ("invalid_token", lambda keys, env: "a.b.c"),
    ("wrong_algorithm", lambda keys, env: _with_header(_sign(_claims()), {"alg": "RS256", "typ": "JWT", "kid": KEY_ID})),
    ("invalid_key_id", lambda keys, env: _with_header(_sign(_claims()), {"alg": "ES256", "typ": "JWT", "kid": [KEY_ID]})),
    ("key_fetch_failed", lambda keys, env: _key_endpoint_down(keys)),
]


@pytest.mark.parametrize(
    "reason, build",
    REFUSALS,
    ids=["absent", "audience-not-configured", "wrong-audience", "wrong-issuer", "not-allowlisted",
         "forged", "expired", "malformed", "wrong-algorithm", "invalid-key-id", "key-fetch-failed"],
)
def test_status_identity_logs_why_a_request_was_refused(operator_env, iap_keys, auth_log, monkeypatch, reason, build):
    assert identity.authenticated_operator_email(build(iap_keys, monkeypatch)) is None
    assert auth_log() == [("WARNING", f"status operator refused assertion={reason} header=disabled")]


@pytest.mark.parametrize(
    "header, state",
    [(None, "absent"), ("accounts.google.com:intruder@example.com", "not_allowlisted")],
    ids=["no-header", "not-allowlisted"],
)
def test_status_identity_logs_header_refusals(operator_env, auth_log, monkeypatch, header, state):
    monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", "true")
    assert identity.authenticated_operator_email(None, header) is None
    assert auth_log() == [("WARNING", f"status operator refused assertion=absent header={state}")]


def test_status_identity_logs_an_empty_allowlist(operator_env, auth_log, monkeypatch):
    monkeypatch.setenv("STATUS_OPERATOR_ALLOWLIST", " , ")
    assert identity.authenticated_operator_email(None, f"accounts.google.com:{OPERATOR}") is None
    assert auth_log() == [("WARNING", "status operator refused: STATUS_OPERATOR_ALLOWLIST is empty")]


def test_status_identity_log_never_contains_the_email_or_token(operator_env, iap_keys, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("IAP_TRUSTED_EMAIL_HEADER", "true")
    valid = _sign(_claims())
    mismatched = _sign(_claims(aud=OTHER_AUDIENCE))
    # google-auth's own message for this token quotes the token back.
    malformed = "not-a-jwt-but-long-enough-to-spot-in-a-log"
    identity.authenticated_operator_email(valid)
    identity.authenticated_operator_email(mismatched, f"accounts.google.com:{OPERATOR}")
    identity.authenticated_operator_email(malformed, "accounts.google.com:intruder@example.com")
    assert caplog.records, "nothing was logged, so this test would prove nothing"
    for secret in (OPERATOR, "intruder@example.com", valid, mismatched, malformed):
        assert secret not in caplog.text


def test_status_identity_configure_logging_emits_info_to_stderr(capsys):
    service_logger = logging.getLogger("status_service")
    saved_handlers, saved_level = list(service_logger.handlers), service_logger.level
    service_logger.handlers = []
    try:
        log_setup.configure_logging()
        logging.getLogger(identity.__name__).info("status operator authenticated via=iap_assertion")
        assert "INFO status_service.identity: status operator authenticated via=iap_assertion" in capsys.readouterr().err
    finally:
        service_logger.handlers = saved_handlers
        service_logger.setLevel(saved_level)


def test_status_identity_create_app_configures_logging():
    # app.py builds a Firestore client at import, so this reads the source
    # instead of importing it.
    tree = ast.parse((Path(identity.__file__).parent / "app.py").read_text())
    create_app = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "create_app")
    called = {node.func.id for node in ast.walk(create_app) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "configure_logging" in called
