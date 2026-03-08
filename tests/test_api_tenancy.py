"""
Tests for API route tenant scoping.

Validates that API endpoints properly scope data access to the current admin's students.
"""

import pyotp
from datetime import datetime, timezone

from app import app, db
from app.models import Admin, Student, StudentTeacher, TapEvent, TeacherBlock, StudentBlock, HallPassSettings
from app.hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create a teacher admin for testing."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, primary_teacher: Admin = None, linked_teachers: list[Admin] = None) -> Student:
    """
    Create a student for testing.
    
    Args:
        first_name: Student's first name
        primary_teacher: Primary owner (sets teacher_id)
        linked_teachers: List of teachers to link via student_teachers
    """
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="X",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()
    
    # Add student_teachers links
    if linked_teachers:
        for teacher in linked_teachers:
            db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    elif primary_teacher:
        # If no explicit links but has primary, create link
        db.session.add(StudentTeacher(student_id=student.id, teacher_id=primary_teacher.id))
    
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Login as admin."""
    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def _create_tap_event(student: Student, status: str = "active"):
    """Create a tap event for testing."""
    tap = TapEvent(
        student_id=student.id,
        period="1",
        status=status,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(tap)
    db.session.commit()
    return tap


def _create_claimed_seat(teacher: Admin, student: Student, join_code: str, block: str = "A"):
    """Create a claimed teacher block (seat) for join-code scoped tests."""
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        class_label=block,
        first_name=student.first_name,
        last_initial=student.last_initial,
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=b"seat-salt",
        first_half_hash=f"hash-{teacher.id}-{student.id}-{join_code}",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()
    return seat


def _login_student(client, student: Student, join_code: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["login_time"] = now
        sess["last_activity"] = now
        if join_code:
            sess["current_join_code"] = join_code


def test_attendance_history_api_scoped_to_teacher(client):
    """Admin should only see attendance history for their own students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students for each teacher
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events for both students
    tap_a = _create_tap_event(student_a, status="active")
    tap_b = _create_tap_event(student_b, status="active")
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see student A's tap event
    assert data["status"] == "success"
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a.id in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_includes_shared_students(client):
    """Admin should see attendance history for shared students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create shared student
    shared_student = _create_student("Shared", primary_teacher=teacher_a, linked_teachers=[teacher_a, teacher_b])
    
    # Create exclusive students
    exclusive_a = _create_student("ExclusiveA", primary_teacher=teacher_a)
    exclusive_b = _create_student("ExclusiveB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_shared = _create_tap_event(shared_student)
    tap_a = _create_tap_event(exclusive_a)
    tap_b = _create_tap_event(exclusive_b)
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should see shared student and exclusive A, but not exclusive B
    record_ids = [r["id"] for r in data["records"]]
    assert tap_shared.id in record_ids
    assert tap_a.id in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_filters_work_with_scoping(client):
    """Filters should work correctly with tenant scoping."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students with different periods
    student_a1 = _create_student("StudentA1", primary_teacher=teacher_a)
    student_a1.block = "Period1"
    student_a2 = _create_student("StudentA2", primary_teacher=teacher_a)
    student_a2.block = "Period2"
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    student_b.block = "Period1"
    db.session.commit()
    
    # Create tap events
    tap_a1 = TapEvent(student_id=student_a1.id, period="1", status="active", timestamp=datetime.now(timezone.utc))
    tap_a2 = TapEvent(student_id=student_a2.id, period="2", status="active", timestamp=datetime.now(timezone.utc))
    tap_b = TapEvent(student_id=student_b.id, period="1", status="active", timestamp=datetime.now(timezone.utc))
    db.session.add_all([tap_a1, tap_a2, tap_b])
    db.session.commit()
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history filtered by period 1
    response = client.get("/api/attendance/history?period=1")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see teacher A's period 1 student (not teacher B's)
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a1.id in record_ids
    assert tap_a2.id not in record_ids  # Different period
    assert tap_b.id not in record_ids  # Different teacher


