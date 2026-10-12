"""A hall pass cannot be issued in a class with no hall-pass settings.

FEAT-PROD-002 §III evaluates the class's ``hall_pass_settings`` before writing a
``hall_pass_logs`` row. Before this fix, a class with the feature turned on but
no settings row fell back to the built-in pass types and recorded
``policy_uuid = 'default'``, a reference that names no policy (DOM-POL-001 §VII).
Production held 14 such logs on 2026-10-06, written as recently as the day
before (docs/ops/audits/RECON_2026-10-06_P0B_PRODUCTION_STATE.md §5.2).

The owner ruled that there is no default policy: hall passes are unavailable
until the teacher saves settings, and nothing creates settings on the teacher's
behalf. The gate sits at every step, so a request exists only when it could be
approved:

* the student is offered no destinations;
* a request is refused and queues nothing;
* approval of a request made before the gate is refused, and per FEAT-PROD-002
  §III.A the request stays pending for the teacher to reject.
"""

import pytest

from app.extensions import db
from app.feats.attendance import save_hall_pass_setup_config
from app.feats.base import FEATContext
from app.feats.hall_pass_request_feat import approve_hall_pass_request, submit_hall_pass_request
from app.feats.prod import HallPassSettingsMissing
from app.models import EntitlementEvent, HallPassLog, HallPassSettings, PendingAction
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_hall_pass_balance, grant_hall_passes
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher
from tests.helpers.hall_pass_requests import seed_pending_hall_pass_request


