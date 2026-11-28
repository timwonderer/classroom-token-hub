"""The credential compliance gate (DOM-IDEN-003 §VII.A, SPEC-OPS-004 §V).

A teacher or system administrator who lacks an activated passkey, or whose authenticator seed is under
the 112-bit floor, reaches only credential maintenance, sign-out and (teachers) account destruction.
The decision is made from the live user row on every protected request: nothing is stored, cached in
the session or flashed, and a GET writes nothing.

Principals here come from the canonical fixtures, which are compliant by default (SPEC-TEST-001,
SPEC-TEST-002); each scenario then makes one noncompliant explicitly.
"""

from __future__ import annotations

import pathlib
import re
import uuid

import pyotp
import pytest
from sqlalchemy import event

from app import db
from app.auth import (
    _ADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS as ADMIN_ALLOWED,
    _SYSADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS as SYSADMIN_ALLOWED,
)
from app.feats.base import FEATContext
from app.models import User
from app.services.credential_lifecycle import CredentialCompliance, credential_compliance
from app.utils.auth_username import build_hashed_username_fields
from tests.dom.identity.test_passkey_lifecycle import _new_credential
from tests.dom.identity.test_teacher_recovery_completion import finish, recovery, setup  # noqa: F401
from tests.dom.identity.test_totp_replacement_routes import _confirm, _start
from tests.helpers import temporal
from tests.helpers.canonical_classroom import TEACHERS, _teacher_key_for
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.operation_routes import seed_sysadmin_session
from tests.helpers.passkey import (  # noqa: F401  (fake_passwordless is a fixture)
    HELD_SEED,
    SHORT_SEED,
    ensure_credential_compliance,
    fake_passwordless,
    finish_registration,
    give_totp_seed,
    make_passkey_missing,
    make_totp_noncompliant,
    record_passkey,
    start_registration,
)

STATES = ("passkey_missing", "totp_noncompliant")
TAB = {"passkey_missing": "passkeys", "totp_noncompliant": "authenticator"}
ROLES = ("teacher", "sysadmin")
PREFIX = {"teacher": "/admin", "sysadmin": "/sysadmin"}


# ---------------------------------------------------------------------------
# principals
# ---------------------------------------------------------------------------

def _make(user_id, state):
    {"passkey_missing": make_passkey_missing, "totp_noncompliant": make_totp_noncompliant}[state](user_id)


def _teacher(client, app, key="chemistry_p1"):
    classroom = initialize_as_teacher(key, client, app)
    return classroom, classroom.teacher_user.id


def _sysadmin(client, *, compliant=True):
    from app.services.identity_service import create_system_principal

    name = f"gate_sysadmin_{uuid.uuid4().hex[:8]}"
    with FEATContext("FEAT-IDEN-008", idempotency_key=f"gate-test:sysadmin:{name}"):
        create_system_principal(name)
    user = User.query.filter_by(username_lookup_hash=build_hashed_username_fields(name)[2]).one()
    give_totp_seed(user.id)  # a known 160-bit seed, so the test can compute its codes
    seed_sysadmin_session(client, user_id=user.id, username=name, compliant=compliant)
    return user.id, name


def _principal(role, client, app, state=None):
    if role == "teacher":
        _, user_id = _teacher(client, app)
    else:
        user_id, _ = _sysadmin(client)
    if state:
        _make(user_id, state)
    return user_id


def _classless(user_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"gate-test:classless:{uuid.uuid4().hex}"):
        user = db.session.get(User, user_id)
        user.last_active_class_id = None
        user.last_active_seat_id = None


def _url(app, endpoint, **values):
    with app.test_request_context():
        from flask import url_for
        return url_for(endpoint, **values)


def _home(role):
    return {"teacher": "/admin/", "sysadmin": "/sysadmin/dashboard"}[role]


