"""An open hall pass must not survive the class-local day (DOM-PROD-001 §XI.1).

Each test states what DOM-PROD-001 / FEAT-PROD-001 §VI require at the day
boundary and drives the real routes and sweep under a pinned clock.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession, HallPassLog, HallPassSettings
from app.scheduled_tasks import close_prior_day_hall_pass_requests_job, enforce_daily_limits_job
from app.services.attendance_service import (
    calculate_payable_attendance_seconds,
    calculate_worked_attendance_seconds_today,
    get_class_attendance_status,
)
from app.services.attendance_writer_service import close_due_hanging_hall_pass
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_available_hall_pass_grant, grant_hall_passes
from app.services.hall_pass_request_queue import list_pending_hall_pass_requests_for_class
from app.services.hall_pass_status_service import (
    HALL_PASS_STATUS_RETURNED,
    resolve_hall_pass_lifecycle_status,
)
from tests.helpers import temporal
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.hall_pass_requests import seed_pending_hall_pass_request

DAY_1 = date(2027, 3, 2)
DAY_2 = date(2027, 3, 3)
DAY_3 = date(2027, 3, 4)
ONE_HOUR = 3600


def _ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _start_work(classroom, student):
    record_attendance_session(
        ctx=_ctx(classroom, student), status="active", mechanism="self",
        idempotency_key=f"start:{student.seat.id}:{temporal.now().isoformat()}",
    )


def _issue_pass(client, classroom, student):
    """Teacher approval of a real pending request; leaves the teacher logged in."""
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="hall_pass")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"policy:{class_id}"):
        predecessor = HallPassSettings.query.filter_by(
            class_id=class_id, availability_state="IN_USE"
        ).first()
        if predecessor is not None:
            predecessor.availability_state = "RETIRED"
            db.session.flush()
        db.session.add(HallPassSettings(
            class_id=class_id,
            max_queue_limit=10,
            effective_date=temporal.now(),
            pass_type_payload=[
                {"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}
            ],
        ))
        db.session.flush()
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
        grant_hall_passes(student.seat, 1, correlation_id=f"corr:{student.seat.id}")
    seed_pending_hall_pass_request(
        request_id="req-1", class_id=class_id, seat_id=student.seat.id,
        destination="Bathroom", requested_at_utc=temporal.now(),
    )
    login_teacher(client, classroom)
    assert client.post("/api/hall-pass/request/req-1/approve").status_code == 200
    return HallPassLog.query.filter_by(class_id=class_id).one()


def _out_on_a_pass_on_day_1(client, classroom, student):
    """Worked 09:00-10:00 on day 1, then left on a pass and never came back."""
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 10)):
        log = _issue_pass(client, classroom, student)
        login_student(client, student)
        assert client.post("/api/hall-pass/checkout", json={"pass_id": log.id}).status_code == 200
    return log


def _timeline(classroom, student):
    return (
        AttendanceSession.query
        .filter_by(class_id=classroom.class_id, target_seat_id=student.seat.id)
        .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
        .all()
    )


def _sweep_at(class_id, on, hour):
    with temporal.pinned_clock(temporal.class_wall_time(class_id, on, hour)):
        enforce_daily_limits_job()
        db.session.commit()


@pytest.fixture
def setup(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        yield classroom, classroom.students[0]


def test_DOM_PROD_001__day_end_sweep_resolves_a_hanging_pass(client, setup):
    """§XI.1: a hanging pass gets active + inactive/done_for_day at one timestamp."""
    classroom, student = setup
    _out_on_a_pass_on_day_1(client, classroom, student)

    _sweep_at(classroom.class_id, DAY_2, 1)

    rows = _timeline(classroom, student)
    assert [(r.status, r.reason_code) for r in rows[-2:]] == [
        ("active", "start_work"), ("inactive", "done_for_day"),
    ]
    assert rows[-1].timestamp == rows[-2].timestamp


def test_teacher_return_on_a_later_day_does_not_open_a_paid_session(client, setup):
    """A return click after the boundary resumes nothing: only day 1's hour is owed."""
    classroom, student = setup
    class_id = classroom.class_id
    log = _out_on_a_pass_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 8)):
        login_teacher(client, classroom)
        assert client.post(f"/api/hall-pass/{log.id}/return").status_code == 400

    _sweep_at(class_id, DAY_3, 1)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_3, 1)):
        payable = calculate_payable_attendance_seconds(
            student.seat.id, class_id, ctx=_ctx(classroom, student)
        )
    assert payable == ONE_HOUR


