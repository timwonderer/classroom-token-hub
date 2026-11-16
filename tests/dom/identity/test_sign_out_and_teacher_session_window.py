"""Sign-in and sign-out follow the identity and GET-purity documents (#1635, #1636).

- INV-ARC-007 §V: a GET changes no session. Opening ``/admin/login`` used to
  sign a teacher out, and ``GET /admin/logout`` / ``GET /student/logout`` ended
  the session. Both logouts are now POST-only, CSRF-checked.
- DOM-IDEN-002/003 §Session Establishment: the sign-in lives on the ``users``
  row (``current_session_nonce``). Logout used to delete only the cookie, so a
  copy of it kept working. Logout now voids the row's sign-in.
- DOM-IDEN-006 §IX: signing out is not class-scoped, so a student with no
  active class can do it.
- DOM-IDEN-003: a teacher session is a fixed 60-minute window from sign-in,
  not a 10-minute idle timeout that an active teacher never reaches.
"""
from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, User
from tests.helpers import temporal
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.operation_routes import seed_sysadmin_session
from tests.dom.interpretation.helpers import create_sysadmin
from tests.test_login_hardening_s5 import _create_teacher


@pytest.fixture
def csrf_enabled(app, monkeypatch):
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)


def _session(client):
    """The session minus the CSRF token, which rendering any form may mint and which names nobody."""
    with client.session_transaction() as sess:
        return {k: v for k, v in sess.items() if k != "csrf_token"}


def _replay(client, snapshot):
    """Put a copied pre-logout cookie back in the browser."""
    with client.session_transaction() as sess:
        sess.clear()
        sess.update(snapshot)


def _row(user_id):
    db.session.expire_all()
    return db.session.get(User, user_id)


# ------------------------------------------------------------ GET is pure

@pytest.mark.parametrize("path", ["/admin/logout", "/student/logout"])
def test_INV_ARC_007__get_logout_is_refused_and_keeps_the_session(client, app, path):
    if path.startswith("/admin"):
        initialize_as_teacher("chemistry_p1", client, app)
    else:
        initialize_as_student("chemistry_p1", client, app)
    before = _session(client)

    assert client.get(path).status_code == 405
    assert _session(client) == before