def _is_gate_refusal(response) -> bool:
    if response.status_code == 403 and (response.get_json(silent=True) or {}).get("error") == "credential_noncompliant":
        return True
    return response.status_code == 302 and "/passkey/settings?tab=" in response.location


def _security_location(role, state):
    return f"{PREFIX[role]}/passkey/settings?tab={TAB[state]}"


# ---------------------------------------------------------------------------
# compliant principals are not touched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_compliant_principal_reaches_the_dashboard(client, app, role):
    user_id = _principal(role, client, app)
    assert credential_compliance(db.session.get(User, user_id)) is CredentialCompliance.COMPLIANT
    assert client.get(_home(role)).status_code == 200


# ---------------------------------------------------------------------------
# the gate: navigation, background requests, direct access
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_noncompliant_principal_is_sent_to_the_security_tab_that_fixes_it(client, app, role, state):
    _principal(role, client, app, state)
    pages = {"teacher": ("/admin/", "/admin/students", "/admin/payroll"),
             "sysadmin": ("/sysadmin/dashboard", "/sysadmin/support")}[role]
    for page in pages:
        response = client.get(page)
        assert response.status_code == 302, page
        assert response.location.endswith(_security_location(role, state)), (page, response.location)


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_background_request_gets_json_403_not_a_redirect(client, app, role, state):
    _principal(role, client, app, state)
    target = {"teacher": "/admin/onboarding/status", "sysadmin": "/sysadmin/dashboard"}[role]
    for headers in ({"X-Requested-With": "XMLHttpRequest"}, {"Sec-Fetch-Mode": "cors"}):
        response = client.get(target, headers=headers)
        assert response.status_code == 403, headers
        body = response.get_json()
        assert body["error"] == "credential_noncompliant" and body["status"] == "error"
    posted = client.post({"teacher": "/admin/students/deletion-preview", "sysadmin": target}[role], json={})
    assert posted.status_code == 403 and posted.get_json()["error"] == "credential_noncompliant"


def test_DOM_IDEN_003__a_noncompliant_sysadmin_is_refused_grafana_and_its_auth_check(client, app):
    user_id, _ = _sysadmin(client)
    assert client.get("/sysadmin/grafana/auth-check").status_code == 200
    make_passkey_missing(user_id)

    assert client.get("/sysadmin/grafana/auth-check").status_code == 403
    proxied = client.get("/sysadmin/grafana/public/build/app.js")
    assert proxied.status_code == 403 and proxied.get_json()["error"] == "credential_noncompliant"
    # the bare console URL is a navigation: sent to the Security tab, not proxied
    assert _is_gate_refusal(client.get("/sysadmin/grafana"))


@pytest.mark.parametrize("state", STATES)
def test_DOM_IDEN_003__direct_access_to_protected_endpoints_is_refused(client, app, state):
    _principal("teacher", client, app, state)
    protected = [
        ("get", _url(app, "admin.dashboard")),
        ("get", _url(app, "admin.students")),
        ("get", _url(app, "admin.onboarding")),
        ("get", _url(app, "admin.select_class_context")),
        ("get", _url(app, "admin.class_delete")),
        ("post", _url(app, "admin.set_current_class")),
        ("post", _url(app, "admin.student_deletion_preview")),
        ("post", _url(app, "admin.onboarding_skip_task")),
        ("post", _url(app, "admin.create_new_class")),
    ]
    for method, path in protected:
        navigated = getattr(client, method)(path)
        assert _is_gate_refusal(navigated), (method, path, navigated.status_code, navigated.location)
        background = getattr(client, method)(path, json={})
        assert _is_gate_refusal(background), (method, path, background.status_code)


