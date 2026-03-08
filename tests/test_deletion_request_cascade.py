"""
Tests for sysadmin teacher deletion endpoint behavior.

Teacher account deletions are now self-managed by teachers. These tests ensure
the sysadmin endpoint blocks account deletion attempts and leaves related data
intact.
"""

import pyotp
from datetime import datetime, timezone, timedelta

from app import db
from app.models import Admin, Student, StudentTeacher, SystemAdmin, DeletionRequest, DeletionRequestType, DeletionRequestStatus
from app.hash_utils import get_random_salt, hash_hmac
from app.utils.username_migration import build_hashed_username_fields


def _create_admin(username: str) -> tuple[Admin, str, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    admin = Admin(
        username=None,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
        salt=salt,
        totp_secret=secret,
    )
    db.session.add(admin)
    db.session.commit()
    return admin, secret, username


def _create_sysadmin() -> tuple[SystemAdmin, str, str]:
    """Create a system admin with TOTP authentication."""
    secret = pyotp.random_base32()
    auth_username = "sysadmin_cascade_test"
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(auth_username)
    sysadmin = SystemAdmin(
        username=None,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
        salt=salt,
        totp_secret=secret,
    )
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret, auth_username


def _create_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """Create a student associated with a teacher."""
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
    )
    db.session.add(student)
    db.session.flush()
    
    # Create StudentTeacher link (replaces deprecated teacher_id)
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()
    
    return student


def _login_sysadmin(client, username: str, secret: str):
    """Log in as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_sysadmin_teacher_deletion_is_blocked_preserves_deletion_requests(client):
    """
    Sysadmin delete endpoint should not delete teacher accounts.
    DeletionRequest records must remain intact when deletion is blocked.
    """
    # Create teacher and make them inactive for >6 months (so sysadmin can delete)
    teacher, _, _ = _create_admin("teacher-with-requests")
    teacher.last_login = datetime.now(timezone.utc) - timedelta(days=200)
    db.session.commit()
    
    # Create some students for this teacher
    _create_student("Alice", teacher, block="A")
    _create_student("Bob", teacher, block="B")
    
    # Create multiple deletion requests for this teacher
    period_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.PERIOD,
        period="A",
        reason="Test period deletion",
        status=DeletionRequestStatus.PENDING,
    )
    account_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.ACCOUNT,
        reason="Test account deletion",
        status=DeletionRequestStatus.APPROVED,
    )
    another_period_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.PERIOD,
        period="B",
        status=DeletionRequestStatus.PENDING,
    )
    
    db.session.add_all([period_request, account_request, another_period_request])
    db.session.commit()
    
    period_request_id = period_request.id
    account_request_id = account_request.id
    another_period_request_id = another_period_request.id
    teacher_id = teacher.id
    
    # Create and login as sysadmin
    _, sys_secret, sysadmin_username = _create_sysadmin()
    _login_sysadmin(client, sysadmin_username, sys_secret)
    
    # Sysadmin delete is blocked by policy.
    response = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher_id}",
        follow_redirects=True
    )

    # Endpoint responds with error flash and keeps records untouched.
    assert response.status_code == 200
    assert b"System admins cannot delete teacher accounts" in response.data

    # Verify teacher is preserved
    assert db.session.get(Admin, teacher_id) is not None

    # Verify DeletionRequest records are preserved
    assert db.session.get(DeletionRequest, period_request_id) is not None
    assert db.session.get(DeletionRequest, account_request_id) is not None
    assert db.session.get(DeletionRequest, another_period_request_id) is not None
    
    # Verify no orphaned DeletionRequest records with NULL teacher_id exist
    orphaned_requests = DeletionRequest.query.filter(
        DeletionRequest.teacher_id.is_(None)
    ).all()
    assert len(orphaned_requests) == 0, "Found orphaned DeletionRequest records with NULL teacher_id"


def test_delete_teacher_with_no_deletion_requests(client):
    """
    Verify that the sysadmin delete endpoint cannot remove teachers even when
    they have no DeletionRequest records.
    """
    # Create teacher and make them inactive for >6 months
    teacher, _, _ = _create_admin("teacher-no-requests")
    teacher.last_login = datetime.now(timezone.utc) - timedelta(days=200)
    db.session.commit()
    
    teacher_id = teacher.id
    
    # Create and login as sysadmin
    _, sys_secret, sysadmin_username = _create_sysadmin()
    _login_sysadmin(client, sysadmin_username, sys_secret)
    
    # Sysadmin delete is blocked by policy.
    response = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher_id}",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"System admins cannot delete teacher accounts" in response.data
    assert db.session.get(Admin, teacher_id) is not None
