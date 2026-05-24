from __future__ import annotations

from datetime import timedelta

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.hash_utils import get_random_salt, hash_hmac, hash_username_lookup
from app.models import RecoveryRequest, Student, StudentRecoveryCode, StudentTeacher
from app.services.recovery_bridge_service import (
    dismiss_recovery_code,
    get_pending_recovery_code_for_student,
    get_recovery_code_for_student,
    set_recovery_code_verified,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _seed_teacher_student():
    teacher = make_admin("recovery-bridge", "test-secret")
    db.session.add(teacher)
    db.session.flush()

    student_salt = get_random_salt()
    student = Student(
        first_name="Recover",
        last_initial="S",
        block="A",
        salt=student_salt,
        username_lookup_hash=hash_username_lookup("recover-student"),
        passphrase_hash=generate_password_hash("secret"),
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.flush()
    return teacher, student


def test_pending_recovery_code_for_student_filters_active_pending_request(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        teacher_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        student_id=student.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    pending = get_pending_recovery_code_for_student(student.id, utc_now())
    assert pending is not None
    assert pending.id == code_row.id
    assert pending.student_id == student.id
    assert pending.recovery_request.expires_at == request_row.expires_at


def test_get_recovery_code_for_student_respects_student_scope(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        teacher_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        student_id=student.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    found = get_recovery_code_for_student(code_row.id, student.id)
    not_found = get_recovery_code_for_student(code_row.id, student.id + 999)
    assert found is not None
    assert found.id == code_row.id
    assert not_found is None


def test_recovery_code_verify_and_dismiss_updates_rows(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        teacher_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        student_id=student.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    verified_at = utc_now()
    set_recovery_code_verified(code_row.id, hash_hmac(b"123456", b""), verified_at)
    dismiss_recovery_code(code_row.id)
    db.session.commit()

    refreshed = db.session.get(StudentRecoveryCode, code_row.id)
    assert refreshed is not None
    assert refreshed.code_hash is not None
    assert refreshed.verified_at == verified_at
    assert refreshed.dismissed is True