_PAYLOAD = [{"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}]


def _remove_hall_pass_settings(class_id: str) -> None:
    """Reproduce production: the feature is on, but the teacher never saved settings."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"remove-hall-pass-settings:{class_id}"):
        HallPassSettings.query.filter_by(class_id=class_id).delete()
        db.session.flush()


def _class_without_settings(classroom, *, passes: int = 1):
    student = classroom.students[0]
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _remove_hall_pass_settings(classroom.class_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
        grant_hall_passes(student.seat, passes, correlation_id=f"corr-grant-{student.seat.id}")
    request = seed_pending_hall_pass_request(class_id=classroom.class_id, seat_id=student.seat.id)
    return student, request.request_id


def _consumed(class_id: str) -> int:
    """Passes used in the class. A hall-pass log naming a pass is the only consumption
    record (FEAT-PROD-002 §III; owner ruling 2026-10-09); use writes no CONSUMED event."""
    assert EntitlementEvent.query.filter_by(class_id=class_id, event_type="CONSUMED").count() == 0
    return HallPassLog.query.filter(
        HallPassLog.class_id == class_id, HallPassLog.hall_pass_id.isnot(None)
    ).count()


def test_approval_is_refused_without_settings_and_writes_nothing(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        student, request_id = _class_without_settings(classroom)
        balance_before = get_hall_pass_balance(student.seat.id, classroom.class_id)

    response = client.post(f"/api/hall-pass/request/{request_id}/approve")

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert "not set up" in body["message"]
    with app.app_context():
        db.session.expire_all()
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0
        assert _consumed(classroom.class_id) == 0
        assert get_hall_pass_balance(student.seat.id, classroom.class_id) == balance_before
        # FEAT-PROD-002 §III.A: a refused approval leaves the request pending.
        assert PendingAction.query.filter_by(
            class_id=classroom.class_id, pending_action_id=request_id
        ).count() == 1
        # The refusal exposes the missing configuration; it does not fabricate it.
        assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() == 0


def test_feat_refuses_without_settings_instead_of_recording_a_default_policy(client, app):
    classroom = initialize("chemistry_p1", app)
    student, request_id = _class_without_settings(classroom)
    ctx = CanonicalContext(
        user_id=classroom.teacher_user_id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id,
        actor_role="teacher",
    )

    with pytest.raises(HallPassSettingsMissing):
        approve_hall_pass_request(
            ctx=ctx,
            request_id=request_id,
            idempotency_key=f"hall_pass_approve:{classroom.class_id}:{request_id}",
        )
    db.session.rollback()

    assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0
    assert HallPassLog.query.filter_by(policy_uuid="default").count() == 0


def test_approval_succeeds_once_the_teacher_saves_settings(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        student, request_id = _class_without_settings(classroom)

    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 409

    with app.app_context():
        saved = save_hall_pass_setup_config(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            hall_pass_enabled=True,
            pass_type_payload=_PAYLOAD,
            max_queue_limit=10,
            correlation_id="corr_hall_pass_settings",
            idempotency_key="test:hall-pass:requires-settings",
        )
        saved_uuid = saved.policy_uuid

    response = client.post(f"/api/hall-pass/request/{request_id}/approve")

    assert response.status_code == 200, response.data
    with app.app_context():
        logs = HallPassLog.query.filter_by(class_id=classroom.class_id).all()
        assert [log.policy_uuid for log in logs] == [saved_uuid]
        assert _consumed(classroom.class_id) == 1


def test_another_class_settings_do_not_unlock_this_class(client, app):
    """Settings are class-scoped: a class with settings does not stand in for one without."""
    other = initialize("ap_csp_p3", app)
    assert HallPassSettings.query.filter_by(class_id=other.class_id).count() >= 1

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _student, request_id = _class_without_settings(classroom)

    response = client.post(f"/api/hall-pass/request/{request_id}/approve")

    assert response.status_code == 409
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0


def _student_class_without_settings(classroom, student):
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _remove_hall_pass_settings(classroom.class_id)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
        grant_hall_passes(student.seat, 1, correlation_id=f"corr-grant-{student.seat.id}")


def _pending_requests(class_id: str) -> int:
    return PendingAction.query.filter_by(class_id=class_id, authoritative_feat="FEAT-PROD-002").count()


def test_student_is_offered_no_destinations_until_settings_exist(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _student_class_without_settings(classroom, student)

    response = client.get("/api/hall-pass/available-types")

    assert response.status_code == 409
    assert response.get_json()["status"] == "error"
    assert "not set up" in response.get_json()["message"]

    with app.app_context():
        save_hall_pass_setup_config(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            hall_pass_enabled=True,
            pass_type_payload=_PAYLOAD,
            max_queue_limit=10,
            correlation_id="corr_hall_pass_types",
            idempotency_key="test:hall-pass:types",
        )

    response = client.get("/api/hall-pass/available-types")

    assert response.status_code == 200
    assert [t["pass_name"] for t in response.get_json()["pass_type_payload"]] == ["Bathroom"]


def test_request_is_refused_without_settings_and_queues_nothing(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _student_class_without_settings(classroom, student)

    started = client.post("/api/tap", json={"action": "start_work", "pin": student.pin})
    assert started.status_code == 200, started.data

    response = client.post("/api/hall-pass/request", json={"destination": "Bathroom", "pin": student.pin})

    assert response.status_code == 409, response.data
    assert "not set up" in response.get_json()["message"]
    with app.app_context():
        assert _pending_requests(classroom.class_id) == 0
        assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() == 0


def test_submit_feat_refuses_without_settings(client, app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    _student_class_without_settings(classroom, student)
    ctx = CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )

    with pytest.raises(HallPassSettingsMissing):
        submit_hall_pass_request(
            ctx=ctx,
            destination="Bathroom",
            requested_at_utc=utc_now(),
            idempotency_key=f"hall_pass_request:{classroom.class_id}:{student.seat.id}:test",
        )
    db.session.rollback()

    assert _pending_requests(classroom.class_id) == 0


# --------------------------------------------------------------------------
# No built-in destination preset (owner, 2026-10-06): nothing can display one.
# --------------------------------------------------------------------------

def test_there_is_no_built_in_destination_preset():
    assert not hasattr(HallPassSettings, "get_default_pass_types")
    assert HallPassSettings(pass_type_payload=[]).get_pass_types() == []


def test_teacher_setup_starts_empty_without_settings(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _remove_hall_pass_settings(classroom.class_id)

    setup = client.get("/api/hall-pass/setup")
    assert setup.status_code == 200
    assert setup.get_json()["pass_type_payload"] == []

    queue = client.get("/api/hall-pass/settings")
    assert queue.status_code == 200
    assert queue.get_json()["settings"]["pass_type_payload"] == []


def test_queue_limit_alone_does_not_create_settings(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _remove_hall_pass_settings(classroom.class_id)

    response = client.post("/api/hall-pass/settings", json={"max_queue_limit": 5})

    assert response.status_code == 409
    assert "not set up" in response.get_json()["message"]
    with app.app_context():
        assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() == 0


def test_student_break_modal_hides_destinations_until_they_load(client, app):
    """Only "Done for the day" shows unless attendance.js renders saved destinations."""
    initialize_as_student("chemistry_p1", client, app)

    page = client.get("/student/dashboard")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert '<div id="hallPassDestinationSection" hidden>' in html
    assert "doneForDayBreakBtn" in html
