from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from tests.helpers.mock_teacher_block import TeacherBlock
from app.models import Admin, PayrollSettings, Seat, Student, StudentTeacher
from tests.helpers.class_scope import create_class_scope


def test_student_payroll_uses_teacher_block_pay_rate(client):
    teacher = make_admin("teacher_payrate_scope", "secret")
    db.session.add(teacher)
    db.session.flush()

    student = Student(
        first_name="Rate",
        last_initial="S",
        block="A",
        salt=b"salt",
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.flush()

    class_scope = create_class_scope(
        teacher=teacher,
        join_code="RATEA123",
        student=student,
        block="A",
        display_name="Rate Class",
    )
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        join_code="RATEA123",
        class_id=class_scope.class_id,
        student_id=student.id,
        is_claimed=True,
        first_name="Rate",
        last_initial="S",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=b"salt",
        first_half_hash="hash_rate_a",
    )
    db.session.add(
        teacher_block
    )
    db.session.add(
        PayrollSettings(
            teacher_id=teacher.id,
            block="A",
            class_id=class_scope.class_id,
            join_code="RATEA123",
            pay_rate=Decimal("0.50"),
            settings_mode="simple",
            is_active=True,
        )
    )
    db.session.commit()

    seat = Seat.query.filter_by(student_id=student.id, class_id=class_scope.class_id).first()
    assert seat is not None
    seat.claimed_at = datetime.now(timezone.utc)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_seat_id"] = seat.id
        sess["current_class_id"] = class_scope.class_id
        sess["current_join_code"] = "RATEA123"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    resp = client.get("/student/payroll")
    assert resp.status_code == 200
    assert b"Current Pay Rate:</strong> $0.50 per minute" in resp.data
    assert b"$0.25 per minute" not in resp.data