def test_sweep_closes_a_pass_the_student_started_work_past(client, setup):
    """Starting work first must not leave the old pass open, or cost today's session."""
    classroom, student = setup
    class_id = classroom.class_id
    log = _out_on_a_pass_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 9)):
        _start_work(classroom, student)
    _sweep_at(class_id, DAY_2, 10)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 10)):
        assert resolve_hall_pass_lifecycle_status(
            class_id=class_id, seat_id=student.seat.id, hall_pass_id=log.hall_pass_id,
        ).status == HALL_PASS_STATUS_RETURNED
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )
    assert status["active"] is True
    assert status["done"] is False
    assert status["duration_today"] == ONE_HOUR
    rows = _timeline(classroom, student)
    assert rows[-1].status == "active" and rows[-1].mechanism == "self"


def test_prior_day_pass_is_not_shown_to_the_student_as_currently_out(client, setup):
    """The dashboard state drives the Return control and disables Start Work."""
    classroom, student = setup
    _out_on_a_pass_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(classroom.class_id, DAY_2, 9)):
        status = get_class_attendance_status(
            student.seat, class_id=classroom.class_id, ctx=_ctx(classroom, student)
        )
    assert status["hall_pass"] is None


def test_checkin_from_a_prior_day_pass_does_not_end_the_session_in_progress(client, setup):
    """A stale check-in must not close today's work as done_for_day and reopen it."""
    classroom, student = setup
    class_id = classroom.class_id
    log = _out_on_a_pass_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 9)):
        _start_work(classroom, student)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 10)):
        login_student(client, student)
        client.post("/api/hall-pass/checkin", json={"pass_id": log.id})
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )
    assert not (status["active"] and status["done"])


def test_pass_cannot_be_marked_left_after_the_session_has_closed(client, setup):
    """Leaving needs a session to leave: a done student cannot return until tomorrow."""
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
        record_attendance_session(
            ctx=_ctx(classroom, student), status="inactive", mechanism="self",
            reason="done_for_day", idempotency_key=f"done:{student.seat.id}",
        )
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 10)):
        log = _issue_pass(client, classroom, student)
        response = client.post(f"/api/hall-pass/{log.id}/leave")
    assert response.status_code == 400


def test_time_today_excludes_a_prior_day_session_the_sweep_has_not_closed(client, setup):
    """Payroll bounds this session at its own day end; Time Today must agree."""
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 0, 10)):
        seconds = calculate_worked_attendance_seconds_today(
            student.seat.id, class_id, ctx=_ctx(classroom, student)
        )
    assert seconds == 0


def test_day_end_closure_earns_nothing_and_leaves_the_next_day_open(client, setup):
    """The closure sits on the next day's first instant but belongs to the day before."""
    classroom, student = setup
    class_id = classroom.class_id
    log = _out_on_a_pass_on_day_1(client, classroom, student)

    _sweep_at(class_id, DAY_2, 1)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 9)):
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )
        assert status["done"] is False
        assert status["duration_today"] == 0
        assert status["hall_pass"] is None
        assert resolve_hall_pass_lifecycle_status(
            class_id=class_id, seat_id=student.seat.id, hall_pass_id=log.hall_pass_id,
        ).status == HALL_PASS_STATUS_RETURNED
        assert calculate_payable_attendance_seconds(
            student.seat.id, class_id, ctx=_ctx(classroom, student)
        ) == ONE_HOUR
        _start_work(classroom, student)
    assert _timeline(classroom, student)[-1].status == "active"


def test_day_end_closure_is_written_once_and_records_the_day_it_left_on(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    _out_on_a_pass_on_day_1(client, classroom, student)

    _sweep_at(class_id, DAY_3, 1)
    rows_after_first_sweep = len(_timeline(classroom, student))
    _sweep_at(class_id, DAY_3, 2)

    rows = _timeline(classroom, student)
    assert len(rows) == rows_after_first_sweep
    day_1_end = temporal.class_day_bounds(class_id, DAY_1)[1]
    assert rows[-1].timestamp == day_1_end
    assert rows[-1].mechanism == "system"


def test_sweep_leaves_a_same_day_pass_open(client, setup):
    """The student may still walk back in: only the end of the day ends the pass."""
    classroom, student = setup
    class_id = classroom.class_id
    _out_on_a_pass_on_day_1(client, classroom, student)

    _sweep_at(class_id, DAY_1, 23)

    assert _timeline(classroom, student)[-1].reason_code == "hall_pass"


def test_return_after_the_sweep_opens_no_session(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    log = _out_on_a_pass_on_day_1(client, classroom, student)

    _sweep_at(class_id, DAY_2, 1)
    rows_before = len(_timeline(classroom, student))
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 8)):
        login_student(client, student)
        assert client.post("/api/hall-pass/checkin", json={"pass_id": log.id}).status_code == 200

    assert len(_timeline(classroom, student)) == rows_before


