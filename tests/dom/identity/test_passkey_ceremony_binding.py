"""The passkey ceremony's origin and RP ID are checked against this deployment's own configuration.

passwordless.dev records the origin and RP ID the browser supplied and keeps no allowed list,
so FEAT-IDEN-102 §VI requires the application to compare what the provider echoes with
``PASSKEY_EXPECTED_ORIGIN`` (and its hostname), never with anything the request carried.
"""
from __future__ import annotations

import pytest

from app import db
from app.models import CredentialOperationStage, PasskeyCredential
from app.services import passkey_service
from app.services.passkey_service import PasskeyError
from tests.dom.identity.helpers import admin_passkey_auth_finish
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.passkey import (  # noqa: F401  (fake_passwordless is a fixture)
    EXPECTED_ORIGIN, EXPECTED_RP_ID, fake_passwordless, finish_registration, give_totp_seed, record_passkey,
    start_registration,
)
from tests.dom.identity.test_passkey_lifecycle import _bound, _open_operations, _new_credential

WRONG = [
    ("origin", "https://evil.test"),
    ("origin", "http://cth.test"),
    ("origin", "https://cth.test:8443"),
    ("origin", "https://CTH.test"),
    ("origin", None),
    ("origin", ""),
    ("rp_id", "evil.test"),
    ("rp_id", "sub.cth.test"),
    ("rp_id", None),
]


def _teacher(client, app, fake, passkeys=()):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    user_id = classroom.teacher_user.id
    give_totp_seed(user_id)
    for credential in passkeys:
        record_passkey(user_id, credential, fake)
    return user_id


@pytest.mark.parametrize("attribute, value", WRONG)
def test_a_registration_from_another_origin_or_rp_id_records_no_candidate(
    client, app, fake_passwordless, attribute, value,
):
    user_id = _teacher(client, app, fake_passwordless)
    assert start_registration(client).status_code == 200
    setattr(fake_passwordless, attribute, value)
    token, _ = _new_credential(fake_passwordless, user_id)

    response = finish_registration(client, token)

    assert response.status_code == 400
    assert _bound(user_id) == []
    (operation,) = _open_operations(user_id)
    assert operation.stage is CredentialOperationStage.REGISTRATION_PENDING
    assert operation.new_credential_id is None


@pytest.mark.parametrize("attribute, value", WRONG)
def test_a_sign_in_from_another_origin_or_rp_id_is_refused_and_stamps_nothing(
    client, app, fake_passwordless, attribute, value,
):
    user_id = _teacher(client, app, fake_passwordless, passkeys=("cred-a",))
    with client.session_transaction() as sess:
        sess.clear()
    setattr(fake_passwordless, attribute, value)

    response = admin_passkey_auth_finish(client, token=fake_passwordless.sign_in_token("cred-a"))

    assert response.status_code == 401
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None
    db.session.expire_all()
    assert PasskeyCredential.query.filter_by(user_id=user_id).one().last_used is None


def test_the_configured_origin_and_rp_id_pass_unchanged(client, app, fake_passwordless):
    user_id = _teacher(client, app, fake_passwordless)
    assert start_registration(client).status_code == 200
    token, credential_id = _new_credential(fake_passwordless, user_id)

    assert finish_registration(client, token).status_code == 200
    assert _bound(user_id) == [credential_id]
    assert (fake_passwordless.origin, fake_passwordless.rp_id) == (EXPECTED_ORIGIN, EXPECTED_RP_ID)


def test_a_trailing_slash_and_rp_id_case_are_tolerated_nothing_else(app, fake_passwordless):
    from types import SimpleNamespace
    with app.app_context():
        passkey_service.check_ceremony_binding(SimpleNamespace(origin="https://cth.test/", rp_id="CTH.test"))
        with pytest.raises(PasskeyError):
            passkey_service.check_ceremony_binding(SimpleNamespace(origin="https://cth.test/x", rp_id="cth.test"))


def test_an_unconfigured_expectation_refuses_everything(app):
    from types import SimpleNamespace
    with app.app_context():
        app.config["PASSKEY_EXPECTED_ORIGIN"] = ""
        app.config["PASSKEY_EXPECTED_RP_ID"] = ""
        try:
            with pytest.raises(PasskeyError):
                passkey_service.check_ceremony_binding(SimpleNamespace(origin="", rp_id=""))
        finally:
            app.config["PASSKEY_EXPECTED_ORIGIN"] = EXPECTED_ORIGIN
            app.config["PASSKEY_EXPECTED_RP_ID"] = EXPECTED_RP_ID


