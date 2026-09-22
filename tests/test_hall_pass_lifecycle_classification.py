"""A hall pass exits the Issued/Out tabs once it is returned (finding 44).

Raised live tonight: Jordan Lee completed a full self-service round trip
(approved -> left -> returned, confirmed correct on the public verification
page), but the teacher's Hall Pass Management page kept listing them under
Issued with a "Left Class" button -- as if they had never left. Clicking that
button would have sent an already-returned student back out.

The teacher's page asked a cruder question than the verification page: only
whether the seat's single LATEST attendance event was inactive/hall_pass, with
no representation of "returned" at all. A completed round trip and a pass that
had never been used both answer that question "no" and landed in the same
catch-all bucket. v1's Issued/Out tabs were a temporary holding area, not a
permanent record -- once returned, a pass should leave both.

The fix factors the three-state model (approved / left / returned) the
verification page already computed correctly into
``resolve_hall_pass_lifecycle_status``, and both routes now call it, so the
question can no longer be answered two different ways.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceSession, HallPassLog, HallPassSettings
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    enqueue_hall_pass_request,
)
from app.services.hall_pass_status_service import (
    HALL_PASS_STATUS_APPROVED,
    HALL_PASS_STATUS_LEFT,
    HALL_PASS_STATUS_RETURNED,
    resolve_hall_pass_lifecycle_status,
)
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _seed_hall_pass_policy(class_id: str) -> None:
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"hall_pass_policy:{class_id}"):
        predecessor = (
            HallPassSettings.query
            .filter_by(class_id=class_id, availability_state="IN_USE")
            .first()
        )
        if predecessor is not None:
            predecessor.availability_state = "RETIRED"
            db.session.flush()
        db.session.add(HallPassSettings(
            class_id=class_id,
            max_queue_limit=10,
            pass_type_payload=[{"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}],
        ))
        db.session.flush()


def _approve_pass(app, client, classroom, student, request_id="req-1"):
    """Get a pass to 'approved' and return the HallPassLog row."""
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _seed_hall_pass_policy(classroom.class_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}:{request_id}"):
        grant_hall_passes(student.seat, 1, correlation_id=f"corr-grant-{request_id}")
    enqueue_hall_pass_request(PendingHallPassRequest(
        request_id=request_id,
        class_id=classroom.class_id,
        requested_by_seat_id=student.seat.id,
        destination="Bathroom",
        requested_at_utc=datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc),
    ))
    ctx = CanonicalContext(
        user_id=student.user.id, class_id=classroom.class_id,
        seat_id=student.seat.id, actor_role="student",
    )
    record_attendance_session(
        ctx=ctx, status="active", mechanism="self",
        idempotency_key=f"clock-in:{student.seat.id}:{request_id}",
    )
    response = client.post(f"/api/hall-pass/request/{request_id}/approve")
    assert response.status_code == 200, response.data
    return HallPassLog.query.filter_by(
        class_id=classroom.class_id, requested_by_seat_id=student.seat.id,
    ).order_by(HallPassLog.timestamp.desc()).first()


def _leave(client, student, log):
    login_student(client, student)
    r = client.post("/api/hall-pass/checkout", json={"pass_id": log.id})
    assert r.status_code == 200, r.data


def _return(client, student, log):
    login_student(client, student)
    r = client.post("/api/hall-pass/checkin", json={"pass_id": log.id})
    assert r.status_code == 200, r.data


# --------------------------------------------------------------------------
# The shared resolver, directly -- all three states
# --------------------------------------------------------------------------

def test_resolver_reports_approved_before_any_departure(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
        result = resolve_hall_pass_lifecycle_status(
            class_id=classroom.class_id, seat_id=student.seat.id,
            hall_pass_id=log.hall_pass_id,
            day_boundary_start_utc=datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc),
            day_boundary_end_utc=datetime(2026, 9, 22, 7, 0, tzinfo=timezone.utc),
        )
        assert result.status == HALL_PASS_STATUS_APPROVED
        assert result.left_row is None
        assert result.return_row is None


def test_resolver_reports_left_after_departure(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
    _leave(client, student, log)
    with app.app_context():
        result = resolve_hall_pass_lifecycle_status(
            class_id=classroom.class_id, seat_id=student.seat.id,
            hall_pass_id=log.hall_pass_id,
            day_boundary_start_utc=datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc),
            day_boundary_end_utc=datetime(2026, 9, 22, 7, 0, tzinfo=timezone.utc),
        )
        assert result.status == HALL_PASS_STATUS_LEFT
        assert result.left_row is not None
        assert result.return_row is None


def test_resolver_reports_returned_after_the_full_round_trip(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
    _leave(client, student, log)
    _return(client, student, log)
    with app.app_context():
        result = resolve_hall_pass_lifecycle_status(
            class_id=classroom.class_id, seat_id=student.seat.id,
            hall_pass_id=log.hall_pass_id,
            day_boundary_start_utc=datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc),
            day_boundary_end_utc=datetime(2026, 9, 22, 7, 0, tzinfo=timezone.utc),
        )
        assert result.status == HALL_PASS_STATUS_RETURNED
        assert result.left_row is not None
        assert result.return_row is not None


# --------------------------------------------------------------------------
# The teacher's Hall Pass Management page, end to end
# --------------------------------------------------------------------------

def test_a_returned_pass_disappears_from_both_issued_and_out(app, client):
    """The exact live incident: Jordan Lee's completed round trip.

    Before the fix this log's id still appeared in the Issued tab's
    'Left Class' button markup after a full return -- clicking it would have
    sent an already-returned student back out.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
        log_id = log.id

    _leave(client, student, log)
    _return(client, student, log)

    login_teacher(client, classroom)
    page = client.get("/admin/hall-pass").data.decode()

    assert f"handlePassAction({log_id}, 'leave')" not in page, (
        "a returned pass still offers 'Left Class' -- clicking it would send "
        "an already-returned student back out"
    )
    assert f"handlePassAction({log_id}, 'return')" not in page, (
        "a returned pass must not appear in the Out tab either"
    )


