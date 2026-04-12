from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Student, StudentTeacher, TapEvent


def _login_admin(client, admin_id, join_code):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        sess["current_join_code"] = join_code
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _setup_shared_student_with_split_membership():
    admin_a = make_admin("tap_scope_admin_a", "secret-a")
    admin_b = make_admin("tap_scope_admin_b", "secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    student = Student(first_name="Tap", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    # Shared student-teacher association but student class membership only in TAPB01.
    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=admin_a.id),
        StudentTeacher(student_id=student.id, teacher_id=admin_b.id),
        ClassEconomy(join_code="TAPA01", teacher_id=admin_a.id, status="active", created_by_admin_id=admin_a.id),
        ClassEconomy(join_code="TAPB01", teacher_id=admin_b.id, status="active", created_by_admin_id=admin_b.id),
        ClassMembership(join_code="TAPA01", admin_id=admin_a.id, role="admin"),
        ClassMembership(join_code="TAPB01", admin_id=admin_b.id, role="admin"),
        ClassMembership(join_code="TAPB01", student_id=student.id, role="student"),
    ])
    db.session.flush()

    tap_event = TapEvent(
        student_id=student.id,
        period="A",
        status="active",
        join_code="TAPB01",
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(tap_event)
    db.session.commit()
    return admin_a, admin_b, student, tap_event


def test_get_tap_entries_requires_student_in_current_join_code(client):
    admin_a, admin_b, student, _event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.get(f"/api/admin/tap-entries/{student.id}")
    assert denied.status_code == 404

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.get(f"/api/admin/tap-entries/{student.id}")
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["student_id"] == student.id
    assert "A" in data["periods"]


def test_delete_tap_entry_rejects_cross_join_code_context(client):
    admin_a, admin_b, _student, event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert denied.status_code == 403
    db.session.refresh(event)
    assert event.is_deleted is False

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert allowed.status_code == 200
    db.session.refresh(event)
    assert event.is_deleted is True