@pytest.mark.parametrize("state", STATES)
def test_DOM_IDEN_003__attempted_bypasses_of_the_gate_are_refused(client, app, state):
    _principal("teacher", client, app, state)
    attempts = [
        # a tab query on an endpoint that is not Security does not make it Security
        ("/admin/?tab=passkeys", {}),
        ("/admin/?tab=authenticator&next=/admin/passkey/settings", {}),
        # a request claiming to be a plain navigation, or to prefer HTML, is still refused
        ("/admin/students", {"Sec-Fetch-Mode": "navigate"}),
        ("/admin/students", {"Accept": "text/html", "X-Requested-With": "XMLHttpRequest"}),
        # forwarding headers name no endpoint
        ("/admin/students", {"X-Original-URI": "/admin/passkey/settings", "X-Forwarded-Prefix": "/admin/passkey"}),
        # a settings-looking path that is a different endpoint
        ("/admin/passkey/settings/../students", {}),
        ("/admin//students", {}),
    ]
    for path, headers in attempts:
        response = client.get(path, headers=headers)
        assert response.status_code != 200, (path, headers)
        assert response.status_code in (301, 302, 308, 403, 404), (path, headers, response.status_code)
        if response.status_code == 302 and "/passkey/settings" in response.location:
            assert response.location.endswith(_security_location("teacher", state)), (path, response.location)


