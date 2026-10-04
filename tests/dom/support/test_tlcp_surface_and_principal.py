"""TLCP records the surface a request asked for and the principal who asked.

Production, 2026-10-02 17:20-17:21 UTC: a Chromebook signed in as a student
followed the landing page's operator sign-in button to /sysadmin/login, loaded
it and submitted it twice. No sysadmin session was established, yet TLCP logged
eight ``TLCP-INVARIANT-VIOLATION: sysadmin request unexpectedly carries
canonical class context`` lines at ERROR. TLCP had named the request a
"sysadmin request" by its URL, and treated the student's class context as a
violation of a rule about sysadmins.

The URL answers what surface was requested; the authenticated principal answers
who requested it (INV-ARC-019 §V: "No identifier answers more than its assigned
question"; §XIII). The invariant concerns the principal -- a system
administrator holds no class context (INV-CORE-000 §III.4, SPEC-OPS-004 §V) --
on every surface.

    student/teacher + sysadmin surface   -> TLCP-SURFACE-PRINCIPAL-MISMATCH, INFO
    sysadmin + class context, any URL    -> TLCP-INVARIANT-VIOLATION, ERROR
    anonymous + sysadmin surface         -> nothing
"""

import logging

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import User
from app.services import tlcp
from tests.dom.interpretation.helpers import create_sysadmin
from tests.helpers.classroom_initializer import (
    initialize,
    initialize_as_student,
    initialize_as_teacher,
)
from tests.helpers.operation_routes import seed_sysadmin_session

VIOLATION = "TLCP-INVARIANT-VIOLATION"
MISMATCH = "TLCP-SURFACE-PRINCIPAL-MISMATCH"
IDENTITY_KEYS = ("user_id", "role", "class_id", "current_session_nonce")


def _identity(client):
    with client.session_transaction() as sess:
        return {key: sess.get(key) for key in IDENTITY_KEYS}


def _records(caplog, token):
    return [r for r in caplog.records if r.getMessage().startswith(token)]


def _capture(caplog):
    return caplog.at_level(logging.INFO)


# -------------------- today's shape --------------------


def test_INV_ARC_019__student_at_sysadmin_login_is_a_mismatch_not_a_violation(client, app, caplog):
    """The production event, replayed: GET then a refused POST, by a student."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    before = _identity(client)
    assert before["user_id"] == student.user.id

    with _capture(caplog):
        page = client.get("/sysadmin/login")
        submit = client.post(
            "/sysadmin/login",
            data={"username": "not_an_operator", "totp_code": "000000"},
        )

    assert page.status_code == 200
    # The existing failure path: "Invalid credentials or TOTP." and back to the form.
    assert submit.status_code == 302
    assert submit.headers["Location"].endswith("/sysadmin/login")

    assert _records(caplog, VIOLATION) == []

    get_line, post_line = _records(caplog, MISMATCH)
    for record in (get_line, post_line):
        assert record.levelno == logging.INFO
        assert record.tlcp_surface == "sysadmin_authentication"
        assert record.tlcp_principal == "student"
        assert record.tlcp_class_context == "present"
    # SPEC-OPS-003 §VI: rendering the form completed; the refused submission is
    # a deliberate rejection.
    assert get_line.tlcp_outcome == "SUCCESS"
    assert "method=GET" in get_line.getMessage()
    assert post_line.tlcp_outcome == "EXPECTED_DENIAL"
    assert post_line.tlcp_principal_after == "student"
    assert "method=POST" in post_line.getMessage()
    assert (
        "surface=sysadmin_authentication principal=student class_context=present outcome=EXPECTED_DENIAL"
        in post_line.getMessage()
    )

    # The student is still signed in, in the same class.
    assert _identity(client) == before
    db.session.expire_all()
    assert db.session.get(User, student.user.id).last_active_class_id == classroom.class_id
    assert client.get("/student/dashboard").status_code == 200


def test_INV_ARC_019__mismatch_line_carries_no_username(client, app, caplog):
    """SPEC-SEC-001: the submitted login name never reaches the log."""
    initialize_as_student("chemistry_p1", client, app)
    with _capture(caplog):
        client.post("/sysadmin/login", data={"username": "probe_login_name", "totp_code": "000000"})
    assert _records(caplog, MISMATCH)
    assert not any("probe_login_name" in r.getMessage() for r in caplog.records)


def test_INV_ARC_019__student_at_sysadmin_console_is_a_denied_mismatch(client, app, caplog):
    initialize_as_student("chemistry_p1", client, app)
    with _capture(caplog):
        response = client.get("/sysadmin/dashboard")

    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]
    assert _records(caplog, VIOLATION) == []
    (line,) = _records(caplog, MISMATCH)
    assert line.tlcp_surface == "sysadmin_console"
    assert line.tlcp_principal == "student"
    assert line.tlcp_outcome == "EXPECTED_DENIAL"


def test_INV_ARC_019__teacher_at_sysadmin_login_is_a_mismatch_not_a_violation(client, app, caplog):
    initialize_as_teacher("chemistry_p1", client, app)
    with _capture(caplog):
        assert client.get("/sysadmin/login").status_code == 200

    assert _records(caplog, VIOLATION) == []
    (line,) = _records(caplog, MISMATCH)
    assert line.levelno == logging.INFO
    assert line.tlcp_surface == "sysadmin_authentication"
    assert line.tlcp_principal == "teacher"
    assert line.tlcp_class_context == "present"
    assert line.tlcp_outcome == "SUCCESS"


def test_INV_ARC_019__anonymous_at_sysadmin_login_records_nothing(client, caplog):
    """The operator's own path, and the Grafana redirect loop: no principal, nothing to record."""
    with _capture(caplog):
        assert client.get("/sysadmin/login").status_code == 200
        client.post("/sysadmin/login", data={"username": "nobody", "totp_code": "000000"})

    assert _records(caplog, VIOLATION) == []
    assert _records(caplog, MISMATCH) == []


