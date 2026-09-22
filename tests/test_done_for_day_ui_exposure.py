"""``done_for_day`` was computed correctly server-side but never surfaced to
any client code path (initial page render, the 10s status poll, or the tap
response itself) -- a student who tapped "Done for the Day" still saw an
enabled Start Work / Break row on reload. The server-side re-open guard in
``app/feats/prod.py`` already refused a same-day restart (409), so this was
presentation-only, but confirmed live: operator used "Done for Day" as
Jordan, reloaded, and the dashboard still showed "Active" with enabled
buttons.

``is_done_for_day()`` (app/services/attendance_service.py) is the single
computation now shared by ``get_class_attendance_status`` (page render +
``/api/student-status`` poll) and ``/api/tap``'s own response.
"""
from __future__ import annotations

from app.services.attendance_service import get_class_attendance_status, is_done_for_day
from app.services.context_resolver import CanonicalContext
from tests.helpers.attendance_domain import tap_in_student
from tests.helpers.classroom_initializer import initialize_as_student


def _ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _tap_out_done(client, *, pin: str):
    return client.post(
        "/api/tap",
        json={"action": "tap_out", "pin": pin, "reason": "Done for the day"},
    )


def test_is_done_for_day_false_before_any_done_for_day_event(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        assert is_done_for_day(student.seat.id, classroom.class_id, ctx=_ctx(classroom, student)) is False


def test_is_done_for_day_true_after_a_done_for_day_stop_work(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    assert _tap_out_done(client, pin="1234").status_code == 200

    with app.app_context():
        assert is_done_for_day(student.seat.id, classroom.class_id, ctx=_ctx(classroom, student)) is True


def test_get_class_attendance_status_reports_done(client, app):
    """The shared read that feeds both the page render and the poller."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    assert _tap_out_done(client, pin="1234").status_code == 200

    with app.app_context():
        state = get_class_attendance_status(
            student.seat, class_id=classroom.class_id, ctx=_ctx(classroom, student)
        )
        assert state["done"] is True
        assert state["active"] is False


def test_tap_response_reports_done_for_day_after_the_done_reason(client, app):
    """The /api/tap response itself must carry "done" -- this is what the
    button-disabling client code now reads immediately after the tap that
    caused it, without waiting for the next poll.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    response = _tap_out_done(client, pin="1234")

    assert response.status_code == 200
    assert response.get_json()["done"] is True


def test_tap_response_reports_done_false_for_an_ordinary_tap_in(client, app):
    initialize_as_student("chemistry_p1", client, app)

    response = tap_in_student(client, pin="1234")

    assert response.status_code == 200
    assert response.get_json()["done"] is False


def test_student_status_poll_reports_done_after_done_for_day(client, app):
    """The 10s poller (/api/student-status) must also carry "done" -- this is
    what corrects the button state on a page that was already open when
    "Done for the Day" was tapped from elsewhere (e.g. a second tab).
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    assert _tap_out_done(client, pin="1234").status_code == 200

    response = client.get("/api/student-status")

    assert response.status_code == 200
    body = response.get_json()
    assert body["attendance_state"]["done"] is True


def test_a_repeated_start_work_while_already_active_reports_done_false(client, app):
    """Covers handle_tap's "start_work while already active" early return,
    which hardcodes "done": False -- correct because a still-active session
    can never itself be a completed done-for-day event.
    """
    initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    response = tap_in_student(client, pin="1234")

    assert response.status_code == 200
    assert response.get_json()["done"] is False


def test_a_further_stop_work_while_already_done_still_reports_done(client, app):
    """Covers handle_tap's "stop_work while not currently_active" early
    return, which computes "done" via is_done_for_day() rather than a bare
    literal (unlike the symmetric "start_work while already active" branch,
    which can never be done-for-day and correctly hardcodes False).
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    assert _tap_out_done(client, pin="1234").status_code == 200

    response = _tap_out_done(client, pin="1234")

    assert response.status_code == 200
    assert response.get_json()["done"] is True
