from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app import db, Student, TapEvent, Transaction
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    calculate_period_attendance,
    get_session_status,
    get_all_block_statuses
)
from datetime import datetime, timedelta, timezone


def _attach_student_to_class(student, join_code="ATTEND1", block="A"):
    from app.models import Admin, TeacherBlock, StudentTeacher, User, Seat
    from tests.helpers.class_scope import create_class_scope

    teacher = make_admin(f"teacher_{join_code}_{student.id or 'new'}", "s")
    db.session.add(teacher)
    db.session.flush()

    class_economy = create_class_scope(
        teacher=teacher,
        join_code=join_code,
        student=student,
        block=block,
        display_name=block,
    )
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    user = User(
        username=f"user_{join_code}_{student.id}",
        password_hash="hash",
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(
        TeacherBlock(
            teacher_id=teacher.id,
            student_id=student.id,
            block=block,
            join_code=join_code,
            class_id=class_economy.class_id,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=None,
            first_half_hash=f"hash-{join_code}-{block}",
            salt=b's',
            dob_sum_hash=None,
        )
    )
    db.session.add(
        Seat(
            user_id=user.id,
            student_id=student.id,
            join_code=join_code,
            block=block,
        )
    )
    db.session.commit()
    return join_code

def test_get_last_payroll_time(client):
    # Test with no payroll transactions
    assert get_last_payroll_time() is None

    # Create a student first to satisfy foreign key constraint
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    # Test with a payroll transaction
    now = datetime.now(timezone.utc)
    tx = Transaction(student_id=student.id, amount=10, type="payroll", timestamp=now)
    db.session.add(tx)
    db.session.commit()
    assert get_last_payroll_time() == now

    # Manual payments should only change the per-student anchor
    manual_time = now + timedelta(hours=1)
    manual_tx = Transaction(student_id=student.id, amount=5, type="manual_payment", timestamp=manual_time)
    db.session.add(manual_tx)
    db.session.commit()

    assert get_last_payroll_time() == now
    assert get_last_payroll_time(student_id=student.id) == manual_time

    # Class-scoped anchors must ignore payroll/manual payment activity from other classes
    other_join_time = manual_time + timedelta(hours=1)
    other_join_tx = Transaction(
        student_id=student.id,
        amount=7,
        type="payroll",
        timestamp=other_join_time,
        join_code="OTHER",
    )
    db.session.add(other_join_tx)
    db.session.commit()

    assert get_last_payroll_time(join_code="OTHER") == other_join_time
    assert get_last_payroll_time(student_id=student.id, join_code="OTHER") == other_join_time
    assert get_last_payroll_time(student_id=student.id, join_code="MISSING") is None

def test_calculate_unpaid_attendance_seconds(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()
    join_code = _attach_student_to_class(student, join_code="ATTEND2", block="A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=30)
    tap_out_time = now - timedelta(minutes=15)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time, join_code=join_code)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time, join_code=join_code)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    last_payroll_time = now - timedelta(days=1)
    unpaid_seconds = calculate_unpaid_attendance_seconds(student.id, "A", last_payroll_time, join_code=join_code)

    # 15 minutes of attendance = 900 seconds
    assert unpaid_seconds == 900

def test_calculate_period_attendance(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    now = datetime.now(timezone.utc)
    today = now.date()
    tap_in_time = now - timedelta(minutes=20)
    tap_out_time = now - timedelta(minutes=10)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    period_attendance = calculate_period_attendance(student.id, "A", today)

    # 10 minutes of attendance = 600 seconds
    assert period_attendance == 600

def test_get_session_status(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()
    join_code = _attach_student_to_class(student, join_code="ATTEND3", block="A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=5)
    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time, join_code=join_code)
    db.session.add(tap_in)
    db.session.commit()

    is_active, done, duration = get_session_status(student.id, "A")
    assert is_active is True
    assert done is False
    assert duration > 0

def test_get_all_block_statuses(client):
    student = Student(first_name="Test", last_initial="S", block="A,B", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()
    join_code_a = _attach_student_to_class(student, join_code="ATTEND4", block="A")
    _attach_student_to_class(student, join_code="ATTEND5", block="B")

    now = datetime.now(timezone.utc)
    tap_in_time_a = now - timedelta(minutes=10)
    tap_in_a = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time_a, join_code=join_code_a)
    db.session.add(tap_in_a)
    db.session.commit()

    statuses = get_all_block_statuses(student)
    assert "A" in statuses
    assert "B" in statuses
    assert statuses["A"]["active"] is True
    assert statuses["B"]["active"] is False
    assert statuses["A"]["projected_pay"] is None
    assert statuses["B"]["projected_pay"] is None
