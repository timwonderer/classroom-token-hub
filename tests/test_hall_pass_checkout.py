"""
Tests for hall pass checkout and checkin API endpoints.

Ensures that students can check out and check in directly from the dashboard
without using the terminal, with proper limit enforcement.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    Student, Admin, HallPassLog, StudentTeacher, HallPassSettings, TapEvent, ClassEconomy
)
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_hall_pass_checkout_test(client):
    """Create teacher, student, and approved hall pass for testing checkout."""
    # Create teacher
    teacher = Admin(
        username="teacher1",
        totp_secret="secret1"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create student
    salt = get_random_salt()
    student = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt,
        username_hash=hash_username("alice_a", salt),
        pin_hash="$2b$12$test_hash"  # Mock hash
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teacher
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()

    # Create hall pass settings
    settings = HallPassSettings(
        teacher_id=teacher.id,
        queue_enabled=True,
        queue_limit=10,
        pass_types=[
            {"name": "Bathroom", "queue_limit": None, "simultaneous_limit": 2, "enabled": True},
            {"name": "Office", "queue_limit": None, "simultaneous_limit": None, "enabled": True}
        ]
    )
    db.session.add(settings)
    db.session.commit()

    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code="TEST123",
        display_name='Test Hall Pass Class',
        status='active',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()

    # Create approved hall pass
    now = datetime.now(timezone.utc)
    hall_pass = HallPassLog(
        student_id=student.id,
        reason="Bathroom",
        status="approved",
        period="Period1",
        pass_number="A01",
        request_time=now - timedelta(minutes=10),
        decision_time=now - timedelta(minutes=5),
        join_code="TEST123"
    )
    db.session.add(hall_pass)
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'hall_pass': hall_pass,
        'settings': settings
    }


def test_checkout_with_approved_pass(client, setup_hall_pass_checkout_test):
    """Test that student can check out with an approved hall pass."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    hall_pass = data['hall_pass']

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Checkout
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'Bathroom' in json_data['message']

    # Verify status changed to 'left'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'left'
    assert hall_pass.left_time is not None

    # Verify tap event was created
    tap_event = TapEvent.query.filter_by(
        student_id=student.id,
        status='inactive',
        reason='Bathroom'
    ).first()
    assert tap_event is not None


def test_checkout_blocked_by_simultaneous_limit(client, setup_hall_pass_checkout_test):
    """Test that checkout is blocked when simultaneous limit is reached."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    hall_pass = data['hall_pass']

    # Create 2 other students already out for bathroom (limit is 2)
    for i in range(2):
        salt = get_random_salt()
        other_student = Student(
            first_name=f"Student{i}",
            last_initial="S",
            block="Period1",
            salt=salt,
            username_hash=hash_username(f"student{i}_s", salt)
        )
        db.session.add(other_student)
        db.session.commit()

        # Create 'left' hall pass for this student
        now = datetime.now(timezone.utc)
        other_pass = HallPassLog(
            student_id=other_student.id,
            reason="Bathroom",
            status="left",
            period="Period1",
            pass_number=f"B0{i}",
            request_time=now - timedelta(minutes=15),
            decision_time=now - timedelta(minutes=10),
            left_time=now - timedelta(minutes=5),
            join_code="TEST123"
        )
        db.session.add(other_pass)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to checkout (should fail due to limit)
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'limit reached' in json_data['message'].lower()

    # Verify status is still 'approved'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'approved'


def test_checkin_with_left_pass(client, setup_hall_pass_checkout_test):
    """Test that student can check in when they're currently out."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    hall_pass = data['hall_pass']

    # Set pass to 'left' status
    now = datetime.now(timezone.utc)
    hall_pass.status = 'left'
    hall_pass.left_time = now - timedelta(minutes=5)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Checkin
    response = client.post('/api/hall-pass/checkin',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'checked in' in json_data['message'].lower()

    # Verify status changed to 'returned'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'returned'
    assert hall_pass.return_time is not None

    # Verify tap event was created
    tap_event = TapEvent.query.filter_by(
        student_id=student.id,
        status='active',
        reason='Returned from hall pass'
    ).first()
    assert tap_event is not None


def test_checkout_requires_authentication(client, setup_hall_pass_checkout_test):
    """Test that checkout requires student to be logged in."""
    data = setup_hall_pass_checkout_test
    hall_pass = data['hall_pass']

    # Try to checkout without login
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    # Should redirect to login or return 401
    assert response.status_code in [302, 401]


def test_checkout_rejects_wrong_student(client, setup_hall_pass_checkout_test):
    """Test that student cannot check out another student's pass."""
    data = setup_hall_pass_checkout_test
    hall_pass = data['hall_pass']

    # Create another student
    salt = get_random_salt()
    other_student = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt,
        username_hash=hash_username("bob_b", salt)
    )
    db.session.add(other_student)
    db.session.commit()

    # Login as other student
    with client.session_transaction() as sess:
        sess['student_id'] = other_student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to checkout Alice's pass
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'unauthorized' in json_data['message'].lower()


def test_checkout_rejects_non_approved_pass(client, setup_hall_pass_checkout_test):
    """Test that checkout fails if pass is not in approved status."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    hall_pass = data['hall_pass']

    # Set pass to 'pending' status
    hall_pass.status = 'pending'
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to checkout
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'not approved' in json_data['message'].lower()


def test_checkin_rejects_non_left_pass(client, setup_hall_pass_checkout_test):
    """Test that checkin fails if pass is not in left status."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    hall_pass = data['hall_pass']

    # Pass is still in 'approved' status
    assert hall_pass.status == 'approved'

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['is_student'] = True
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to checkin
    response = client.post('/api/hall-pass/checkin',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'not currently checked out' in json_data['message'].lower()