def test_the_expectation_is_never_taken_from_the_request(client, app, fake_passwordless):
    """A request that claims the (wrong) ceremony origin in its headers does not move the expectation."""
    user_id = _teacher(client, app, fake_passwordless)
    assert start_registration(client).status_code == 200
    fake_passwordless.origin, fake_passwordless.rp_id = "https://evil.test", "evil.test"
    token, _ = _new_credential(fake_passwordless, user_id)

    response = client.post(
        "/admin/passkey/register/finish",
        json={"token": token, "binding": client.last_registration_binding, "authenticatorName": "x",
              "origin": "https://evil.test", "rpId": "evil.test"},
        headers={"Origin": "https://evil.test"},
    )

    assert response.status_code == 400 and _bound(user_id) == []


def _provider_verify_callers(source: str) -> bool:
    """Pure detector: does ``source`` call ``verify_signin_token(`` or the SDK's ``.sign_in(``?

    Whitespace between the name and the parenthesis is tolerated, as Python does; a ``def`` is not a call.
    """
    import re
    return bool(re.search(r"(?<!def )\bverify_signin_token\s*\(|\.sign_in\s*\(\s*VerifySignIn", source))


def test_mutation_the_detector_catches_a_spaced_sign_in_call():
    assert _provider_verify_callers("sdk.sign_in (VerifySignIn(token))")
    assert _provider_verify_callers("sdk.sign_in(VerifySignIn(token))")
    assert _provider_verify_callers("verified = verify_signin_token (client, token)")
    assert not _provider_verify_callers("def verify_signin_token(client, token): ...")
    assert not _provider_verify_callers("def sign_in(request): return None")


def test_every_provider_verification_goes_through_the_check():
    """No caller reaches the provider's verification without it (a structural guard)."""
    import inspect
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[3] / "app"
    callers = [
        str(path.relative_to(root)) for path in root.rglob("*.py")
        if _provider_verify_callers(path.read_text())
    ]
    assert callers == ["services/passkey_service.py"]
    source = inspect.getsource(passkey_service._verify)
    assert "check_ceremony_binding(verified)" in source


# ---- the real /signin/verify response shape -----------------------------------

def _raw_verify(**overrides):
    import json
    body = {
        "success": True, "userId": "u1", "credentialId": "c1", "type": "passkey_signin",
        "nickname": None, "origin": EXPECTED_ORIGIN, "rpId": EXPECTED_RP_ID,
        "timestamp": "2026-11-27T12:00:00Z", "expiresAt": "2026-11-27T12:01:00Z",
        "tokenId": "t1", "device": "Chrome", "country": "US",
    }
    body.update(overrides)
    return json.dumps({k: v for k, v in body.items() if v is not Ellipsis})


def test_a_raw_verify_response_with_rpId_passes_the_binding(app):
    from app.utils.passwordless_client import parse_signin_verify_response
    verified = parse_signin_verify_response(_raw_verify())
    assert verified.rp_id == EXPECTED_RP_ID
    with app.app_context():
        passkey_service.check_ceremony_binding(verified)  # no refusal


def test_a_raw_verify_response_without_rpId_is_refused(app):
    from app.utils.passwordless_client import parse_signin_verify_response
    verified = parse_signin_verify_response(_raw_verify(rpId=Ellipsis))
    assert verified.rp_id is None
    with app.app_context():
        with pytest.raises(passkey_service.PasskeyError):
            passkey_service.check_ceremony_binding(verified)


def test_the_sdk_schema_drops_rpId_which_is_why_the_parser_is_narrowed():
    """Documents the defect: the stock schema reads ``rpid`` and so loses ``/signin/verify``'s ``rpId``."""
    from passwordless.serialization import VerifiedUserSchema
    assert VerifiedUserSchema().loads(_raw_verify()).rp_id is None


# ---- startup -----------------------------------------------------------------

