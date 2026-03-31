from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import Admin, PayrollSettings, Student, StudentTeacher, TeacherBlock, ClassEconomy


def test_student_payroll_uses_teacher_block_pay_rate(client):
    teacher = Admin(username="teacher_payrate_scope", totp_secret="secret")
    db.session.add(teacher)
    db.session.flush()

    # Create ClassEconomy to satisfy FK
    economy = ClassEconomy(join_code="RATEA123", teacher_id=teacher.id, status="active")
    db.session.add(economy)
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

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.add(
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            join_code="RATEA123",
            student_id=student.id,
            is_claimed=True,
            first_name="Rate",
            last_initial="S",
            last_name_hash_by_part=None,
            dob_sum_hash=None,
            salt=b"salt",
            first_half_hash="hash_rate_a",
        )
    )
    db.session.add(
        PayrollSettings(
            teacher_id=teacher.id,
            block="A",
            join_code="RATEA123",
            pay_rate=Decimal("0.50"),
            settings_mode="simple",
            is_active=True,
        )
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_join_code"] = "RATEA123"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    resp = client.get("/student/payroll")
    assert resp.status_code == 200
    assert b"Current Pay Rate:</strong> $0.50 per minute" in resp.data
    assert b"$0.25 per minute" not in resp.data
