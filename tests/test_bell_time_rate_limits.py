"""Audit O1: bell-time rate limits must not be pooled across one network address.

Students at a school leave through a small pool of shared public addresses.
Two routes carried only an address-keyed limit, which meant that pool was
shared budget rather than a per-student one:

- ``/api/tap`` counted every POST from an address together, so one busy seat
  (or several, at bell time) could exhaust the limit for every classmate
  behind the same address.
- ``/student/login`` counted GET page loads and POST attempts together
  against one address-wide ``60 per minute``: 30 page loads plus 30 attempts
  exhausted the whole school's budget at the 61st request, and a shared NAT
  meant that budget was shared by every student in the building, not one.

The fix keys ``/api/tap`` on ``(class_id, seat_id)`` once a canonical context
is attached (the same pattern as ``/api/student-status``, audited and fixed
separately), and splits student login into an address-keyed limit scoped to
POST only (so GETs no longer spend it) plus a second limit keyed on the
submitted username, which is what actually bounds repeated guessing against
one account regardless of how many classmates share the address.

The limiter is enabled explicitly here, as in test_student_status_rate_limit.py,
so these exercise the real routes, decorator order and key functions.
"""

from __future__ import annotations

import time as _time

import limits.storage.memory
import pytest
from flask import g

import wsgi  # noqa: F401 -- registers the 429 handler on import
from app.extensions import (
    attendance_tap_seat_limit_key,
    limiter,
    student_login_identity_limit_key,
)
from tests.helpers.canonical_classroom import login_student
from tests.helpers.classroom_initializer import initialize

SCHOOL_ADDRESS = {"CF-Connecting-IP": "203.0.113.9"}  # RFC 5737 documentation range
TAP_LIMIT_PER_MINUTE = 100
LOGIN_IDENTITY_LIMIT_PER_MINUTE = 10


class _Clock:
    """Stands in for the ``time`` module inside the limiter's memory storage."""

    def __init__(self):
        self.now = _time.time()

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(limits.storage.memory, "time", fake)
    return fake


@pytest.fixture
def limiter_on(app):
    was_enabled = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = was_enabled


def _two_students_one_class(client, app):
    """Two logged-in students in one class, each on their own browser."""
    classroom = initialize("chemistry_p1", app)
    first, second = classroom.students[0], classroom.students[1]
    other_browser = app.test_client()
    login_student(client, first)
    login_student(other_browser, second)
    return classroom, client, other_browser


def _tap(browser):
    return browser.post("/api/tap", json={"action": "start_work"}, headers=SCHOOL_ADDRESS)


def _login_attempt(browser, username, passphrase="wrong-passphrase"):
    return browser.post(
        "/student/login",
        data={"username": username, "passphrase": passphrase},
        headers=SCHOOL_ADDRESS,
    )


# -------------------- /api/tap --------------------


def test_one_seats_tap_budget_does_not_throttle_its_classmate(client, app, limiter_on, clock):
    """The limit belongs to the seat: exhausting it refuses that seat only.

    Mutation proof for the key: keyed by client address, the classmate behind
    the same address would be refused too.
    """
    _, first, second = _two_students_one_class(client, app)

    # No PIN is supplied, so each tap is refused for an invalid PIN (403) --
    # that refusal happens inside the view, after the rate limiter has already
    # let the request through, so it is a faithful probe of the limit itself.
    within = [_tap(first).status_code for _ in range(TAP_LIMIT_PER_MINUTE)]
    over = _tap(first)
    classmate = _tap(second)

    assert set(within) == {403}
    assert over.status_code == 429
    assert classmate.status_code == 403

    clock.advance(61)
    assert _tap(first).status_code == 403


def test_unauthenticated_taps_still_fall_back_to_the_address_key(client, app, limiter_on, clock):
    """No canonical context -- the existing address-wide protection still applies."""
    anonymous = app.test_client()

    statuses = [
        anonymous.post("/api/tap", json={}, headers=SCHOOL_ADDRESS).status_code
        for _ in range(TAP_LIMIT_PER_MINUTE + 1)
    ]
    assert statuses[-1] == 429
    assert all(code == 401 for code in statuses[:-1])


def test_tap_key_reads_the_context_already_on_g_without_resolving_again(app, monkeypatch):
    """The key reads g.canonical_context and never calls the resolver itself.

    /api/tap carries no @login_required; the context on g was attached by the
    app-wide before_request hook (capture_correlation_context), which always
    runs before this decorator's key func.
    """
    import app.services.context_resolver as context_resolver
    from app.services.context_resolver import BoundaryContext, CanonicalContext

    def _must_not_resolve(*args, **kwargs):
        raise AssertionError("the limit key must not resolve canonical context")

    monkeypatch.setattr(context_resolver, "resolve_canonical_context", _must_not_resolve)

    with app.test_request_context(
        "/api/tap", headers=SCHOOL_ADDRESS, environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        g.canonical_context = CanonicalContext(
            user_id="u-1", class_id="class-a", seat_id=41, actor_role="student"
        )
        assert attendance_tap_seat_limit_key() == "seat:class-a:41"

        g.canonical_context = BoundaryContext(user_id="u-1", actor_role="teacher")
        assert attendance_tap_seat_limit_key() == "ip:203.0.113.9"

        g.canonical_context = None
        assert attendance_tap_seat_limit_key() == "ip:203.0.113.9"


# -------------------- /student/login --------------------


def test_one_students_failed_login_attempts_do_not_block_a_classmate(client, app, limiter_on, clock):
    """Two students behind one address: one wrong-password streak hits only them.

    Mutation proof for the key: keyed by address alone, the classmate's own
    (correct) login would be refused too, since the address-wide POST limit
    (60/min) is wider than the per-identity one (10/min) but both apply.
    """
    classroom = initialize("chemistry_p1", app)
    first, second = classroom.students[0], classroom.students[1]
    other_browser = app.test_client()

    within = [
        _login_attempt(client, first.username).status_code
        for _ in range(LOGIN_IDENTITY_LIMIT_PER_MINUTE)
    ]
    over = _login_attempt(client, first.username)

    assert set(within) == {302}  # bad credentials -> flash + redirect, not 429
    assert over.status_code == 429

    classmate = other_browser.post(
        "/student/login",
        data={"username": second.username, "passphrase": second.passphrase},
        headers=SCHOOL_ADDRESS,
        follow_redirects=True,
    )
    assert classmate.status_code == 200
    assert b"Logged in as" in classmate.data or classmate.request.path != "/student/login"


def test_login_GET_requests_do_not_spend_the_post_limit(client, app, limiter_on, clock):
    """Audit O1's literal example: GET page loads must not share the POST budget."""
    for _ in range(80):
        response = client.get("/student/login", headers=SCHOOL_ADDRESS)
        assert response.status_code == 200

    # A single POST attempt right after 80 GETs must not already be refused.
    response = _login_attempt(client, "someone-not-in-the-roster")
    assert response.status_code != 429


def test_login_identity_key_hashes_the_username_not_plaintext(app, monkeypatch):
    """The key must never place a raw username into the limiter's storage."""
    from app.hash_utils import hash_username_lookup

    with app.test_request_context(
        "/student/login",
        method="POST",
        data={"username": "ana.lopez"},
        headers=SCHOOL_ADDRESS,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        key = student_login_identity_limit_key()
        assert key == f"login-identity:{hash_username_lookup('ana.lopez')}"
        assert "ana.lopez" not in key

    with app.test_request_context(
        "/student/login", method="GET", headers=SCHOOL_ADDRESS,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert student_login_identity_limit_key() == "ip:203.0.113.9"