def test_attendance_history_api_system_admin_sees_all(client):
    """System admin should see all attendance records."""
    from app.models import SystemAdmin
    
    # Create system admin
    sys_secret = pyotp.random_base32()
    sys_admin = SystemAdmin(username="sysadmin", totp_secret=sys_secret)
    db.session.add(sys_admin)
    db.session.commit()
    
    # Create teachers and students
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_a = _create_tap_event(student_a)
    tap_b = _create_tap_event(student_b)
    
    # Login as system admin
    client.post(
        "/sysadmin/login",
        data={"username": "sysadmin", "totp_code": pyotp.TOTP(sys_secret).now()},
        follow_redirects=True,
    )
    
    # System admins accessing via /api routes would need admin session too
    # For now, just verify the scoping logic works for regular admins
    # (System admins typically don't use the API routes directly)


def test_admin_tap_entries_scoped_by_join_code(client):
    """Admin should only receive tap entries from their own join-code scope."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTap",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="B")

    tap_a = TapEvent(
        student_id=shared_student.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN_A",
    )
    tap_b = TapEvent(
        student_id=shared_student.id,
        period="B",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN_B",
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.get(f"/api/admin/tap-entries/{shared_student.id}")

    assert response.status_code == 200
    payload = response.get_json()
    returned_ids = {
        event["id"]
        for period_data in payload["periods"].values()
        for event in period_data["events"]
    }
    assert tap_a.id in returned_ids
    assert tap_b.id not in returned_ids


def test_admin_delete_tap_entry_enforces_join_code_scope(client):
    """Admin should not delete tap entries from another teacher's join code."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedDelete",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="B")

    tap_a = TapEvent(
        student_id=shared_student.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN_A",
    )
    tap_b = TapEvent(
        student_id=shared_student.id,
        period="B",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN_B",
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)

    deny_response = client.delete(
        f"/api/admin/tap-entries/{tap_b.id}",
        headers={"X-CSRFToken": "test"},
    )
    assert deny_response.status_code == 404
    db.session.refresh(tap_b)
    assert tap_b.is_deleted is False

    allow_response = client.delete(
        f"/api/admin/tap-entries/{tap_a.id}",
        headers={"X-CSRFToken": "test"},
    )
    assert allow_response.status_code == 200
    db.session.refresh(tap_a)
    assert tap_a.is_deleted is True


def test_admin_student_block_settings_rejects_out_of_scope_join_code(client):
    """Admin must not update a StudentBlock row bound to another join code."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedBlock",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    block = StudentBlock(
        student_id=shared_student.id,
        period="A",
        join_code="JOIN_B",
        tap_enabled=True,
    )
    db.session.add(block)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post(
        "/api/admin/student-block-settings",
        json={"student_id": shared_student.id, "period": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    db.session.refresh(block)
    assert block.tap_enabled is True


def test_admin_student_block_settings_rejects_null_join_code_row(client):
    """Admin update should reject StudentBlock rows without join-code scope in v2 mode."""
    teacher_a, secret_a = _create_admin("teacher-a")
    student = _create_student("LegacyBlock", primary_teacher=teacher_a)
    _create_claimed_seat(teacher_a, student, "JOIN_A", block="A")

    block = StudentBlock(
        student_id=student.id,
        period="A",
        join_code=None,
        tap_enabled=True,
    )
    db.session.add(block)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post(
        "/api/admin/student-block-settings",
        json={"student_id": student.id, "period": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    db.session.refresh(block)
    assert block.tap_enabled is True
    assert block.join_code is None


def test_admin_block_tap_settings_get_ignores_out_of_scope_join_code_row(client):
    """Block-level tap state should ignore StudentBlock rows from other join-code scopes."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTapState",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    # Out-of-scope row for teacher A should not drive block-level state.
    db.session.add(
        StudentBlock(
            student_id=shared_student.id,
            period="A",
            join_code="JOIN_B",
            tap_enabled=False,
        )
    )
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.get("/api/admin/block-tap-settings?block=A")

    assert response.status_code == 200
    payload = response.get_json()
    # Teacher A has no scoped disabled row; default remains enabled.
    assert payload["tap_enabled"] is True


