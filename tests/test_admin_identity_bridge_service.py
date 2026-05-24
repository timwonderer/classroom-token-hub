from __future__ import annotations

from app.extensions import db
from app.services.admin_identity_bridge_service import (
    admin_has_passkeys,
    count_active_admin_invite_codes,
    create_admin_credential,
    create_admin_invite_code,
    create_legacy_completed_teacher_onboarding,
    delete_admin_credential,
    delete_admin_credentials_for_teacher,
    delete_teacher_onboarding_for_teacher,
    get_admin_credential,
    get_admin_invite_code_by_code,
    get_admin_invite_code_by_id,
    get_or_create_teacher_onboarding,
    get_teacher_onboarding,
    list_admin_invite_codes,
    mark_admin_invite_code_used,
    list_admin_credentials,
    set_teacher_onboarding_skipped,
    set_teacher_onboarding_widget_dismissed,
    set_teacher_onboarding_widget_task_status,
    touch_admin_credentials_last_used,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _seed_teacher():
    teacher = make_admin("admin-identity-bridge", "test-secret")
    db.session.add(teacher)
    db.session.flush()
    return teacher


def test_onboarding_bridge_create_and_updates(client):
    teacher = _seed_teacher()
    now = utc_now()

    assert get_teacher_onboarding(teacher.id) is None

    created = get_or_create_teacher_onboarding(teacher.id, now)
    assert created.teacher_id == teacher.id
    assert created.is_completed is False
    assert created.is_skipped is False
    assert created.steps_completed == {}
    assert created.widget_tasks_completed == {}

    set_teacher_onboarding_widget_task_status(teacher.id, "store", "skipped", utc_now())
    set_teacher_onboarding_widget_dismissed(teacher.id, dismissed=True, now=utc_now())
    set_teacher_onboarding_widget_dismissed(teacher.id, dismissed=False, now=utc_now())
    set_teacher_onboarding_skipped(teacher.id, utc_now())
    db.session.commit()

    refreshed = get_teacher_onboarding(teacher.id)
    assert refreshed is not None
    assert refreshed.widget_tasks_completed.get("store") == "skipped"
    assert refreshed.widget_dismissed is False
    assert refreshed.widget_dismissed_at is None
    assert refreshed.is_skipped is True


def test_onboarding_bridge_legacy_completed_create(client):
    teacher = _seed_teacher()
    completed = create_legacy_completed_teacher_onboarding(teacher.id, utc_now())
    db.session.commit()

    assert completed.teacher_id == teacher.id
    assert completed.is_completed is True
    assert completed.is_skipped is True
    assert completed.completed_at is not None


def test_admin_credential_bridge_lifecycle(client):
    teacher = _seed_teacher()
    assert admin_has_passkeys(teacher.id) is False

    created = create_admin_credential(teacher.id, authenticator_name="My Passkey")
    db.session.flush()

    assert created.teacher_id == teacher.id
    assert admin_has_passkeys(teacher.id) is True

    listed = list_admin_credentials(teacher.id)
    assert len(listed) == 1
    assert listed[0].id == created.id
    assert listed[0].authenticator_name == "My Passkey"

    fetched = get_admin_credential(created.id, teacher.id)
    assert fetched is not None
    assert fetched.id == created.id

    touched = touch_admin_credentials_last_used(teacher.id, utc_now())
    assert touched == 1

    deleted = delete_admin_credential(created.id, teacher.id)
    assert deleted is True
    db.session.flush()
    assert admin_has_passkeys(teacher.id) is False


def test_admin_identity_bridge_bulk_deletes(client):
    teacher = _seed_teacher()
    now = utc_now()
    get_or_create_teacher_onboarding(teacher.id, now)
    create_admin_credential(teacher.id, authenticator_name="Key 1")
    create_admin_credential(teacher.id, authenticator_name="Key 2")
    db.session.flush()

    delete_admin_credentials_for_teacher(teacher.id)
    delete_teacher_onboarding_for_teacher(teacher.id)
    db.session.commit()

    assert admin_has_passkeys(teacher.id) is False
    assert get_teacher_onboarding(teacher.id) is None


def test_admin_invite_code_bridge_lifecycle(client):
    assert count_active_admin_invite_codes() == 0

    invite = create_admin_invite_code("test-code", expires_at=utc_now())
    db.session.flush()

    assert invite.code == "test-code"
    assert invite.used is False
    assert count_active_admin_invite_codes() == 1

    listed = list_admin_invite_codes()
    assert len(listed) == 1
    assert listed[0].id == invite.id

    by_id = get_admin_invite_code_by_id(invite.id)
    by_code = get_admin_invite_code_by_code("test-code")
    assert by_id is not None and by_id.id == invite.id
    assert by_code is not None and by_code.id == invite.id

    marked = mark_admin_invite_code_used(invite.id)
    db.session.commit()
    assert marked is True
    assert count_active_admin_invite_codes() == 0

    refreshed = get_admin_invite_code_by_id(invite.id)
    assert refreshed is not None
    assert refreshed.used is True
