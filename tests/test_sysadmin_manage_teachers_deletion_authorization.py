"""
Regression tests for sysadmin manage-teachers deletion authorization UI state.

Ensures pending teacher deletion requests unlock the corresponding delete actions
even when the teacher is currently active.
"""

import pyotp

from app import db
from app.models import (
    Admin,
    DeletionRequest,
    DeletionRequestStatus,
    DeletionRequestType,
    Student,
    StudentTeacher,
    SystemAdmin,
)
from app.hash_utils import get_random_salt, hash_hmac


def _create_sysadmin(username: str) -> tuple[SystemAdmin, str]:
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username=username, totp_secret=secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def _create_teacher(username: str) -> Admin:
    teacher = Admin(username=username, totp_secret=pyotp.random_base32())
    db.session.add(teacher)
    db.session.commit()
    return teacher


def _create_student_for_teacher(teacher: Admin, block: str = "A", first_name: str = "Alex") -> Student:
    salt = get_random_salt()
    first_half_hash = hash_hmac(b"A2025", salt)
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        dob_sum=2025,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    return student


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str):
    return client.post(
        "/sysadmin/login",
        data={"username": sysadmin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_manage_teachers_shows_account_delete_for_active_teacher_with_request(client):
    teacher = _create_teacher("teacher-account-request")
    req = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.ACCOUNT,
        status=DeletionRequestStatus.PENDING,
        reason="Please delete account",
    )
    db.session.add(req)
    db.session.commit()

    sysadmin, secret = _create_sysadmin("sysadmin-account-request")
    _login_sysadmin(client, sysadmin, secret)

    response = client.get("/sysadmin/manage-teachers")
    assert response.status_code == 200
    html = response.data.decode()

    assert f"/sysadmin/manage-teachers/delete/{teacher.id}" in html


def test_manage_teachers_shows_period_delete_for_active_teacher_with_period_request(client):
    teacher = _create_teacher("teacher-period-request")
    _create_student_for_teacher(teacher, block="A", first_name="Avery")

    req = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.PERIOD,
        period="A",
        status=DeletionRequestStatus.PENDING,
        reason="Please delete period A",
    )
    db.session.add(req)
    db.session.commit()

    sysadmin, secret = _create_sysadmin("sysadmin-period-request")
    _login_sysadmin(client, sysadmin, secret)

    response = client.get("/sysadmin/manage-teachers")
    assert response.status_code == 200
    html = response.data.decode()

    assert f"/sysadmin/delete-period/{teacher.id}/A" in html
