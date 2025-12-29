from datetime import datetime, timezone
import os

from werkzeug.security import generate_password_hash

from app.models import Admin, Student, TeacherBlock, RentSettings
from app.extensions import db
from hash_utils import get_random_salt, hash_username


def test_dashboard_handles_rent_with_multi_block_student(client):
    """Dashboard should render when rent is enabled for a multi-block student."""

    teacher = Admin(username="rent_teacher", totp_secret="rentsecret")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Rent",
        last_initial="R",
        block="A,B",
        salt=salt,
        username_hash=hash_username("rent_student", salt),
        pin_hash=generate_password_hash("0000"),
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()

    seat_a = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Rent",
        last_initial="R",
        last_name_hash_by_part=["hash_a"],
        dob_sum=2025,
        salt=os.urandom(16),
        first_half_hash="hash_a",
        join_code="JOINA",
        student_id=student.id,
        is_claimed=True,
    )
    seat_b = TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name="Rent",
        last_initial="R",
        last_name_hash_by_part=["hash_b"],
        dob_sum=2025,
        salt=os.urandom(16),
        first_half_hash="hash_b",
        join_code="JOINB",
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add_all([seat_a, seat_b])

    rent_settings = RentSettings(
        teacher_id=teacher.id,
        is_enabled=True,
        bill_preview_enabled=True,
        rent_amount=25.0,
    )
    db.session.add(rent_settings)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        # Ensure the dashboard context points at block B while the student has both A and B
        sess['current_join_code'] = "JOINB"

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    # Block state JSON should include only the current class context (block B) and not error on block A
    assert b'"B"' in response.data
