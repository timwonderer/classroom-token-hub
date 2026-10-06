"""A hall pass cannot be issued in a class with no hall-pass settings.

FEAT-PROD-002 §III evaluates the class's ``hall_pass_settings`` before writing a
``hall_pass_logs`` row. Before this fix, a class with the feature turned on but
no settings row fell back to the built-in pass types and recorded
``policy_uuid = 'default'``, a reference that names no policy (DOM-POL-001 §VII).
Production held 14 such logs on 2026-10-06, written as recently as the day
before (docs/ops/audits/RECON_2026-10-06_P0B_PRODUCTION_STATE.md §5.2).

The owner ruled that there is no default policy: approval is refused until the
teacher saves settings, and nothing creates settings on the teacher's behalf.
Per FEAT-PROD-002 §III.A a refused approval rolls back and leaves the request
pending.
"""

import pytest

from app.extensions import db
from app.feats.attendance import save_hall_pass_setup_config
from app.feats.base import FEATContext
from app.feats.hall_pass_request_feat import approve_hall_pass_request
from app.feats.prod import HallPassSettingsMissing
from app.models import EntitlementEvent, HallPassLog, HallPassSettings, PendingAction
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_hall_pass_balance, grant_hall_passes
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
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
    return EntitlementEvent.query.filter_by(class_id=class_id, event_type="CONSUMED").count()


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