def test_INV_ARC_007__opening_the_teacher_login_page_signs_nobody_out(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    before = _session(client)

    assert client.get("/admin/login").status_code == 200

    assert _session(client) == before
    assert client.get("/admin/").status_code == 200


@pytest.mark.parametrize("path", ["/admin/logout", "/student/logout"])
def test_logout_post_without_csrf_token_is_refused(client, app, csrf_enabled, path):
    if path.startswith("/admin"):
        initialize_as_teacher("chemistry_p1", client, app)
    else:
        initialize_as_student("chemistry_p1", client, app)
    before = _session(client)

    assert client.post(path).status_code == 400
    assert _session(client) == before


# ------------------------------------------- logout voids the server sign-in

def test_DOM_IDEN_003__teacher_logout_voids_the_sign_in_and_a_copied_cookie_is_refused(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    copied = _session(client)

    assert client.post("/admin/logout").status_code == 302

    teacher = _row(classroom.teacher_user_id)
    assert teacher.current_session_nonce is None
    assert teacher.current_session_expires_at is None
    _replay(client, copied)
    response = client.get("/admin/")
    assert response.status_code == 302 and "/admin/login" in response.location


def test_DOM_IDEN_002__student_logout_voids_the_sign_in_and_a_copied_cookie_is_refused(client, app):
    _, student = initialize_as_student("chemistry_p1", client, app)
    copied = _session(client)

    assert client.post("/student/logout").status_code == 302

    assert _row(student.user.id).current_session_nonce is None
    _replay(client, copied)
    response = client.get("/student/dashboard")
    assert response.status_code == 302 and "/student/login" in response.location


def test_sysadmin_logout_voids_the_sign_in_and_a_copied_cookie_is_refused(client, app):
    sysadmin = create_sysadmin("logout_voids_sign_in")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="logout_voids_sign_in")
    db.session.commit()
    copied = _session(client)

    assert client.post("/sysadmin/logout").status_code == 302

    assert _row(sysadmin.id).current_session_nonce is None
    _replay(client, copied)
    response = client.get("/sysadmin/dashboard")
    assert response.status_code == 302 and "/sysadmin/login" in response.location


def test_stale_cookie_logout_does_not_end_a_newer_sign_in(client, app):
    """Only the sign-in the cookie holds is voided; a newer one elsewhere survives."""
    _, student = initialize_as_student("chemistry_p1", client, app)
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:newer-sign-in"):
        db.session.get(User, student.user.id).current_session_nonce = "newer-sign-in-elsewhere"
        db.session.flush()
    db.session.commit()

    client.post("/student/logout")

    assert _row(student.user.id).current_session_nonce == "newer-sign-in-elsewhere"


def test_DOM_IDEN_006__student_with_no_active_class_can_sign_out(client, app):
    _, student = initialize_as_student("chemistry_p1", client, app)
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:no-active-class"):
        user = db.session.get(User, student.user.id)
        user.last_active_class_id = None
        user.last_active_seat_id = None
        db.session.flush()
    db.session.commit()
    assert "select-class" in client.get("/student/dashboard").location

    response = client.post("/student/logout")

    assert response.status_code == 302 and response.location.split("?")[0].endswith("/student/login")
    assert "user_id" not in _session(client)
    assert _row(student.user.id).current_session_nonce is None


# ------------------------------------------- teacher fixed 60-minute window

def _sign_in_teacher(client, monkeypatch, username):
    teacher, secret = _create_teacher(username)
    monkeypatch.setattr("app.routes.admin.verify_turnstile_token", lambda *a, **k: True)
    response = client.post("/admin/login", data={"username": username, "totp_code": pyotp.TOTP(secret).now()})
    assert response.status_code == 302
    return teacher


def test_DOM_IDEN_003__teacher_sign_in_writes_a_fixed_60_minute_window(client, app, monkeypatch):
    start = temporal.now()
    with temporal.pinned_clock(start):
        teacher = _sign_in_teacher(client, monkeypatch, "window_written")

    row = _row(teacher.id)
    assert row.current_session_started_at == start
    assert row.current_session_expires_at == temporal.shifted(start, minutes=60)
    # The cookie dies with the server-side window.
    assert datetime.fromisoformat(_session(client)["session_expires_at"]) == row.current_session_expires_at


def test_DOM_IDEN_003__teacher_active_for_61_minutes_is_signed_out(client, app, monkeypatch):
    start = temporal.now()
    with temporal.pinned_clock(start):
        _sign_in_teacher(client, monkeypatch, "active_61")
    for minute in (10, 20, 30, 40, 50, 59):
        with temporal.pinned_clock(temporal.shifted(start, minutes=minute)):
            assert client.get("/admin/create-class").status_code == 200, minute

    with temporal.pinned_clock(temporal.shifted(start, minutes=61)):
        response = client.get("/admin/create-class")

    assert response.status_code == 302 and "/admin/login" in response.location


def test_DOM_IDEN_003__teacher_idle_for_11_minutes_is_not_signed_out(client, app, monkeypatch):
    start = temporal.now()
    with temporal.pinned_clock(start):
        _sign_in_teacher(client, monkeypatch, "idle_11")

    with temporal.pinned_clock(temporal.shifted(start, minutes=11)):
        assert client.get("/admin/create-class").status_code == 200


def test_DOM_IDEN_003__creating_a_class_does_not_restart_the_window(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    expires_before = _row(classroom.teacher_user_id).current_session_expires_at

    client.post("/admin/create-class", data={
        "class_display_name": "Window Check", "section": "P9", "class_timezone": "America/Los_Angeles",
        "first_name": "Win", "last_name": "Dow",
    })

    assert ClassEconomy.query.filter_by(teacher_user_id=classroom.teacher_user_id, display_name="Window Check").count() == 1
    assert _row(classroom.teacher_user_id).current_session_expires_at == expires_before
