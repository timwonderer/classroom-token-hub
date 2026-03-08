"""
Tests for StudentBlock cleanup during student deletion.

These tests ensure that StudentBlock entries are properly cleaned up
when students are deleted via various routes.
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import (
    Admin,
    Student,
    StudentTeacher,
    StudentBlock,
    TeacherBlock,
    SystemAdmin,
    Transaction,
    IssueCategory,
    Issue,
    IssueResolutionAction,
)
from app.hash_utils import get_random_salt, hash_hmac


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_sysadmin() -> tuple[SystemAdmin, str]:
    """Create a system admin with TOTP authentication."""
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username="sysadmin", totp_secret=secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def _create_student_with_student_block(first_name: str, teacher: Admin, block: str = "A", period: str = "1") -> tuple[Student, StudentBlock]:
    """Create a student with an associated StudentBlock entry."""
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
    
    # Create StudentTeacher link
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))

    join_code = f"JOIN{teacher.id}{block}"
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=first_name[0].upper(),
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=join_code,
        is_claimed=True,
        student_id=student.id,
    ))
    
    # Create StudentBlock entry
    student_block = StudentBlock(
        student_id=student.id,
        period=period,
        join_code=join_code,
        tap_enabled=True,
    )
    db.session.add(student_block)
    db.session.commit()
    
    return student, student_block


def _login_admin(client, admin: Admin, secret: str):
    """Log in as admin."""
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


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str):
    """Log in as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": sysadmin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_delete_student_removes_student_and_student_block(client):
    """Deleting an unshared student should remove both student and StudentBlock rows."""
    teacher, secret = _create_admin("teacher-cleanup")
    student, student_block = _create_student_with_student_block("Alice", teacher)
    
    student_id = student.id
    student_block_id = student_block.id
    
    _login_admin(client, teacher, secret)
    
    # Delete the student
    response = client.post(
        "/admin/student/delete",
        data={"student_id": student_id, "confirmation": "DELETE"},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    # Verify student is deleted
    assert db.session.get(Student, student_id) is None

    # Verify StudentBlock is deleted with the student
    assert db.session.get(StudentBlock, student_block_id) is None


def test_bulk_delete_students_removes_students_and_student_blocks(client):
    """Bulk delete should remove students and StudentBlock rows."""
    teacher, secret = _create_admin("teacher-bulk")
    student1, sb1 = _create_student_with_student_block("Alice", teacher, period="1")
    student2, sb2 = _create_student_with_student_block("Bob", teacher, period="2")
    
    student1_id = student1.id
    student2_id = student2.id
    sb1_id = sb1.id
    sb2_id = sb2.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete students
    response = client.post(
        "/admin/students/bulk-delete",
        json={
            "student_ids": [student1_id, student2_id],
            "gate_phrase": "DELETE STUDENTS",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify students are deleted
    assert db.session.get(Student, student1_id) is None
    assert db.session.get(Student, student2_id) is None

    # Verify StudentBlocks are deleted with students
    assert db.session.get(StudentBlock, sb1_id) is None
    assert db.session.get(StudentBlock, sb2_id) is None


def test_delete_block_removes_student_blocks(client):
    """When a block is deleted, all StudentBlock entries for students in that block should be removed."""
    teacher, secret = _create_admin("teacher-block-del")
    student1, sb1 = _create_student_with_student_block("Alice", teacher, block="X", period="1")
    student2, sb2 = _create_student_with_student_block("Bob", teacher, block="X", period="2")
    
    sb1_id = sb1.id
    sb2_id = sb2.id
    
    _login_admin(client, teacher, secret)
    
    # Delete the block
    response = client.post(
        "/admin/students/delete-block",
        json={
            "block": "X",
            "gate_phrase": "DELETE BLOCK X",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify all StudentBlocks for students in block X are deleted
    assert db.session.get(StudentBlock, sb1_id) is None
    assert db.session.get(StudentBlock, sb2_id) is None


def test_bulk_delete_legacy_unclaimed_deletes_students(client):
    """Legacy unclaimed bulk deletion route should remove students fully."""
    teacher, secret = _create_admin("teacher-legacy")
    
    # Create a legacy unclaimed student (username_hash = None)
    salt = get_random_salt()
    credential = "C2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    student = Student(
        first_name="Charlie",
        last_initial="C",
        block="Z",
        salt=salt,
        first_half_hash=first_half_hash,
        username_hash=None,  # Legacy unclaimed - no username_hash
    )
    db.session.add(student)
    db.session.flush()
    
    # Create StudentTeacher link
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    
    # Create StudentBlock for this student
    student_block = StudentBlock(
        student_id=student.id,
        period="1",
        tap_enabled=True,
    )
    db.session.add(student_block)
    db.session.commit()
    
    student_id = student.id
    student_block_id = student_block.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete legacy unclaimed students in block Z
    response = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={"block": "Z"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify student is deleted
    assert db.session.get(Student, student_id) is None

    # Verify StudentBlock is deleted
    assert db.session.get(StudentBlock, student_block_id) is None


def test_sysadmin_delete_admin_removes_student_blocks(client):
    """When sysadmin deletes an admin, StudentBlock entries for their exclusive students should be removed."""
    teacher, _ = _create_admin("teacher-to-delete")
    sysadmin, sys_secret = _create_sysadmin()
    
    # Make teacher inactive so sysadmin can delete without request
    teacher.last_login = None
    db.session.commit()
    
    teacher_id = teacher.id
    
    student1, sb1 = _create_student_with_student_block("Alice", teacher, block="A", period="1")
    student2, sb2 = _create_student_with_student_block("Bob", teacher, block="B", period="2")
    sb1_id = sb1.id
    sb2_id = sb2.id
    
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Delete the teacher (which should delete their exclusive students)
    response = client.post(
        f"/sysadmin/admins/{teacher_id}/delete",
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    # Verify StudentBlocks are deleted
    assert db.session.get(StudentBlock, sb1_id) is None
    assert db.session.get(StudentBlock, sb2_id) is None


def test_delete_student_clears_cross_issue_transaction_references(client):
    """Deleting a student should null cross-issue tx refs and remove student tx rows."""
    teacher, secret = _create_admin("teacher-issue-fk")
    student_to_delete, _ = _create_student_with_student_block("Alice", teacher, period="1")
    reporter_student, _ = _create_student_with_student_block("Riley", teacher, period="2")

    tx = Transaction(
        student_id=student_to_delete.id,
        teacher_id=teacher.id,
        amount=25,
        account_type="checking",
        description="Seed transaction for FK regression",
        join_code="JOIN1",
    )
    db.session.add(tx)
    db.session.flush()

    category = IssueCategory(
        name=f"Transaction Test Category {teacher.id}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    issue = Issue(
        student_id=reporter_student.id,
        student_first_name=reporter_student.first_name,
        student_last_initial=reporter_student.last_initial,
        opaque_student_reference="opaque-ref-123",
        teacher_id=teacher.id,
        join_code="JOIN1",
        category_id=category.id,
        issue_type="transaction",
        student_explanation="Transaction appears wrong",
        related_transaction_id=tx.id,
    )
    db.session.add(issue)
    db.session.flush()

    action = IssueResolutionAction(
        issue_id=issue.id,
        action_type="manual_adjustment",
        performed_by_type="teacher",
        performed_by_id=teacher.id,
        related_transaction_id=tx.id,
    )
    db.session.add(action)
    db.session.commit()

    issue_id = issue.id
    action_id = action.id
    deleted_student_id = student_to_delete.id
    tx_id = tx.id

    _login_admin(client, teacher, secret)
    response = client.post(
        "/admin/student/delete",
        data={"student_id": deleted_student_id, "confirmation": "DELETE"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    assert db.session.get(Student, deleted_student_id) is None
    assert db.session.get(Transaction, tx_id) is None

    refreshed_issue = db.session.get(Issue, issue_id)
    refreshed_action = db.session.get(IssueResolutionAction, action_id)
    assert refreshed_issue is not None
    assert refreshed_action is not None
    assert refreshed_issue.related_transaction_id is None
    assert refreshed_action.related_transaction_id is None