def test_return_on_a_pass_that_never_left_opens_no_session(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
        log = _issue_pass(client, classroom, student)
        rows_before = len(_timeline(classroom, student))
        assert client.post(f"/api/hall-pass/{log.id}/return").status_code == 400

    assert len(_timeline(classroom, student)) == rows_before


def test_closing_a_hanging_pass_touches_only_its_own_class(app, client, setup):
    classroom, student = setup
    other = initialize("ap_csp_p3", app)
    other_student = other.students[0]
    with temporal.pinned_clock(temporal.class_wall_time(other.class_id, DAY_1, 9)):
        _start_work(other, other_student)
    _out_on_a_pass_on_day_1(client, classroom, student)

    rows_before = len(_timeline(classroom, student))
    with temporal.pinned_clock(temporal.class_wall_time(classroom.class_id, DAY_2, 1)):
        with pytest.raises(ValueError, match="canonical class"):
            close_due_hanging_hall_pass(
                ctx=_ctx(other, other_student), seat_id=student.seat.id,
                as_of_utc=temporal.class_wall_time(classroom.class_id, DAY_2, 1),
            )

    assert [r.status for r in _timeline(other, other_student)] == ["active"]
    assert len(_timeline(classroom, student)) == rows_before


@pytest.mark.parametrize("actor", ["student", "teacher"])
def test_a_pass_that_has_ended_cannot_leave_again(client, setup, actor):
    """A second exit would leave the student out on a pass that reads returned."""
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
        log = _issue_pass(client, classroom, student)
        login_student(client, student)
        assert client.post("/api/hall-pass/checkout", json={"pass_id": log.id}).status_code == 200
        assert client.post("/api/hall-pass/checkin", json={"pass_id": log.id}).status_code == 200
        rows_before = len(_timeline(classroom, student))

        if actor == "teacher":
            login_teacher(client, classroom)
            response = client.post(f"/api/hall-pass/{log.id}/leave")
        else:
            response = client.post("/api/hall-pass/checkout", json={"pass_id": log.id})

    assert response.status_code == 400
    assert len(_timeline(classroom, student)) == rows_before
    assert _timeline(classroom, student)[-1].status == "active"


def test_approved_pass_leaves_attendance_to_the_ordinary_close(client, setup):
    """Approval never touches attendance: the session simply ends done_for_day."""
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 10)):
        log = _issue_pass(client, classroom, student)

    _sweep_at(class_id, DAY_2, 1)

    rows = _timeline(classroom, student)
    assert [(r.status, r.reason_code) for r in rows] == [
        ("active", "start_work"), ("inactive", "done_for_day"),
    ]
    assert rows[-1].timestamp == temporal.class_day_bounds(class_id, DAY_1)[1]
    assert not [r for r in rows if r.hall_pass_id == log.hall_pass_id]


def _approved_on_day_1(client, classroom, student):
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 10)):
        return _issue_pass(client, classroom, student)


@pytest.mark.parametrize("actor", ["student", "teacher"])
def test_revoked_pass_cannot_be_left_on(client, setup, actor):
    classroom, student = setup
    class_id = classroom.class_id
    log = _approved_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 9)):
        _start_work(classroom, student)
        rows_before = len(_timeline(classroom, student))
        if actor == "teacher":
            login_teacher(client, classroom)
            response = client.post(f"/api/hall-pass/{log.id}/leave")
        else:
            login_student(client, student)
            response = client.post("/api/hall-pass/checkout", json={"pass_id": log.id})

    assert response.status_code == 400
    assert len(_timeline(classroom, student)) == rows_before


def test_revoked_is_derived_and_the_pass_stays_used(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    _approved_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 20)):
        login_teacher(client, classroom)
        same_day = client.get(
            "/api/hall-pass/history",
            query_string={"start_date": DAY_1.isoformat(), "end_date": DAY_1.isoformat()},
        ).get_json()["records"]
    assert [r["status"] for r in same_day] == ["approved"]

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 9)):
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )
        login_teacher(client, classroom)
        records = client.get(
            "/api/hall-pass/history",
            query_string={"start_date": DAY_1.isoformat(), "end_date": DAY_1.isoformat()},
        ).get_json()["records"]
        spare_pass = get_available_hall_pass_grant(student.seat.id, class_id)
    assert status["hall_pass"] is None
    assert [r["status"] for r in records] == ["revoked"]
    assert spare_pass is None
    assert HallPassLog.query.filter_by(class_id=class_id).count() == 1


def _pending_on_day_1(classroom, student):
    class_id = classroom.class_id
    enable_class_feature(class_id=class_id, feature="hall_pass")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
        grant_hall_passes(student.seat, 1, correlation_id=f"corr:{student.seat.id}")
    seed_pending_hall_pass_request(
        request_id=f"req-{student.seat.id}", class_id=class_id, seat_id=student.seat.id,
        destination="Bathroom",
        requested_at_utc=temporal.class_wall_time(class_id, DAY_1, 10),
    )
    assert get_available_hall_pass_grant(student.seat.id, class_id) is None


