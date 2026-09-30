"""``/api/student-status`` is limited per seat, not per network address.

The student dashboard polls this endpoint every 10 seconds (360 an hour per
open tab). It used to carry only the application-wide default limits, which
are keyed by client address: ``200 per hour`` let one student exhaust the
budget in about 33 minutes, and in production the school's students share a
small pool of public addresses, so one student's poller throttled everyone
else who happened to leave through the same address. 699 polls answered 429
in the first days after launch.

The poll is authenticated, class-scoped activity. Its limit is now keyed on
``(class_id, seat_id)`` from the canonical context ``login_required``
validated (DOM-IDEN-006 §VII, §IX), so the network a student sits behind
no longer decides whether their status refreshes.

The limiter is enabled explicitly here: the suite runs with it reset per
client, and these tests exercise the real route, decorator order and error
handler rather than the key function in isolation (except where noted).
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

SCHOOL_ADDRESS = {"CF-Connecting-IP": "203.0.113.7"}  # RFC 5737 documentation range
SEAT_LIMIT_PER_MINUTE = 30


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


def _poll(browser):
    return browser.get("/api/student-status", headers=SCHOOL_ADDRESS)


def test_a_shared_school_address_does_not_throttle_normal_polling(client, app, limiter_on, clock):
    """Twenty minutes of ordinary polling from two students behind one address.

    One student has the dashboard open in two tabs (12 polls a minute), the
    other in one (6 a minute): 360 polls from one address in twenty minutes.
    Keyed by address, the "200 per hour" default refused the 201st.
    """
    _, first, second = _two_students_one_class(client, app)

    statuses = []
    for _ in range(20 * 6):  # one round every 10 seconds for 20 minutes
        statuses.append(_poll(first).status_code)   # first tab
        statuses.append(_poll(first).status_code)   # second tab
        statuses.append(_poll(second).status_code)
        clock.advance(10)

    assert len(statuses) == 360
    assert set(statuses) == {200}


def test_one_seat_over_its_limit_does_not_throttle_its_classmate(client, app, limiter_on, clock):
    """The limit belongs to the seat: exhausting it refuses that seat only.

    Mutation proof for the key: keyed by client address, the classmate behind
    the same address would be refused too.
    """
    _, first, second = _two_students_one_class(client, app)

    within = [_poll(first).status_code for _ in range(SEAT_LIMIT_PER_MINUTE)]
    over = _poll(first)
    classmate = _poll(second)

    assert set(within) == {200}
    assert over.status_code == 429
    assert classmate.status_code == 200

    clock.advance(61)
    assert _poll(first).status_code == 200


def test_the_rate_limited_poll_is_answered_in_json_with_retry_after(client, app, limiter_on, clock):
    """attendance.js reads JSON; an HTML 429 page made its r.json() throw."""
    _, first, _ = _two_students_one_class(client, app)

    for _ in range(SEAT_LIMIT_PER_MINUTE):
        _poll(first)
    response = _poll(first)

    assert response.status_code == 429
    assert response.is_json
    body = response.get_json()
    assert body["status"] == "error"
    assert body["error"]
    retry_after = int(response.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_other_api_429s_are_json_and_page_429s_stay_html(client, app, limiter_on, clock):
    """The JSON answer covers /api/*; the styled page still serves everything else."""
    statuses = [
        client.post("/api/tap", json={}, headers=SCHOOL_ADDRESS).status_code for _ in range(101)
    ]
    assert statuses[-1] == 429
    api_response = client.post("/api/tap", json={}, headers=SCHOOL_ADDRESS)
    assert api_response.status_code == 429
    assert api_response.is_json

    for _ in range(6):
        page_response = client.post("/admin/recover", data={}, headers=SCHOOL_ADDRESS)
    assert page_response.status_code == 429
    assert page_response.mimetype == "text/html"
    assert "Too Many Requests" in page_response.get_data(as_text=True)


def test_unauthenticated_polls_get_401_and_spend_no_seat_budget(client, app, limiter_on, clock):
    """A caller with no session is refused by login_required before the limit.

    It gets the existing JSON 401 (which attendance.js turns into a login
    redirect), never a 429, and cannot spend a student's seat budget.
    """
    _, first, _ = _two_students_one_class(client, app)
    anonymous = app.test_client()

    for _ in range(SEAT_LIMIT_PER_MINUTE * 2):
        response = _poll(anonymous)
        assert response.status_code == 401
        assert response.get_json()["status"] == "error"

    assert set(_poll(first).status_code for _ in range(SEAT_LIMIT_PER_MINUTE)) == {200}


def test_seat_key_comes_from_the_validated_context_without_resolving_again(app, monkeypatch):
    """The key reads g.canonical_context, as login_required left it, and nothing else.

    Resolving here would be one more construction of the context in the same
    request (DOM-IDEN-006 §IX); the resolver is made to fail loudly to prove
    the key never calls it.
    """
    import app.services.context_resolver as context_resolver
    from app.extensions import student_status_seat_limit_key
    from app.services.context_resolver import BoundaryContext, CanonicalContext

    def _must_not_resolve(*args, **kwargs):
        raise AssertionError("the limit key must not resolve canonical context")

    monkeypatch.setattr(context_resolver, "resolve_canonical_context", _must_not_resolve)

    with app.test_request_context("/api/student-status", headers=SCHOOL_ADDRESS):
        g.canonical_context = CanonicalContext(
            user_id="u-1", class_id="class-a", seat_id=41, actor_role="student"
        )
        assert student_status_seat_limit_key() == "seat:class-a:41"

        g.canonical_context = BoundaryContext(user_id="u-1", actor_role="teacher")
        assert student_status_seat_limit_key() == "ip:203.0.113.7"

        g.canonical_context = None
        assert student_status_seat_limit_key() == "ip:203.0.113.7"

    with app.test_request_context("/api/student-status", environ_base={"REMOTE_ADDR": None}):
        g.canonical_context = None
        assert student_status_seat_limit_key()  # never empty: an empty key disables the limit