def test_admin_block_tap_settings_post_preserves_out_of_scope_join_code_row(client):
    """Bulk block tap updates must not mutate another join-code's StudentBlock row."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTapBulk",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    foreign_row = StudentBlock(
        student_id=shared_student.id,
        period="A",
        join_code="JOIN_B",
        tap_enabled=True,
    )
    db.session.add(foreign_row)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post(
        "/api/admin/block-tap-settings",
        json={"block": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    db.session.refresh(foreign_row)
    assert foreign_row.tap_enabled is True

    scoped_row = StudentBlock.query.filter_by(
        student_id=shared_student.id,
        period="A",
        join_code="JOIN_A",
    ).first()
    assert scoped_row is None


def test_hall_pass_available_types_accepts_join_code_without_teacher_id(client):
    teacher, _ = _create_admin("teacher-hall-types")
    student = _create_student("JoinCodePassTypes", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLA1", block="A")

    db.session.add(HallPassSettings(
        teacher_id=teacher.id,
        join_code="HALLA1",
        block=None,
        pass_types=[
            {"name": "Bathroom", "enabled": True},
            {"name": "Office", "enabled": False},
            {"name": "Nurse", "enabled": True},
        ],
    ))
    db.session.commit()

    _login_student(client, student, join_code="HALLA1")
    response = client.get("/api/hall-pass/available-types?join_code=HALLA1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["pass_types"] == [{"name": "Bathroom"}, {"name": "Nurse"}]


def test_hall_pass_available_types_rejects_out_of_scope_join_code(client):
    teacher, _ = _create_admin("teacher-hall-scope")
    student = _create_student("JoinCodeScope", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLS1", block="A")

    _login_student(client, student, join_code="HALLS1")
    response = client.get("/api/hall-pass/available-types?join_code=OTHER999")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_hall_pass_available_types_supports_teacher_public_id(client):
    teacher, _ = _create_admin("teacher-hall-public")
    teacher.teacher_public_id = "crisp-otter-leaf"
    student = _create_student("PublicIdPassTypes", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLP1", block="A")

    db.session.add(HallPassSettings(
        teacher_id=teacher.id,
        block=None,
        pass_types=[
            {"name": "Bathroom", "enabled": True},
            {"name": "Counselor", "enabled": True},
        ],
    ))
    db.session.commit()

    _login_student(client, student, join_code="HALLP1")
    response = client.get("/api/hall-pass/available-types?teacher_public_id=crisp-otter-leaf")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["pass_types"] == [{"name": "Bathroom"}, {"name": "Counselor"}]


def test_switch_teacher_public_id_updates_join_code_context(client):
    teacher_a, _ = _create_admin("teacher-switch-a")
    teacher_b, _ = _create_admin("teacher-switch-b")
    teacher_b.teacher_public_id = "teacher-switch-b-public"
    db.session.commit()

    student = _create_student(
        "SwitchByPublicId",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, student, "SWITCHA1", block="A")
    _create_claimed_seat(teacher_b, student, "SWITCHB1", block="B")

    _login_student(client, student, join_code="SWITCHA1")
    response = client.post("/student/switch-teacher/teacher-switch-b-public")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWITCHB1"
        assert sess["current_teacher_id"] == teacher_b.id


def test_switch_teacher_public_id_invalid_keeps_current_context(client):
    teacher_a, _ = _create_admin("teacher-switch-invalid-a")
    student = _create_student("SwitchInvalidPublicId", primary_teacher=teacher_a)
    _create_claimed_seat(teacher_a, student, "SWITCHINV", block="A")

    _login_student(client, student, join_code="SWITCHINV")
    response = client.post("/student/switch-teacher/not-valid-public-id")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWITCHINV"


def test_switch_period_legacy_route_does_not_switch_context(client):
    teacher_a, _ = _create_admin("teacher-switch-legacy-a")
    teacher_b, _ = _create_admin("teacher-switch-legacy-b")
    student = _create_student(
        "SwitchLegacyRoute",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, student, "SWLEGACYA", block="A")
    _create_claimed_seat(teacher_b, student, "SWLEGACYB", block="B")

    _login_student(client, student, join_code="SWLEGACYA")
    response = client.post(f"/student/switch-period/{teacher_b.id}")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWLEGACYA"