# -------------------- the surface dimension --------------------


def test_INV_ARC_019__student_on_the_application_surface_records_no_mismatch(client, app, caplog):
    """The principal alone is not the event: the surface must be a sysadmin one."""
    initialize_as_student("chemistry_p1", client, app)
    with _capture(caplog):
        assert client.get("/student/dashboard").status_code == 200

    assert _records(caplog, MISMATCH) == []
    assert _records(caplog, VIOLATION) == []


def test_INV_ARC_019__surface_is_named_from_the_admission_rule(app):
    """Every sysadmin endpoint is either console (system_admin_required) or one
    of the sign-in endpoints that must admit a caller with no sysadmin session.
    A new unauthenticated sysadmin endpoint fails here until it is classified.
    """
    views = app.view_functions
    auth_surface = {
        endpoint
        for endpoint, view in views.items()
        if endpoint.startswith("sysadmin.")
        and tlcp.classify_surface("sysadmin", view) == tlcp.SURFACE_SYSADMIN_AUTHENTICATION
    }
    assert auth_surface == {
        "sysadmin.login",
        "sysadmin.logout",
        "sysadmin.passkey_auth_start",
        "sysadmin.passkey_auth_finish",
        "sysadmin.grafana_auth_check",
    }
    assert tlcp.classify_surface(
        "sysadmin", views["sysadmin.dashboard"]
    ) == tlcp.SURFACE_SYSADMIN_CONSOLE
    assert tlcp.classify_surface(
        "student", views["student.dashboard"]
    ) == tlcp.SURFACE_APPLICATION


# -------------------- the real violation --------------------


def _sysadmin_with_session_class_id(client, app, key):
    classroom = initialize(key, app)
    sysadmin = create_sysadmin(f"tlcp_{key}")
    seed_sysadmin_session(client, user_id=sysadmin.id, username=f"tlcp_{key}")
    with client.session_transaction() as sess:
        sess["role"] = "sysadmin"
        sess["class_id"] = classroom.class_id  # the leak under test
    return classroom, sysadmin