def test_an_approved_but_not_yet_departed_pass_is_in_issued(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
        log_id = log.id

    login_teacher(client, classroom)
    page = client.get("/admin/hall-pass").data.decode()

    assert f"handlePassAction({log_id}, 'leave')" in page
    assert f"handlePassAction({log_id}, 'return')" not in page


def test_a_pass_that_has_left_but_not_returned_is_in_out(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
        log_id = log.id
    _leave(client, student, log)

    login_teacher(client, classroom)
    page = client.get("/admin/hall-pass").data.decode()

    assert f"handlePassAction({log_id}, 'return')" in page
    assert f"handlePassAction({log_id}, 'leave')" not in page


# --------------------------------------------------------------------------
# /api/hall-pass/history -- the third place this concept was computed
# --------------------------------------------------------------------------

def test_history_reports_returned_and_ignores_an_unrelated_stray_active_row(app, client):
    """The exact shape of tonight's live incident (finding 42), for History.

    /api/hall-pass/history duplicated the same left_row/return_row logic a
    third time, independently of the admin Issued/Out classifier and the
    public verification page -- it happened to be correct, but that is luck,
    not a guarantee, and it is exactly the kind of duplication finding 44 grew
    out of. Migrated to the shared resolver; this proves the migration is
    behaviour-preserving even on a messy timeline like Alex's real one
    tonight, which included a stray active row with no hall_pass_id wedged
    between the real leave and the real return.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        log = _approve_pass(app, client, classroom, student)
        log_id = log.id
    _leave(client, student, log)

    # A stray, unrelated plain start_work row between the leave and the real
    # return -- exactly Alex's real shape tonight. Inserted directly (not
    # through record_attendance_session) because finding 42's own guard now
    # correctly refuses to CREATE this shape through any domain entry point,
    # including this one -- which is a second confirmation the fix holds. The
    # row can still exist historically (it does, on the live host, from before
    # that fix shipped), so history must resolve correctly around one anyway.
    with app.app_context():
        stray = AttendanceSession(
            target_seat_id=student.seat.id,
            actor_seat_id=student.seat.id,
            class_id=classroom.class_id,
            status="active",
            reason_code="start_work",
            mechanism="self",
            hall_pass_id=None,
        )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"stray:{student.seat.id}"):
            db.session.add(stray)
            db.session.flush()

    _return(client, student, log)

    login_teacher(client, classroom)
    response = client.get(
        "/api/hall-pass/history",
        query_string={"start_date": "2026-09-21", "end_date": "2026-09-21"},
    )
    assert response.status_code == 200, response.data
    payload = response.get_json()
    record = next(r for r in payload["records"] if r["id"] == log_id)
    assert record["status"] == "returned", record
    assert record["left_time"] is not None
    assert record["return_time"] is not None
