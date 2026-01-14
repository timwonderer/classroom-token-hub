import pytest
from app import app, db, Student, TapEvent, Transaction
from app.payroll import calculate_payroll
from datetime import datetime, timedelta, timezone

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_calculate_payroll(client):
    from app.models import Admin, TeacherBlock, Student
    
    # Create Teacher
    teacher = Admin(username="prof_payroll", totp_secret="s")
    db.session.add(teacher)
    db.session.commit()

    # Create a student
    student = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=b'salt',
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()
    
    # CRITICAL: Link Student to Teacher/Class for Payroll Scoping
    # Payroll now strictly requires a claimed TeacherBlock (join_code)
    tb = TeacherBlock(
        teacher_id=teacher.id,
        student_id=student.id,
        block="A",
        join_code="JOIN123",
        is_claimed=True,
        first_name="Test",
        last_initial="S",
        last_name_hash_by_part=['mock_hash'],
        first_half_hash='hash123',
        salt=b's',
        dob_sum=123
    )
    db.session.add(tb)
    db.session.commit()
    
    # Set TapEvent join_code to match
    join_code = "JOIN123"

    # Create TapEvents to simulate attendance
    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=60)
    tap_out_time = now - timedelta(minutes=30)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time, join_code=join_code)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time, join_code=join_code)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    # Calculate payroll
    students = [student]
    last_payroll_time = now - timedelta(days=1)
    payroll_summary = calculate_payroll(students, last_payroll_time)

    # Assert the payroll amount is correct
    # 30 minutes of attendance = 1800 seconds
    # 1800 seconds * ($0.25 / 60 seconds) = $7.50
    expected_payroll = 7.50
    assert student.id in payroll_summary
    assert payroll_summary[student.id] == expected_payroll

    # Test case with no attendance
    # NOTE: student2 intentionally has no StudentTeacher link and no TeacherBlock
    # to verify proper skipping behavior in calculate_payroll. Students without
    # these associations should be skipped during payroll processing.
    student2 = Student(first_name="Test2", last_initial="S", block="B", salt=b'salt2', has_completed_setup=True)
    db.session.add(student2)
    db.session.commit()
    # Need to link student2 to avoid skipping?
    # Actually if student2 has NO attendance, payroll is 0 anyway or empty dict.
    # But if no TeacherBlock, it is skipped even before checking attendance.
    # We want to verify that student2 is NOT in summary.
    
    students2 = [student2]
    payroll_summary2 = calculate_payroll(students2, last_payroll_time)
    assert student2.id not in payroll_summary2

    # Manual payments after the last payroll should clear projected pay for that student
    manual_time = now - timedelta(minutes=5)
    manual_tx = Transaction(student_id=student.id, amount=3, type="manual_payment", timestamp=manual_time, join_code=join_code)
    db.session.add(manual_tx)
    db.session.commit()

    post_manual_summary = calculate_payroll(students, last_payroll_time)
    assert post_manual_summary == {}