@pytest.mark.parametrize(
    "path, surface",
    [
        ("/sysadmin/dashboard", "sysadmin_console"),
        ("/sysadmin/login", "sysadmin_authentication"),
        ("/student/dashboard", "application"),
        ("/health", "application"),
    ],
)
def test_INV_CORE_000__sysadmin_principal_with_class_context_is_a_violation_on_any_surface(
    client, app, caplog, path, surface,
):
    classroom, _ = _sysadmin_with_session_class_id(client, app, "chemistry_p1")

    with _capture(caplog):
        client.get(path)

    violations = _records(caplog, VIOLATION)
    assert violations, path
    line = violations[0]
    assert line.levelno == logging.ERROR
    assert line.error_class == "InvariantViolation"
    assert line.actor_type == "sysadmin"
    assert line.class_id == classroom.class_id
    assert "sysadmin principal carries canonical class context" in line.getMessage()
    assert f"surface={surface}" in line.getMessage()
    assert _records(caplog, MISMATCH) == []


def test_INV_CORE_000__persisted_class_pointer_on_a_sysadmin_is_a_violation(client, app, caplog):
    """The users row is the other carrier of class context (DOM-IDEN-006 §VIII)."""
    classroom = initialize("chemistry_p1", app)
    sysadmin = create_sysadmin("tlcp_pointer")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="tlcp:sysadmin-class-pointer"):
        db.session.get(User, sysadmin.id).last_active_class_id = classroom.class_id
        db.session.flush()
    seed_sysadmin_session(client, user_id=sysadmin.id, username="tlcp_pointer")

    with _capture(caplog):
        client.get("/sysadmin/dashboard")

    (line,) = _records(caplog, VIOLATION)
    assert line.levelno == logging.ERROR
    assert line.class_id == classroom.class_id


def test_INV_CORE_000__sysadmin_without_class_context_records_nothing(client, app, caplog):
    sysadmin = create_sysadmin("tlcp_clean")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="tlcp_clean")

    with _capture(caplog):
        assert client.get("/sysadmin/dashboard").status_code == 200

    assert _records(caplog, VIOLATION) == []
    assert _records(caplog, MISMATCH) == []


# -------------------- the predicate, pure --------------------


@pytest.mark.parametrize(
    "surface, principal, class_context, verdict",
    [
        ("sysadmin_authentication", "student", True, "surface_principal_mismatch"),
        ("sysadmin_authentication", "teacher", False, "surface_principal_mismatch"),
        ("sysadmin_console", "student", True, "surface_principal_mismatch"),
        ("sysadmin_authentication", "anonymous", False, None),
        ("sysadmin_console", "sysadmin", False, None),
        ("application", "student", True, None),
        ("application", "teacher", True, None),
        ("application", "sysadmin", False, None),
        ("application", "sysadmin", True, "invariant_violation"),
        ("sysadmin_console", "sysadmin", True, "invariant_violation"),
        ("sysadmin_authentication", "sysadmin", True, "invariant_violation"),
    ],
)
def test_INV_ARC_019__classify_request_uses_both_dimensions(surface, principal, class_context, verdict):
    assert tlcp.classify_request(
        surface=surface, principal=principal, class_context_present=class_context,
    ) == verdict


@pytest.mark.parametrize(
    "surface, endpoint, method, status, after, outcome",
    [
        ("sysadmin_authentication", "sysadmin.login", "GET", 200, "student", "SUCCESS"),
        ("sysadmin_authentication", "sysadmin.login", "POST", 302, "student", "EXPECTED_DENIAL"),
        ("sysadmin_authentication", "sysadmin.login", "POST", 302, "sysadmin", "SUCCESS"),
        ("sysadmin_authentication", "sysadmin.passkey_auth_finish", "POST", 401, "teacher", "EXPECTED_DENIAL"),
        ("sysadmin_authentication", "sysadmin.passkey_auth_start", "POST", 401, "teacher", "EXPECTED_DENIAL"),
        ("sysadmin_authentication", "sysadmin.passkey_auth_start", "POST", 200, "teacher", "SUCCESS"),
        ("sysadmin_authentication", "sysadmin.grafana_auth_check", "GET", 401, "student", "EXPECTED_DENIAL"),
        # Logout completes for any principal.
        ("sysadmin_authentication", "sysadmin.logout", "POST", 302, "anonymous", "SUCCESS"),
        ("sysadmin_console", "sysadmin.dashboard", "GET", 302, "student", "EXPECTED_DENIAL"),
        ("sysadmin_authentication", "sysadmin.login", "POST", 500, "student", "SYSTEM_FAILURE"),
    ],
)
def test_SPEC_OPS_003__classify_outcome_uses_the_closed_vocabulary(surface, endpoint, method, status, after, outcome):
    assert tlcp.classify_outcome(
        surface=surface, endpoint=endpoint, method=method, status_code=status, principal_after=after,
    ) == outcome
    assert outcome in {tlcp.OUTCOME_SUCCESS, tlcp.OUTCOME_EXPECTED_DENIAL, tlcp.OUTCOME_SYSTEM_FAILURE}