@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_gated_get_writes_nothing(client, app, role):
    _principal(role, client, app, "passkey_missing")
    statements = []

    def record(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            statements.append(statement[:80])

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        for headers in ({}, {"X-Requested-With": "XMLHttpRequest"}):
            assert _is_gate_refusal(client.get(_home(role), headers=headers))
    finally:
        event.remove(db.engine, "before_cursor_execute", record)

    assert statements == []
    with client.session_transaction() as session:
        assert "_flashes" not in session


# ---------------------------------------------------------------------------
# what stays reachable
# ---------------------------------------------------------------------------

def _call_endpoint(client, app, endpoint):
    rule = next(app.url_map.iter_rules(endpoint))
    path = _url(app, endpoint, **{arg: 0 for arg in rule.arguments})
    method = next(m for m in ("GET", "POST", "DELETE") if m in rule.methods)
    request = {"GET": client.get, "POST": client.post, "DELETE": client.delete}[method]
    return request(path) if method == "GET" else request(path, json={})


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__every_maintenance_endpoint_stays_reachable_while_noncompliant(client, app, role, state):
    _principal(role, client, app, state)
    allowed = {"teacher": ADMIN_ALLOWED, "sysadmin": SYSADMIN_ALLOWED}[role]
    for endpoint in sorted(allowed):
        response = _call_endpoint(client, app, endpoint)
        assert not _is_gate_refusal(response), (endpoint, response.status_code, response.location)
    page = client.get(f"{PREFIX[role]}/passkey/settings")
    assert page.status_code == 200


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__sign_out_is_not_gated(client, app, role, state):
    _principal(role, client, app, state)
    response = client.post(f"{PREFIX[role]}/logout")
    assert response.status_code == 302 and response.location.split("?")[0].endswith(f"{PREFIX[role]}/login")
    assert client.get(_home(role)).location.split("?")[0].endswith(f"{PREFIX[role]}/login")


def test_DOM_IDEN_003__the_allowlists_are_exactly_credential_maintenance_and_account_destruction():
    maintenance = {"passkey_settings", "passkey_register_start", "passkey_register_finish", "passkey_delete",
                   "passkey_resume", "passkey_cancel", "totp_replace_challenge", "totp_replace_start",
                   "totp_replace_confirm", "totp_replace_cancel"}
    assert {e.split(".", 1)[1] for e in SYSADMIN_ALLOWED} == maintenance
    assert {e.split(".", 1)[1] for e in SYSADMIN_ALLOWED if not e.startswith("sysadmin.")} == set()
    assert {e.split(".", 1)[1] for e in ADMIN_ALLOWED} == maintenance | {"account_delete"}
    assert all(e.startswith("admin.") for e in ADMIN_ALLOWED)


def _inline_script_text(html: str) -> str:
    """Text of every <script> element, read with the stdlib HTML parser (not a regexp)."""
    from html.parser import HTMLParser

    chunks: list[str] = []

    class _Scripts(HTMLParser):
        in_script = False

        def handle_starttag(self, tag, attrs):
            self.in_script = tag == "script"

        def handle_endtag(self, tag):
            if tag == "script":
                self.in_script = False

        def handle_data(self, data):
            if self.in_script:
                chunks.append(data)

    _Scripts().feed(html)
    return "\n".join(chunks)


@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__every_request_the_security_page_makes_is_allowlisted(client, app, role):
    """Structural proof: each URL the page's script configures resolves to an allowlisted (or undecorated sign-in) endpoint."""
    _principal(role, client, app, "passkey_missing")
    html = client.get(f"{PREFIX[role]}/passkey/settings").get_data(as_text=True)
    script = _inline_script_text(html)
    paths = set(re.findall(r'"(/(?:admin|sysadmin)/[^"]*)"', script))
    assert len(paths) >= 10, paths
    adapter = app.url_map.bind("localhost")
    allowed = {"teacher": ADMIN_ALLOWED, "sysadmin": SYSADMIN_ALLOWED}[role]
    undecorated_sign_in = {f"{PREFIX[role].strip('/')}.login"}
    for path in paths:
        endpoint = None
        for method in ("POST", "DELETE", "GET"):
            try:
                endpoint, _ = adapter.match(path.replace("/0/", "/1/"), method=method)
                break
            except Exception:
                continue
        assert endpoint is not None, path
        assert endpoint in allowed or endpoint in undecorated_sign_in, (path, endpoint)


def test_DOM_IDEN_003__teacher_account_destruction_stays_reachable_and_its_form_posts_only_there(client, app):
    _, user_id = _teacher(client, app)
    make_passkey_missing(user_id)

    page = client.get("/admin/account-delete")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert re.findall(r'<form[^>]*action="([^"]+)"', html).count("/admin/account-delete") == 1
    # The page's own script makes no request of its own: it only submits that form after the timed gate.
    assert "fetch(" not in (pathlib.Path(app.root_path).parent / "templates" / "admin_account_delete.html").read_text()
    refused = client.post("/admin/account-delete", data={"request_type": "account", "gate_phrase": "nope"})
    assert refused.status_code == 302 and refused.location.endswith("/admin/account-delete")


# ---------------------------------------------------------------------------
# other roles and cross-role access
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_DOM_IDEN_003__a_noncompliant_teacher_gets_nothing_from_the_sysadmin_console(client, app, state):
    _principal("teacher", client, app, state)
    for path in ("/sysadmin/dashboard", "/sysadmin/passkey/settings", "/sysadmin/support"):
        response = client.get(path)
        assert response.status_code == 302 and "/sysadmin/login" in response.location, path


@pytest.mark.parametrize("state", STATES)
def test_DOM_IDEN_003__a_noncompliant_sysadmin_gets_nothing_from_the_teacher_site(client, app, state):
    _principal("sysadmin", client, app, state)
    for path in ("/admin/", "/admin/passkey/settings", "/admin/account-delete"):
        response = client.get(path)
        assert response.status_code == 302 and "/admin/login" in response.location, path


def test_DOM_IDEN_003__a_student_session_reaches_neither_console(client, app):
    initialize_as_student("chemistry_p1", client, app)
    for path in ("/admin/", "/admin/passkey/settings", "/admin/account-delete"):
        assert client.get(path).location.split("?")[0].endswith("/admin/login"), path
    for path in ("/sysadmin/dashboard", "/sysadmin/passkey/settings"):
        assert client.get(path).location.split("?")[0].endswith("/sysadmin/login"), path


def test_DOM_IDEN_003__the_gate_does_not_touch_students(client, app):
    initialize_as_student("chemistry_p1", client, app)
    assert client.get("/student/dashboard").status_code == 200


# ---------------------------------------------------------------------------
# live state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__compliance_is_read_live_so_a_change_takes_effect_on_the_next_request(client, app, role):
    user_id = _principal(role, client, app)
    assert client.get(_home(role)).status_code == 200

    make_passkey_missing(user_id)
    gated = client.get(_home(role))
    assert gated.status_code == 302 and gated.location.endswith(_security_location(role, "passkey_missing"))

    ensure_credential_compliance(user_id)
    assert client.get(_home(role)).status_code == 200

    give_totp_seed(user_id, SHORT_SEED)
    gated = client.get(_home(role))
    assert gated.status_code == 302 and gated.location.endswith(_security_location(role, "totp_noncompliant"))

    give_totp_seed(user_id, HELD_SEED)
    assert client.get(_home(role)).status_code == 200


def test_DOM_IDEN_003__the_session_carries_no_compliance_decision(client, app):
    _, user_id = _teacher(client, app)
    make_passkey_missing(user_id)
    client.get("/admin/")
    with client.session_transaction() as session:
        assert not [key for key in session if "complian" in key.lower() or "gate" in key.lower()]


def test_DOM_IDEN_003__an_absent_passkey_is_reported_before_a_short_seed(client, app):
    _, user_id = _teacher(client, app)
    make_totp_noncompliant(user_id)
    make_passkey_missing(user_id)
    assert client.get("/admin/").location.endswith(_security_location("teacher", "passkey_missing"))


# ---------------------------------------------------------------------------
# a teacher with no class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_DOM_IDEN_003__a_classless_noncompliant_teacher_goes_to_security_not_onboarding(client, app, state):
    _, user_id = _teacher(client, app)
    _make(user_id, state)
    _classless(user_id)

    response = client.get("/admin/")
    assert response.status_code == 302 and response.location.endswith(_security_location("teacher", state))
    assert "onboarding" not in response.location
    onboarding = client.get("/admin/onboarding")
    assert onboarding.location.endswith(_security_location("teacher", state))
    assert client.get("/admin/passkey/settings").status_code == 200


def test_DOM_IDEN_003__onboarding_does_not_obstruct_remediation_for_a_classless_teacher(client, app, fake_passwordless):
    """Neither the gate nor the classless-teacher onboarding redirect stands between the teacher and remediation."""
    _, user_id = _teacher(client, app)
    make_passkey_missing(user_id)
    record_passkey(user_id, "cred-a", fake_passwordless)
    give_totp_seed(user_id, SHORT_SEED)
    _classless(user_id)

    assert client.get("/admin/").location.endswith(_security_location("teacher", "totp_noncompliant"))
    for endpoint in sorted(ADMIN_ALLOWED):
        response = _call_endpoint(client, app, endpoint)
        assert not _is_gate_refusal(response), endpoint
        assert "onboarding" not in (response.location or ""), endpoint
    # The challenge is actually issued, and a replacement actually completes, with no class.
    started = _start(client, fake_passwordless, "cred-a")
    assert started.status_code == 200
    secret = started.get_json()["secret"]
    done = _confirm(client, pyotp.TOTP(secret).at(temporal.now()))
    assert done.status_code == 200
    assert credential_compliance(db.session.get(User, user_id)) is CredentialCompliance.COMPLIANT


def test_DOM_IDEN_003__a_classless_compliant_teacher_still_goes_to_onboarding(client, app):
    _, user_id = _teacher(client, app)
    _classless(user_id)
    assert client.get("/admin/").location.endswith("/admin/onboarding")


# ---------------------------------------------------------------------------
# remediation end to end, with the fake provider
# ---------------------------------------------------------------------------

def _sign_in(client, role, monkeypatch, username, seed):
    """Sign in through the real route. The login routes check the code against the wall clock, so the code is the
    next window's (``valid_window=1`` accepts it), which is never the step a code was already spent in."""
    monkeypatch.setattr("app.routes.admin.verify_turnstile_token", lambda *a, **k: True)
    monkeypatch.setattr("app.routes.system_admin.verify_turnstile_token", lambda *a, **k: True)
    code = pyotp.TOTP(seed).at(temporal.now(), counter_offset=1)
    response = client.post(f"{PREFIX[role]}/login", data={"username": username, "totp_code": code})
    assert response.status_code == 302 and "/login" not in response.location, response.location
    return response


def _principal_with_username(role, client, app):
    if role == "teacher":
        classroom, user_id = _teacher(client, app)
        return user_id, TEACHERS[_teacher_key_for(classroom)]["username"]
    return _sysadmin(client)


@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_principal_with_no_passkey_remediates_end_to_end(client, app, fake_passwordless, monkeypatch, role):
    """No passkey -> gated to the Passkeys tab -> enrol (the sign-in ends) -> sign in with the authenticator -> dashboard."""
    user_id, username = _principal_with_username(role, client, app)
    make_passkey_missing(user_id)
    prefix = PREFIX[role]
    start = temporal.now()

    with temporal.pinned_clock(start):
        assert client.get(_home(role)).location.endswith(_security_location(role, "passkey_missing"))
        started = start_registration(client, prefix=prefix, code=pyotp.TOTP(HELD_SEED).at(start))
        assert started.status_code == 200, started.get_json()
        token, _ = _new_credential(fake_passwordless, user_id)
        finished = finish_registration(client, token, prefix=prefix, name="First key")
        assert finished.status_code == 200, finished.get_json()
        # enrolment ends the sign-in
        assert client.get(_home(role)).location.split("?")[0].endswith(f"{prefix}/login")

    _sign_in(client, role, monkeypatch, username, HELD_SEED)
    assert credential_compliance(db.session.get(User, user_id)) is CredentialCompliance.COMPLIANT
    home = client.get(_home(role))
    assert home.status_code == 200, home.location


@pytest.mark.parametrize("role", ROLES)
def test_DOM_IDEN_003__a_principal_with_a_short_seed_remediates_end_to_end(client, app, fake_passwordless, monkeypatch, role):
    """A short seed cannot sign in with TOTP (pyotp refuses it), so the principal arrives by passkey: gated to the
    Authenticator tab -> step-up replace (the sign-in ends) -> sign in with the new authenticator -> dashboard."""
    user_id, username = _principal_with_username(role, client, app)
    make_passkey_missing(user_id)
    record_passkey(user_id, "cred-a", fake_passwordless)
    give_totp_seed(user_id, SHORT_SEED)
    prefix = PREFIX[role]
    start = temporal.now()

    with temporal.pinned_clock(start):
        client.post(f"{prefix}/logout")
        signed_in = client.post(f"{prefix}/passkey/auth/finish", json={"token": fake_passwordless.sign_in_token("cred-a")})
        assert signed_in.status_code == 200, signed_in.get_json()
        assert credential_compliance(db.session.get(User, user_id)) is CredentialCompliance.TOTP_NONCOMPLIANT
        gated = client.get(_home(role))
        assert gated.location.endswith(_security_location(role, "totp_noncompliant"))
        assert client.get(gated.location).status_code == 200

        staged = _start(client, fake_passwordless, "cred-a", prefix)
        assert staged.status_code == 200, staged.get_json()
        new_seed = staged.get_json()["secret"]
        done = _confirm(client, pyotp.TOTP(new_seed).at(start), prefix)
        assert done.status_code == 200 and done.get_json()["redirect"].endswith(f"{prefix}/login")
        # replacement ends the sign-in
        assert client.get(_home(role)).location.split("?")[0].endswith(f"{prefix}/login")

    _sign_in(client, role, monkeypatch, username, new_seed)
    assert credential_compliance(db.session.get(User, user_id)) is CredentialCompliance.COMPLIANT
    home = client.get(_home(role))
    assert home.status_code == 200, home.location


def test_DOM_IDEN_003__after_satar_completion_the_teacher_is_gated_to_enrolment(client, app, recovery):  # noqa: F811
    """Recovery leaves a fresh strong seed and no passkey: the next request goes to passkey enrolment."""
    grant = setup(recovery)
    assert grant and finish(recovery, grant)
    classroom = recovery.classes[0]
    db.session.refresh(recovery.teacher)
    assert credential_compliance(recovery.teacher) is CredentialCompliance.PASSKEY_MISSING

    with client.session_transaction() as sess:
        set_canonical_context(
            sess, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
            seat_id=classroom.teacher_seat.id, role="teacher",
        )
        sess["role"] = "admin"
    response = client.get("/admin/")
    assert response.status_code == 302 and response.location.endswith(_security_location("teacher", "passkey_missing"))
    assert client.get(response.location).status_code == 200


# ---------------------------------------------------------------------------
# the Security page
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ROLES)
def test_the_security_page_has_two_tabs_selected_by_the_tab_query(client, app, role):
    _principal(role, client, app)
    base = f"{PREFIX[role]}/passkey/settings"

    default = client.get(base).get_data(as_text=True)
    assert 'id="passkeys-tab"' in default and 'id="authenticator-tab"' in default
    assert re.search(r'class="nav-link active" id="passkeys-tab"', default)
    assert 'class="tab-pane fade show active" id="passkeys-pane"' in default

    authenticator = client.get(f"{base}?tab=authenticator").get_data(as_text=True)
    assert re.search(r'class="nav-link active" id="authenticator-tab"', authenticator)
    assert 'class="tab-pane fade show active" id="authenticator-pane"' in authenticator
    assert 'aria-selected="true"' in authenticator

    for bogus in ("bogus", "<script>alert(1)</script>", ""):
        page = client.get(base, query_string={"tab": bogus}).get_data(as_text=True)
        assert 'class="tab-pane fade show active" id="passkeys-pane"' in page
        assert "alert(1)" not in page


