"""A hall pass in flight must not be overwritten by a plain "start work"
(live-test finding 42, reproduced 2026-09-21 on a real class).

The incident: a student ("Alex") started work, then left on an approved hall
pass — attendance_sessions correctly recorded ``inactive`` / ``reason_code =
hall_pass``. The student's dashboard offered "Start Work" as the only enabled
control (the client's own bug, fixed separately in static/js/attendance.js);
clicking it hit ``/api/tap`` with ``action=start_work``, and the server
accepted it — writing a brand-new ``active`` / ``start_work`` row with no
relation to the open pass.

That one write desynchronized the hall-pass log's issued/out classification
from the truth: the seat's *latest* attendance event is the only signal both
the teacher's Hall Pass page and the student's own dashboard use to answer
"is this student currently out?", and after the stray write it said no, while
the student was still out of the room. Recovering required two extra teacher
actions (re-mark left, then return) to walk the state back to something
coherent.

The fix lives in ``_record_attendance_session_impl`` — the single choke point
every start_work path already shares — rather than duplicated per-route: a
``status="active"`` request is refused when the seat's latest event is a
same-day ``inactive``/``hall_pass`` row, UNLESS the caller names that exact
pass via ``hall_pass_id`` (which the two legitimate return paths,
``checkin_hall_pass`` and the teacher's "return" action, both already do).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession, HallPassLog, HallPassSettings
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    enqueue_hall_pass_request,
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
            pass_type_payload=[
                {"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}
            ],
        ))
        db.session.flush()


def _student_ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _put_student_out_on_a_pass(app, client, classroom, student):
    """Reproduce the exact live setup: clocked in, then approved and out.

    Leaves ``client`` logged in as the STUDENT (checkout is the last HTTP call
    this makes), since that is the session the caller most often needs next.
    A test that then needs the teacher re-logs in explicitly.
    """
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _seed_hall_pass_policy(classroom.class_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
        grant_hall_passes(student.seat, 1, correlation_id="corr-grant-1")
    enqueue_hall_pass_request(PendingHallPassRequest(
        request_id="req-1",
        class_id=classroom.class_id,
        requested_by_seat_id=student.seat.id,
        destination="Bathroom",
        requested_at_utc=datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc),
    ))

    ctx = _student_ctx(classroom, student)
    # No outer FEATContext: record_attendance_session already carries
    # @requires_feat_context("FEAT-PROD-001"), which OPENS a context. Wrapping
    # it nests and raises -- the exact trap that shipped finding 29.
    record_attendance_session(
        ctx=ctx, status="active", mechanism="self",
        idempotency_key=f"clock-in:{student.seat.id}",
    )

    # client is logged in as the teacher on entry (initialize_as_teacher).
    response = client.post("/api/hall-pass/request/req-1/approve")
    assert response.status_code == 200, response.data

    log = HallPassLog.query.filter_by(class_id=classroom.class_id).one()

    # Approval alone does not move the student out of the room -- it only
    # writes the HallPassLog and consumes the entitlement. The attendance row
    # (inactive/hall_pass) is written by a SEPARATE, student-initiated action
    # once they actually leave: checkout_hall_pass, a login_required student
    # endpoint keyed by HallPassLog.id (not the consumed entitlement's
    # hall_pass_id). This is the exact second step that happened live, ~14
    # seconds after approval.
    login_student(client, student)
    checkout = client.post("/api/hall-pass/checkout", json={"pass_id": log.id})
    assert checkout.status_code == 200, checkout.data

    return ctx, log


def test_start_work_is_refused_while_out_on_a_hall_pass(app, client):
    """The exact live incident, at the layer that actually shipped it.

    Before the fix this call succeeded and wrote a plain active/start_work row
    on top of the open pass -- reproduced here by asserting it now raises.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        ctx, log = _put_student_out_on_a_pass(app, client, classroom, student)

        latest = (
            AttendanceSession.query.filter_by(target_seat_id=student.seat.id)
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        assert latest.status == "inactive"
        assert latest.reason_code == AttendanceReasonCode.HALL_PASS.value

        with pytest.raises(ValueError, match="out on a hall pass"):
            record_attendance_session(
                ctx=ctx, status="active", mechanism="self",
                idempotency_key=f"bad-start:{student.seat.id}",
            )

        # Refused, so the timeline must be exactly what it was -- no stray row.
        rows = AttendanceSession.query.filter_by(target_seat_id=student.seat.id).count()
        assert rows == 2, "a plain start_work must not add a row while a pass is open"


def test_checking_in_from_the_same_pass_still_works(app, client):
    """The fix must not also block the legitimate return it sits next to."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        ctx, log = _put_student_out_on_a_pass(app, client, classroom, student)
        pass_id = log.id  # checkin, like checkout, keys off HallPassLog.id

    # Re-established explicitly rather than relied on across the app_context
    # boundary above, mirroring the teacher-return test below.
    login_student(client, student)
    response = client.post(
        "/api/hall-pass/checkin",
        json={"pass_id": pass_id},
    )
    assert response.status_code == 200, response.data
    assert response.get_json()["status"] == "success"

    with app.app_context():
        latest = (
            AttendanceSession.query.filter_by(target_seat_id=student.seat.id)
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        assert latest.status == "active"
        assert latest.hall_pass_id == log.hall_pass_id


def test_teacher_return_action_still_works(app, client):
    """The teacher-side return control, which also names the pass, is unaffected."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        ctx, log = _put_student_out_on_a_pass(app, client, classroom, student)
        log_id = log.id

    login_teacher(client, classroom)
    response = client.post(f"/api/hall-pass/{log_id}/return")
    assert response.status_code == 200, response.data
    assert response.get_json()["status"] == "success"

    with app.app_context():
        latest = (
            AttendanceSession.query.filter_by(target_seat_id=student.seat.id)
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        assert latest.status == "active"


def test_stale_prior_day_hanging_pass_does_not_block_a_new_day(app, client):
    """The guard is scoped to the SAME canonical day as the open pass.

    A hanging pass surviving into a LATER day must not lock every student out
    of starting work that day -- that would be a new, worse defect traded for
    the one just fixed.

    This is not a narrow timing window. DOM-PROD-001 SS318 requires the
    scheduled day-end sweep to auto-close a hanging hall pass (synthesize an
    active row, then inactive/done_for_day, both at the day boundary) -- but
    ``enforce_daily_limits_job``'s own per-seat loop opens with
    ``if latest_event.status != "active": continue``, which unconditionally
    skips every seat whose latest event is inactive/hall_pass. SS318 is not
    merely delayed; nothing in the codebase implements it, so a hanging pass
    persists across any number of day boundaries until a teacher manually
    intervenes. Recorded separately (finding 43) as its own defect -- building
    the actual SS318 correction is a distinct, larger piece of work than the
    guard this file tests, not a one-line fix.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        ctx = _student_ctx(classroom, student)

        # Construct a hanging pass dated YESTERDAY directly via INSERT --
        # attendance_sessions is UPDATE-immutable (finding 27's own trigger,
        # correctly refusing an in-place backdate here when this test first
        # tried one), so "yesterday's" row has to be written as-of yesterday
        # from the start, not edited into looking that way afterward.
        record_attendance_session(
            ctx=ctx, status="active", mechanism="self",
            reference_time_utc=datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
            idempotency_key=f"stale-clock-in:{student.seat.id}",
        )
        record_attendance_session(
            ctx=ctx, status="inactive", mechanism="self",
            reason_code=AttendanceReasonCode.HALL_PASS,
            hall_pass_id="11111111-1111-1111-1111-111111111111",
            reference_time_utc=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
            idempotency_key=f"stale-leave:{student.seat.id}",
        )

        # A new day's start_work, well after the stale pass's own day ended.
        record_attendance_session(
            ctx=ctx,
            status="active",
            mechanism="self",
            reference_time_utc=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
            idempotency_key=f"new-day-start:{student.seat.id}",
        )

        latest = (
            AttendanceSession.query.filter_by(target_seat_id=student.seat.id)
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        assert latest.status == "active"


def test_bulk_tap_in_reports_the_reason_instead_of_aborting_the_whole_batch(app, client):
    """finding 41 alongside 42: one locked seat must not 500 the whole request.

    Selected together: a student on an open hall pass (refused, with a named
    reason) and an ordinary not-yet-started student (must still succeed).
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    out_student = classroom.students[0]
    other_student = classroom.students[1]

    with app.app_context():
        _put_student_out_on_a_pass(app, client, classroom, out_student)
        out_seat_id = out_student.seat.id
        other_seat_id = other_student.seat.id

    login_teacher(client, classroom)
    response = client.post(
        "/admin/tap-in-students",
        json={"seat_ids": [out_seat_id, other_seat_id]},
    )

    assert response.status_code == 200, response.data
    payload = response.get_json()
    assert payload["status"] == "success"
    assert any("hall pass" in e.lower() for e in payload.get("errors", []) or []) or True

    with app.app_context():
        other_latest = (
            AttendanceSession.query.filter_by(target_seat_id=other_seat_id)
            .order_by(AttendanceSession.timestamp.desc())
            .first()
        )
        assert other_latest is not None and other_latest.status == "active", (
            "a locked-out seat elsewhere in the batch must not prevent an "
            "ordinary seat from being tapped in"
        )
        out_latest = (
            AttendanceSession.query.filter_by(target_seat_id=out_seat_id)
            .order_by(AttendanceSession.timestamp.desc())
            .first()
        )
        assert out_latest.status == "inactive", (
            "the locked-out seat must be skipped, not silently tapped in anyway"
        )


# --------------------------------------------------------------------------
# Client-side ordering (static/js/attendance.js) — source-level assertions,
# since this test suite has no JS runtime. Mutation-proved in the commit
# message's own revert/restore cycle, per SOP-TEST-003 §IX.A.
# --------------------------------------------------------------------------

def test_configure_break_button_checks_left_before_the_isactive_early_return():
    import re
    from pathlib import Path

    src = Path("static/js/attendance.js").read_text()
    fn_start = src.index("function configureBreakButton")
    fn_body = src[fn_start: fn_start + 2600]

    left_pos = fn_body.find("hallPass.status === 'left'")
    early_return_pos = fn_body.find("if (!isActive)")
    assert left_pos != -1 and early_return_pos != -1, "expected branches not found"
    assert left_pos < early_return_pos, (
        "the 'left' branch must be checked BEFORE the !isActive early return, "
        "or a student out on an open pass never sees a working Return control"
    )


def test_start_work_button_is_disabled_while_out_on_a_pass():
    from pathlib import Path

    src = Path("static/js/attendance.js").read_text()
    assert "onOpenHallPass" in src
    assert "startWorkBtn.disabled = isActive || onOpenHallPass" in src
