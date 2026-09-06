"""The session cookie must not outlive the session it represents.

Three authoritative session lifetimes already existed in app/auth.py before this
suite: a student's hard cap from login (`User.current_session_expires_at`), a
teacher's 10-minute idle limit, and a sysadmin's 60-minute idle limit. All three
are enforced server-side, which means they only fire when a request arrives.

Nothing bounded the *cookie*. `PERMANENT_SESSION_LIFETIME` is unset, so it was
Flask's 31-day default, and a student who closed the tab left a cookie on the
device for a month -- carrying the `display_metadata` cache, which holds
decrypted first and last names for the student and their teacher.

These tests pin the cookie's own expiry against those pre-existing rules. They
also pin the deliberate *absence* of a fourth rule: an unauthenticated session
falls through to the Flask default on purpose, because the two PII-bearing
session keys are written only after authentication, so the pre-login window is
not a PII-retention control and shortening it would only break login forms whose
CSRF token outlived their cookie.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.auth import SESSION_TIMEOUT_MINUTES, SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES
from app.session_lifetime import (
    SESSION_EXPIRES_AT_KEY,
    RoleScopedSessionInterface,
)


class _FakeSession(dict):
    """Minimal stand-in for a Flask session (a dict plus `.permanent`)."""

    def __init__(self, *, permanent=True, **values):
        super().__init__(**values)
        self.permanent = permanent


def _expiry(app, **session_values):
    return RoleScopedSessionInterface().get_expiration_time(
        app, _FakeSession(**session_values)
    )


def test_non_permanent_session_gets_no_expiry(app):
    """A browser-lifetime session must stay a browser-lifetime session."""
    assert _expiry(app, permanent=False, role="student") is None


def test_student_cookie_expires_with_the_users_table_row(app):
    """The student cookie mirrors `User.current_session_expires_at` exactly.

    Not "approximately" and not "within 10 minutes of" -- the same instant, so
    the browser evicts the cookie when login_required stops honoring it.
    """
    authoritative = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    got = _expiry(
        app,
        role="student",
        **{SESSION_EXPIRES_AT_KEY: authoritative.isoformat()},
    )
    assert got == authoritative


def test_student_cookie_expiry_does_not_slide(app):
    """The student rule is a hard cap from login, not an idle timeout.

    A stamped expiry must be returned verbatim on every save. If it were
    recomputed as now+10min the cookie would renew forever while the student
    kept clicking, outliving the hard cap it is supposed to mirror.
    """
    authoritative = datetime.now(timezone.utc) + timedelta(minutes=3)
    stamp = {SESSION_EXPIRES_AT_KEY: authoritative.isoformat()}

    first = _expiry(app, role="student", **stamp)
    second = _expiry(app, role="student", **stamp)

    assert first == second == authoritative


@pytest.mark.parametrize(
    "role,minutes",
    [
        ("admin", SESSION_TIMEOUT_MINUTES),
        ("sysadmin", SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES),
    ],
)
def test_idle_roles_track_their_own_authoritative_limit(app, role, minutes):
    """Teacher and sysadmin cookies match the idle limits in app/auth.py.

    Parametrized against the constants rather than literals: if someone changes
    SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES, the cookie must follow rather than
    silently keep a stale number.
    """
    before = datetime.now(timezone.utc)
    got = _expiry(app, role=role)
    after = datetime.now(timezone.utc)

    assert before + timedelta(minutes=minutes) <= got <= after + timedelta(minutes=minutes)


def test_sysadmin_is_not_truncated_to_the_student_limit(app):
    """Guards the regression a single global lifetime would have caused.

    Setting PERMANENT_SESSION_LIFETIME to 10 minutes would have silently cut
    sysadmin sessions from 60 to 10. This fails if the roles are ever collapsed.
    """
    sysadmin = _expiry(app, role="sysadmin")
    student_window = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    assert sysadmin > student_window


def test_unauthenticated_session_keeps_the_flask_default(app):
    """A role-less session deliberately falls through, and must keep doing so.

    This is the load-bearing negative: a pre-login session holds a CSRF token,
    not PII. If a future change shortens this on PII grounds, it breaks login
    forms to protect data that is not there. See app/session_lifetime.py.
    """
    got = _expiry(app)
    expected = datetime.now(timezone.utc) + app.config["PERMANENT_SESSION_LIFETIME"]
    assert abs((got - expected).total_seconds()) < 5


def test_malformed_stamp_falls_back_instead_of_raising(app):
    """A cookie from an older deploy must not 500 the response on save."""
    got = _expiry(app, role="student", **{SESSION_EXPIRES_AT_KEY: "not-a-timestamp"})
    expected = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    assert abs((got - expected).total_seconds()) < 5


def test_naive_stamp_is_treated_as_utc(app):
    """Postgres can hand back a naive datetime; comparing it naively would raise."""
    naive = (datetime.now(timezone.utc) + timedelta(minutes=7)).replace(tzinfo=None)
    got = _expiry(app, role="student", **{SESSION_EXPIRES_AT_KEY: naive.isoformat()})
    assert got.tzinfo is not None
    assert got == naive.replace(tzinfo=timezone.utc)


def _set_cookie_expiry(response):
    """Parse the Expires attribute off the session Set-Cookie header."""
    from email.utils import parsedate_to_datetime

    for header in response.headers.getlist("Set-Cookie"):
        if not header.startswith("session="):
            continue
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name.lower() == "expires":
                return parsedate_to_datetime(value)
    raise AssertionError("no session cookie with an Expires attribute was issued")


def test_interface_is_actually_installed_on_the_app(app, client):
    """End-to-end: the real Set-Cookie header must carry the role-scoped expiry.

    The unit tests above drive RoleScopedSessionInterface directly, so they pass
    whether or not it is wired into create_app. This one fails if it is not:
    without the interface the header would carry Flask's 31-day default.
    """
    with client.session_transaction() as sess:
        sess["role"] = "sysadmin"
        sess.permanent = True

    expires = _set_cookie_expiry(client.get("/"))

    expected = datetime.now(timezone.utc) + timedelta(
        minutes=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES
    )
    assert abs((expires - expected).total_seconds()) < 60, (
        f"cookie expires at {expires}, expected ~{expected}; "
        "RoleScopedSessionInterface is probably not installed"
    )
    # And explicitly not the default it used to be.
    assert expires < datetime.now(timezone.utc) + timedelta(days=1)


def test_permanent_session_lifetime_is_left_at_the_flask_default(app):
    """Pins the decision *not* to change it.

    The investigated PII-bearing session keys -- display_metadata and
    teacher_display_name_cache -- are populated only after canonical
    authenticated context exists. The generic permanent-session default
    therefore holds no PII and is not a retention control. This test exists so
    that rediscovering the 31-day default does not lead to "fixing" it for a
    reason that was already checked and rejected.
    """
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(days=31)