@pytest.mark.parametrize("role", ROLES)
def test_the_security_page_keeps_the_ids_the_script_binds_and_has_no_page_level_code_card(client, app, role):
    _principal(role, client, app)
    html = client.get(f"{PREFIX[role]}/passkey/settings").get_data(as_text=True)
    for element_id in ("passkey-feedback", "registerPasskeyButton", "totpReplaceButton", "totp-replace-setup",
                       "totp-replace-qr", "totp-replace-secret", "totp-replace-code", "totpConfirmButton",
                       "totpAbandonButton", "totp-replace-feedback"):
        assert f'id="{element_id}"' in html, element_id
    assert "passkey-totp-code" not in html and "codeInputId: 'passkey-totp-code'" not in html


@pytest.mark.parametrize("role", ROLES)
def test_the_navigation_calls_the_page_security(client, app, role):
    _principal(role, client, app)
    page = client.get(_home(role)).get_data(as_text=True)
    href = f'href="{PREFIX[role]}/passkey/settings"'
    assert href in page
    link = page[page.index(href):]
    link = link[:link.index("</a>")]
    assert "Security" in link and "Passkey" not in link
    assert "<title>Security</title>" in client.get(f"{PREFIX[role]}/passkey/settings").get_data(as_text=True)


@pytest.mark.parametrize("role", ROLES)
def test_the_compliance_banner_names_what_is_required_only_when_noncompliant(client, app, role):
    user_id = _principal(role, client, app)
    page = f"{PREFIX[role]}/passkey/settings"
    assert "to continue" not in client.get(page).get_data(as_text=True)

    make_passkey_missing(user_id)
    assert "Register a passkey to continue" in client.get(page).get_data(as_text=True)

    ensure_credential_compliance(user_id)
    make_totp_noncompliant(user_id)
    html = client.get(page).get_data(as_text=True)
    assert "Replace your authenticator app to continue" in html
    assert "Register a passkey to continue" not in html


def test_the_getting_started_widget_labels_the_security_task(client, app):
    _teacher(client, app)
    html = client.get("/admin/").get_data(as_text=True)
    assert "Secure your account" in html and "Set up a passkey" not in html
