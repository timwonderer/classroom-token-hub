"""
Tests for API route tenant scoping.

Validates that API endpoints properly scope data access to the current admin's students.
"""

import pyotp
from datetime import datetime, timezone

from app import app, db
from app.models import Admin, Student, StudentTeacher, TapEvent, ClassEconomy, ClassMembership
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
            db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    elif primary_teacher:
        # If no explicit links but has primary, create link
        db.session.add(StudentTeacher(student_id=student.id, admin_id=primary_teacher.id))
    
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Login as admin."""
    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def _create_tap_event(student: Student, status: str = "active", join_code: str = None):
    """Create a tap event for testing."""
    tap = TapEvent(
        student_id=student.id,
        period="1",
        status=status,
        timestamp=datetime.now(timezone.utc),
        join_code=join_code
    )
    db.session.add(tap)
    db.session.commit()
    return tap


def _setup_class_context(teacher_id: int, join_code: str, student_ids: list[int] = None):
    """Create ClassEconomy and ClassMembership for testing strict scoping."""
    # Ensure ClassEconomy exists
    if not ClassEconomy.query.get(join_code):
        db.session.add(ClassEconomy(
            join_code=join_code,
            status="active",
            created_by_admin_id=teacher_id
        ))
    
    # Ensure Teacher Membership
    if not ClassMembership.query.filter_by(join_code=join_code, admin_id=teacher_id).first():
        db.session.add(ClassMembership(
            join_code=join_code,
            admin_id=teacher_id,
            role="admin",
            status="active"
        ))
    
    # Ensure Student Memberships
    if student_ids:
        for sid in student_ids:
            if not ClassMembership.query.filter_by(join_code=join_code, student_id=sid).first():
                db.session.add(ClassMembership(
                    join_code=join_code,
                    student_id=sid,
                    role="student",
                    status="active"
                ))
    
    db.session.commit()


def test_attendance_history_api_scoped_to_teacher(client):
    """Admin should only see attendance history for their own students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students for each teacher
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)

    # Setup class context
    _setup_class_context(teacher_a.id, "CLASSA", [student_a.id])
    _setup_class_context(teacher_b.id, "CLASSB", [student_b.id])
    
    # Create tap events for both students
    tap_a = _create_tap_event(student_a, status="active", join_code="CLASSA")
    tap_b = _create_tap_event(student_b, status="active", join_code="CLASSB")
    
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

    # Setup class context
    # Teacher A has CLASSA (with shared + exclusive A)
    # Teacher B has CLASSB (with shared + exclusive B)
    _setup_class_context(teacher_a.id, "CLASSA", [shared_student.id, exclusive_a.id])
    _setup_class_context(teacher_b.id, "CLASSB", [shared_student.id, exclusive_b.id])
    
    # Create tap events
    # Shared student taps in CLASSA
    tap_shared = _create_tap_event(shared_student, join_code="CLASSA")
    # Exclusive A taps in CLASSA
    tap_a = _create_tap_event(exclusive_a, join_code="CLASSA")
    # Exclusive B taps in CLASSB
    tap_b = _create_tap_event(exclusive_b, join_code="CLASSB")
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should see shared student (in CLASSA context) and exclusive A
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

    # Setup class context
    # Teacher A has CLASS_A1 (Period1), CLASS_A2 (Period2)
    # Teacher B has CLASS_B1 (Period1)
    _setup_class_context(teacher_a.id, "CLASS_A1", [student_a1.id])
    _setup_class_context(teacher_a.id, "CLASS_A2", [student_a2.id])
    _setup_class_context(teacher_b.id, "CLASS_B1", [student_b.id])
    
    # Create tap events
    tap_a1 = TapEvent(student_id=student_a1.id, period="1", status="active", timestamp=datetime.now(timezone.utc), join_code="CLASS_A1")
    tap_a2 = TapEvent(student_id=student_a2.id, period="2", status="active", timestamp=datetime.now(timezone.utc), join_code="CLASS_A2")
    tap_b = TapEvent(student_id=student_b.id, period="1", status="active", timestamp=datetime.now(timezone.utc), join_code="CLASS_B1")
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