def _close_requests_at(class_id, on, hour):
    with temporal.pinned_clock(temporal.class_wall_time(class_id, on, hour)):
        close_prior_day_hall_pass_requests_job()


def test_request_open_at_the_day_boundary_closes_like_a_denial(setup):
    classroom, student = setup
    class_id = classroom.class_id
    _pending_on_day_1(classroom, student)

    _close_requests_at(class_id, DAY_1, 23)
    assert len(list_pending_hall_pass_requests_for_class(class_id)) == 1

    _close_requests_at(class_id, DAY_2, 1)
    assert list_pending_hall_pass_requests_for_class(class_id) == []
    assert get_available_hall_pass_grant(student.seat.id, class_id) is not None
    assert HallPassLog.query.filter_by(class_id=class_id).count() == 0


def test_closing_requests_goes_by_each_requests_own_day_and_class(app, setup):
    classroom, student = setup
    other = initialize("ap_csp_p3", app)
    other_student = other.students[0]
    _pending_on_day_1(classroom, student)
    enable_class_feature(class_id=other.class_id, feature="hall_pass")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{other_student.seat.id}"):
        grant_hall_passes(other_student.seat, 1, correlation_id=f"corr:{other_student.seat.id}")
    seed_pending_hall_pass_request(
        request_id="req-today", class_id=other.class_id, seat_id=other_student.seat.id,
        destination="Bathroom", requested_at_utc=temporal.class_wall_time(other.class_id, DAY_2, 8),
    )

    _close_requests_at(classroom.class_id, DAY_2, 9)

    assert list_pending_hall_pass_requests_for_class(classroom.class_id) == []
    assert [r.request_id for r in list_pending_hall_pass_requests_for_class(other.class_id)] == ["req-today"]


def test_prior_day_request_cannot_be_approved_before_the_job_closes_it(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    _pending_on_day_1(classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 0, 5)):
        login_teacher(client, classroom)
        response = client.post(f"/api/hall-pass/request/req-{student.seat.id}/approve")
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )

    assert response.status_code == 400
    assert status["hall_pass"] is None
    assert HallPassLog.query.filter_by(class_id=class_id).count() == 0


def test_no_active_state_passes_the_day_boundary_before_the_sweep(client, setup):
    """A prior day's unclosed row is over: it isn't live, and today starts a new session."""
    classroom, student = setup
    class_id = classroom.class_id
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 9)):
        _start_work(classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 0, 5)):
        status = get_class_attendance_status(
            student.seat, class_id=class_id, ctx=_ctx(classroom, student)
        )
        assert status["active"] is False
        assert status["done"] is False
        login_teacher(client, classroom)
        tapped_out = client.post(
            "/admin/tap-out-students", json={"seat_ids": [student.seat.id], "reason": "done"},
        )
        assert tapped_out.status_code == 200
        assert len(_timeline(classroom, student)) == 1
        tapped_in = client.post("/admin/tap-in-students", json={"seat_ids": [student.seat.id]})
        assert tapped_in.status_code == 200

    rows = _timeline(classroom, student)
    day_1_end = temporal.class_day_bounds(class_id, DAY_1)[1]
    assert [(r.status, r.reason_code) for r in rows] == [
        ("active", "start_work"), ("inactive", "done_for_day"), ("active", "start_work"),
    ]
    assert rows[1].timestamp == day_1_end


def test_prior_day_session_cannot_be_left_on_a_pass(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    log = _approved_on_day_1(client, classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_1, 23)):
        rows_before = len(_timeline(classroom, student))
    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 0, 5)):
        with pytest.raises(ValueError, match="no work session"):
            record_attendance_session(
                ctx=_ctx(classroom, student), status="inactive", mechanism="self",
                reason_code=AttendanceReasonCode.HALL_PASS, hall_pass_id=log.hall_pass_id,
                idempotency_key=f"stale-leave:{student.seat.id}",
            )
    db.session.rollback()
    assert len(_timeline(classroom, student)) == rows_before


def test_prior_day_request_does_not_show_as_open_to_the_teacher(client, setup):
    classroom, student = setup
    class_id = classroom.class_id
    _pending_on_day_1(classroom, student)

    with temporal.pinned_clock(temporal.class_wall_time(class_id, DAY_2, 0, 5)):
        login_teacher(client, classroom)
        page = client.get("/admin/hall-pass")
    assert page.status_code == 200
    assert f"req-{student.seat.id}".encode() not in page.data
