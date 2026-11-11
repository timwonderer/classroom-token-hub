"""Signed-in student routes are rate limited per seat, not per network address.

Issue #1642: only ``/api/tap`` and ``/api/student-status`` carried an explicit
seat-keyed limit (see ``tests/test_student_status_rate_limit.py``). Every
other ``@login_required`` route -- the dashboard, transfers, insurance,
shop, rent, and the hall-pass endpoints -- had no route-level decorator, so
it fell back to the application's ``default_limits``, which are keyed by
client address. A school's students share a small pool of public addresses,
so one student's traffic could exhaust that shared 200/hour budget for every
classmate behind the same address.

Those routes now carry an explicit ``@limiter.limit(..., key_func=student_seat_limit_key)``
below ``@login_required``, the same pattern ``attendance_tap_seat_limit_key``
and ``student_status_seat_limit_key`` already used. This file proves the
re-keying for one read-only page route (``/student/dashboard``), one
money-moving route (``/student/transfer``), one ``/api`` hall-pass route
(``/api/hall-pass/checkout``), and the ``student_seat_limit_key`` function
itself -- and proves ``/student/logout`` was deliberately left exempt rather
than silently uncovered.
"""

from __future__ import annotations

import time as _time

import limits.storage.memory
import pytest
from flask import g

import wsgi  # noqa: F401 -- registers the 429 handler on import
from app.extensions import limiter
from tests.helpers.canonical_classroom import login_student
from tests.helpers.classroom_initializer import initialize

SCHOOL_ADDRESS = {"CF-Connecting-IP": "203.0.113.9"}  # RFC 5737 documentation range
DASHBOARD_LIMIT_PER_MINUTE = 120
TRANSFER_LIMIT_PER_MINUTE = 30
HALL_PASS_LIMIT_PER_MINUTE = 30


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


def test_dashboard_exhausting_one_seat_does_not_throttle_a_classmate(client, app, limiter_on, clock):
    """Keyed by address, the classmate behind the same address would be refused too."""
    _, first, second = _two_students_one_class(client, app)

    within = [
        first.get("/student/dashboard", headers=SCHOOL_ADDRESS).status_code
        for _ in range(DASHBOARD_LIMIT_PER_MINUTE)
    ]
    over = first.get("/student/dashboard", headers=SCHOOL_ADDRESS)
    classmate = second.get("/student/dashboard", headers=SCHOOL_ADDRESS)

    assert set(within) == {200}
    assert over.status_code == 429
    assert classmate.status_code == 200

    clock.advance(61)
    assert first.get("/student/dashboard", headers=SCHOOL_ADDRESS).status_code == 200


def test_transfer_get_is_seat_keyed_not_address_keyed(client, app, limiter_on, clock):
    """``/student/transfer`` carries money-moving state; its budget is the tighter 30/min tier."""
    _, first, second = _two_students_one_class(client, app)

    within = [
        first.get("/student/transfer", headers=SCHOOL_ADDRESS).status_code
        for _ in range(TRANSFER_LIMIT_PER_MINUTE)
    ]
    over = first.get("/student/transfer", headers=SCHOOL_ADDRESS)
    classmate = second.get("/student/transfer", headers=SCHOOL_ADDRESS)

    assert set(within) == {200}
    assert over.status_code == 429
    assert classmate.status_code == 200


def test_hall_pass_checkout_api_route_is_seat_keyed(client, app, limiter_on, clock):
    """``/api/hall-pass/checkout`` is a non-admin, non-tap ``/api`` route the issue named."""
    _, first, second = _two_students_one_class(client, app)

    # The route validates its own payload before the budget runs out; a
    # malformed/empty body (400/404/etc.) still spends the same seat key,
    # which is all this test needs to prove.
    within = [
        first.post("/api/hall-pass/checkout", json={}, headers=SCHOOL_ADDRESS).status_code
        for _ in range(HALL_PASS_LIMIT_PER_MINUTE)
    ]
    over = first.post("/api/hall-pass/checkout", json={}, headers=SCHOOL_ADDRESS)
    classmate = second.post("/api/hall-pass/checkout", json={}, headers=SCHOOL_ADDRESS)

    assert all(code != 429 for code in within)
    assert over.status_code == 429
    assert classmate.status_code != 429


def test_unauthenticated_dashboard_request_spends_no_seat_budget(client, app, limiter_on, clock):
    """``login_required`` redirects before the limiter's key func ever runs."""
    _, first, _ = _two_students_one_class(client, app)
    anonymous = app.test_client()

    for _ in range(DASHBOARD_LIMIT_PER_MINUTE * 2):
        response = anonymous.get("/student/dashboard", headers=SCHOOL_ADDRESS)
        assert response.status_code in (302, 401)

    assert set(
        first.get("/student/dashboard", headers=SCHOOL_ADDRESS).status_code
        for _ in range(DASHBOARD_LIMIT_PER_MINUTE)
    ) == {200}


def test_logout_is_exempt_rather_than_silently_uncovered(client, app, limiter_on, clock):
    """Logout was deliberately decided ``exempt``, not accidentally missed.

    Mutation proof: hammer ``/student/logout`` itself past the address-keyed
    ``200 per hour`` default from an anonymous caller sharing the signed-in
    student's address, then confirm that student can still log out. Without
    ``@limiter.exempt`` the anonymous traffic would spend the same address
    budget and the student's own logout call would 429 too.
    """
    _, first, _ = _two_students_one_class(client, app)
    anonymous = app.test_client()

    for _ in range(205):
        anonymous.get("/student/logout", headers=SCHOOL_ADDRESS)

    assert first.get("/student/logout", headers=SCHOOL_ADDRESS).status_code in (200, 302)


def test_student_seat_limit_key_reads_only_the_validated_context(app, monkeypatch):
    """Mirrors the mutation proof for ``student_status_seat_limit_key``.

    The key must read ``g.canonical_context`` as ``login_required`` left it
    and never resolve identity itself (DOM-IDEN-006 §IX).
    """
    import app.services.context_resolver as context_resolver
    from app.extensions import student_seat_limit_key
    from app.services.context_resolver import BoundaryContext, CanonicalContext

    def _must_not_resolve(*args, **kwargs):
        raise AssertionError("the limit key must not resolve canonical context")

    monkeypatch.setattr(context_resolver, "resolve_canonical_context", _must_not_resolve)

    with app.test_request_context(
        "/student/dashboard", headers=SCHOOL_ADDRESS, environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        g.canonical_context = CanonicalContext(
            user_id="u-1", class_id="class-a", seat_id=7, actor_role="student"
        )
        assert student_seat_limit_key() == "seat:class-a:7"

        g.canonical_context = BoundaryContext(user_id="u-1", actor_role="teacher")
        assert student_seat_limit_key() == "ip:203.0.113.9"

        g.canonical_context = None
        assert student_seat_limit_key() == "ip:203.0.113.9"