def _create_app(monkeypatch, *, key, origin):
    from app import create_app
    monkeypatch.setenv("PASSWORDLESS_API_KEY", key)
    if origin is None:
        monkeypatch.delenv("PASSKEY_EXPECTED_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("PASSKEY_EXPECTED_ORIGIN", origin)
    return create_app()


DIAGNOSTIC = "passkey ceremony refused: PASSKEY_EXPECTED_ORIGIN is not configured"


def test_the_app_starts_with_passkeys_set_and_no_origin_and_says_so_once(monkeypatch, caplog):
    for blank in (None, "", "   "):
        caplog.clear()
        with caplog.at_level("WARNING"):
            app = _create_app(monkeypatch, key="k", origin=blank)
        assert app.config["PASSKEY_EXPECTED_ORIGIN"] == "" and app.config["PASSKEY_EXPECTED_RP_ID"] == ""
        warnings = [r for r in caplog.records if "PASSKEY_EXPECTED_ORIGIN is missing or invalid" in r.getMessage()]
        assert len(warnings) == 1


@pytest.mark.parametrize("origin", [
    "https://cth.test/login", "https://cth.test/", "cth.test", "//cth.test", "ftp://cth.test",
    "https://user@cth.test", "https://cth.test?x=1", "https://cth.test#f", "https://", "https://cth.test:99999",
    "https://cth .test",
])
def test_the_app_starts_with_a_malformed_origin_and_leaves_the_expectation_empty(monkeypatch, caplog, origin):
    with caplog.at_level("WARNING"):
        app = _create_app(monkeypatch, key="k", origin=origin)
    assert app.config["PASSKEY_EXPECTED_ORIGIN"] == "" and app.config["PASSKEY_EXPECTED_RP_ID"] == ""
    assert any("missing or invalid" in r.getMessage() for r in caplog.records)


def test_without_an_origin_registration_start_and_verification_both_refuse_and_leave_nothing_pending(
    client, app, fake_passwordless, caplog,
):
    user_id = _teacher(client, app, fake_passwordless)
    app.config["PASSKEY_EXPECTED_ORIGIN"] = ""
    app.config["PASSKEY_EXPECTED_RP_ID"] = ""
    try:
        with caplog.at_level("ERROR"):
            started = start_registration(client)
            from types import SimpleNamespace
            with app.app_context(), pytest.raises(PasskeyError):
                passkey_service.check_ceremony_binding(SimpleNamespace(origin=EXPECTED_ORIGIN, rp_id=EXPECTED_RP_ID))
    finally:
        app.config["PASSKEY_EXPECTED_ORIGIN"] = EXPECTED_ORIGIN
        app.config["PASSKEY_EXPECTED_RP_ID"] = EXPECTED_RP_ID

    assert started.status_code == 400
    assert _open_operations(user_id) == [] and fake_passwordless.calls == []
    messages = [r.getMessage() for r in caplog.records if DIAGNOSTIC in r.getMessage()]
    assert len(messages) >= 2
    assert all(user_id not in m for m in messages)


def test_student_services_do_not_depend_on_the_passkey_origin(monkeypatch):
    app = _create_app(monkeypatch, key="k", origin=None)
    client = app.test_client()
    assert client.get("/student/login").status_code == 200


def test_startup_derives_the_rp_id_from_the_origin_hostname(monkeypatch):
    for origin, rp_id in (("https://CTH.Test:8443", "cth.test"), ("http://localhost:5000", "localhost")):
        app = _create_app(monkeypatch, key="k", origin=origin)
        assert app.config["PASSKEY_EXPECTED_ORIGIN"] == origin.lower()
        assert app.config["PASSKEY_EXPECTED_RP_ID"] == rp_id


def test_startup_without_passkeys_needs_no_origin(monkeypatch):
    app = _create_app(monkeypatch, key="", origin=None)
    assert app.config["PASSKEY_EXPECTED_ORIGIN"] == "" and app.config["PASSKEY_EXPECTED_RP_ID"] == ""


@pytest.mark.parametrize("raw, origin, rp_id", [
    ("https://CTH.Test", "https://cth.test", "cth.test"),
    ("https://cth.test:443", "https://cth.test", "cth.test"),
    ("https://cth.test:8443", "https://cth.test:8443", "cth.test"),
    ("http://cth.test:80", "http://cth.test", "cth.test"),
    ("HTTP://Localhost:5000", "http://localhost:5000", "localhost"),
    ("https://CTH.Test:443", "https://cth.test", "cth.test"),
])
def test_the_configured_origin_is_canonicalized_as_a_browser_serializes_it(raw, origin, rp_id):
    assert passkey_service.parse_expected_origin(raw) == (origin, rp_id)


@pytest.mark.parametrize("raw", ["https://cth.test/p", "https://cth.test?q", "https://cth.test#f", "https://u@cth.test"])
def test_canonicalization_still_rejects_path_query_fragment_and_userinfo(raw):
    with pytest.raises(passkey_service.PasskeyOriginConfigError):
        passkey_service.parse_expected_origin(raw)


def test_a_browser_origin_passes_when_configured_in_a_non_canonical_spelling(monkeypatch):
    app = _create_app(monkeypatch, key="k", origin="https://CTH.Test:443")
    from types import SimpleNamespace
    with app.app_context():
        passkey_service.check_ceremony_binding(SimpleNamespace(origin="https://cth.test", rp_id="cth.test"))


def test_a_missing_public_key_refuses_registration_start_before_any_operation_exists(
    client, app, fake_passwordless, monkeypatch,
):
    user_id = _teacher(client, app, fake_passwordless)
    monkeypatch.delenv("PASSWORDLESS_API_PUBLIC", raising=False)

    response = start_registration(client)

    assert response.status_code == 503 and response.get_json()["code"] == "not_configured"
    assert _open_operations(user_id) == []
    from app.models import CredentialOperation
    db.session.expire_all()
    assert CredentialOperation.query.filter_by(user_id=user_id).count() == 0