def test_SPEC_OPS_003__student_at_sysadmin_logout_is_a_successful_mismatch(client, app, caplog):
    """POST /sysadmin/logout completes for any principal, so it is not a denial."""
    initialize_as_student("chemistry_p1", client, app)
    with _capture(caplog):
        response = client.post("/sysadmin/logout")

    assert response.status_code == 302
    assert _records(caplog, VIOLATION) == []
    (line,) = _records(caplog, MISMATCH)
    assert line.tlcp_surface == "sysadmin_authentication"
    assert line.tlcp_principal == "student"
    assert line.tlcp_outcome == "SUCCESS"


# -------------------- a revoked cookie is not a principal --------------------
#
# validate_canonical_session_nonce must run before capture_correlation_context:
# a superseded cookie names no principal for this request.


def _revoke(client):
    with client.session_transaction() as sess:
        sess["current_session_nonce"] = "superseded-by-a-later-sign-in"


def test_INV_CORE_000__revoked_sysadmin_cookie_with_class_id_is_not_a_violation(client, app, caplog):
    classroom, _ = _sysadmin_with_session_class_id(client, app, "chemistry_p1")
    _revoke(client)

    with _capture(caplog):
        client.get("/sysadmin/dashboard")

    assert _records(caplog, VIOLATION) == []
    assert _records(caplog, MISMATCH) == []
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_INV_ARC_019__revoked_student_cookie_at_sysadmin_login_records_no_mismatch(client, app, caplog):
    initialize_as_student("chemistry_p1", client, app)
    _revoke(client)

    with _capture(caplog):
        assert client.get("/sysadmin/login").status_code == 200

    assert _records(caplog, MISMATCH) == []
    assert _records(caplog, VIOLATION) == []


def test_INV_CORE_000__valid_sysadmin_cookie_with_class_id_is_still_a_violation(client, app, caplog):
    """The control for the two tests above: the same session, nonce intact."""
    classroom, _ = _sysadmin_with_session_class_id(client, app, "chemistry_p1")

    with _capture(caplog):
        client.get("/sysadmin/dashboard")

    (line,) = _records(caplog, VIOLATION)
    assert line.levelno == logging.ERROR
    assert line.class_id == classroom.class_id


def test_SPEC_OPS_003__student_get_at_sysadmin_logout_is_refused_and_keeps_the_sign_in(client, app, caplog):
    """GET /sysadmin/logout is 405: it reaches no view, ends no sign-in, records no mismatch."""
    initialize_as_student("chemistry_p1", client, app)
    before = _identity(client)
    with _capture(caplog):
        response = client.get("/sysadmin/logout")

    assert response.status_code == 405
    assert _identity(client) == before
    assert _records(caplog, VIOLATION) == []
    assert _records(caplog, MISMATCH) == []


def test_SPEC_OPS_003__student_logout_without_csrf_token_is_refused_before_correlation(
    client, app, caplog, monkeypatch,
):
    """Flask-WTF refuses a tokenless POST (400) before TLCP captures the request:
    the sign-in is kept and nothing is recorded, as for a GET."""
    initialize_as_student("chemistry_p1", client, app)
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    before = _identity(client)
    with _capture(caplog):
        response = client.post("/sysadmin/logout")

    assert response.status_code == 400
    assert _identity(client) == before
    assert _records(caplog, VIOLATION) == []
    assert _records(caplog, MISMATCH) == []
