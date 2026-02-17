"""
Tests for hall pass queue API endpoint scoping.

Ensures that the /api/hall-pass/queue endpoint properly scopes
hall pass data by join_code membership to prevent cross-tenant leakage.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    Student, Admin, HallPassLog, StudentTeacher, HallPassSettings
)
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from app.models import ClassEconomy, ClassMembership


@pytest.fixture
def setup_multi_teacher_hall_passes(client):
    """Create two teachers with students and hall passes for testing scoping."""
    # Create two teachers
    teacher1 = Admin(
        username="teacher1",
        totp_secret="secret1"
    )
    teacher2 = Admin(
        username="teacher2",
        totp_secret="secret2"
    )
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.commit()

    # Create students for teacher1
    salt1 = get_random_salt()
    student1 = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt1,
        username_hash=hash_username("alice_a", salt1)
    )
    
    salt2 = get_random_salt()
    student2 = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt2,
        username_hash=hash_username("bob_b", salt2)
    )

    # Create students for teacher2
    salt3 = get_random_salt()
    student3 = Student(
        first_name="Charlie",
        last_initial="C",
        block="Period2",
        salt=salt3,
        username_hash=hash_username("charlie_c", salt3)
    )
    
    salt4 = get_random_salt()
    student4 = Student(
        first_name="Diana",
        last_initial="D",
        block="Period2",
        salt=salt4,
        username_hash=hash_username("diana_d", salt4)
    )

    db.session.add_all([student1, student2, student3, student4])
    db.session.commit()

    # Link students to teachers via StudentTeacher associations
    db.session.add_all([
        StudentTeacher(student_id=student1.id, admin_id=teacher1.id),
        StudentTeacher(student_id=student2.id, admin_id=teacher1.id),
        StudentTeacher(student_id=student3.id, admin_id=teacher2.id),
        StudentTeacher(student_id=student4.id, admin_id=teacher2.id),
    ])
    db.session.commit()

    # Create Class Contexts
    join_code1 = "CLASS-A"
    join_code2 = "CLASS-B"
    db.session.add_all([
        ClassEconomy(join_code=join_code1, status="active", created_by_admin_id=teacher1.id),
        ClassEconomy(join_code=join_code2, status="active", created_by_admin_id=teacher2.id),
        ClassMembership(join_code=join_code1, admin_id=teacher1.id, role="admin", status="active"),
        ClassMembership(join_code=join_code2, admin_id=teacher2.id, role="admin", status="active"),
        ClassMembership(join_code=join_code1, student_id=student1.id, role="student", status="active"),
        ClassMembership(join_code=join_code1, student_id=student2.id, role="student", status="active"),
        ClassMembership(join_code=join_code2, student_id=student3.id, role="student", status="active"),
        ClassMembership(join_code=join_code2, student_id=student4.id, role="student", status="active"),
    ])
    db.session.flush()

    # Create hall pass settings for both teachers
    settings1 = HallPassSettings(
        teacher_id=teacher1.id,
        queue_enabled=True,
        queue_limit=10
    )
    settings2 = HallPassSettings(
        teacher_id=teacher2.id,
        queue_enabled=True,
        queue_limit=10
    )
    db.session.add_all([settings1, settings2])
    db.session.commit()

    # Create hall passes for teacher1's students
    now = datetime.now(timezone.utc)
    
    # Approved pass for student1 (teacher1)
    pass1 = HallPassLog(
        student_id=student1.id,
        reason="Restroom",
        status="approved",
        join_code=join_code1,
        decision_time=now - timedelta(minutes=5)
    )
    
    # Currently out pass for student2 (teacher1)
    pass2 = HallPassLog(
        student_id=student2.id,
        reason="Office",
        status="left",
        join_code=join_code1,
        left_time=now - timedelta(minutes=3),
        decision_time=now - timedelta(minutes=10)
    )

    # Create hall passes for teacher2's students
    # Approved pass for student3 (teacher2)
    pass3 = HallPassLog(
        student_id=student3.id,
        reason="Nurse",
        status="approved",
        join_code=join_code2,
        decision_time=now - timedelta(minutes=2)
    )
    
    # Currently out pass for student4 (teacher2)
    pass4 = HallPassLog(
        student_id=student4.id,
        reason="Locker",
        status="left",
        join_code=join_code2,
        left_time=now - timedelta(minutes=1),
        decision_time=now - timedelta(minutes=8)
    )

    db.session.add_all([pass1, pass2, pass3, pass4])
    db.session.commit()

    return {
        'teacher1': teacher1,
        'teacher2': teacher2,
        'student1': student1,
        'student2': student2,
        'student3': student3,
        'student4': student4,
        'pass1': pass1,
        'pass2': pass2,
        'pass3': pass3,
        'pass4': pass4
    }


    """Test that the queue endpoint requires join_code parameter."""
    response = client.get('/api/hall-pass/queue')
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'join_code' in data['message']


def test_hall_pass_queue_scopes_to_teacher1(client, setup_multi_teacher_hall_passes):
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    join_code1 = "CLASS-A"
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    response = client.get(f'/api/hall-pass/queue?join_code={join_code1}')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher1 should see 1 in queue (student1) and 1 currently out (student2)
    assert len(json_data['queue']) == 1
    assert json_data['currently_out'] == 1
    assert json_data['total'] == 2
    
    # Verify it's the correct student in queue
    assert json_data['queue'][0]['student_name'] == 'Alice A.'
    assert json_data['queue'][0]['destination'] == 'Restroom'


def test_hall_pass_queue_scopes_to_teacher2(client, setup_multi_teacher_hall_passes):
    """Test that teacher2 only sees their own students' hall passes."""
    data = setup_multi_teacher_hall_passes
    teacher2_id = data['teacher2'].id
    join_code2 = "CLASS-B"
    
    # Login as teacher2
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher2_id
    
    response = client.get(f'/api/hall-pass/queue?join_code={join_code2}')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher2 should see 1 in queue (student3) and 1 currently out (student4)
    assert len(json_data['queue']) == 1
    assert json_data['currently_out'] == 1
    assert json_data['total'] == 2
    
    # Verify it's the correct student in queue
    assert json_data['queue'][0]['student_name'] == 'Charlie C.'
    assert json_data['queue'][0]['destination'] == 'Nurse'


def test_hall_pass_queue_with_shared_student(client, setup_multi_teacher_hall_passes):
    """Test that shared students are visible to both teachers."""
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    teacher2_id = data['teacher2'].id
    student1_id = data['student1'].id
    
    # Share student1 (originally teacher1's) with teacher2
    shared_link = StudentTeacher(
        student_id=student1_id,
        admin_id=teacher2_id
    )
    db.session.add(shared_link)
    db.session.commit()
    
    # Add membership for shared student in Class B
    db.session.add(ClassMembership(join_code="CLASS-B", student_id=student1_id, role="student", status="active"))
    db.session.flush()
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id

    # Teacher1 should still see student1 in queue (Class A)
    response1 = client.get(f'/api/hall-pass/queue?join_code=CLASS-A')
    json_data1 = response1.get_json()
    assert len(json_data1['queue']) == 1
    assert json_data1['queue'][0]['student_name'] == 'Alice A.'
    
    # Teacher2 should ONLY see student1 if they have a pass in Class B or if we are testing cross-listing?
    # Wait, the logic is: queue for A join_code shows passes with that join_code.
    # If student1 has a pass in Class A, they show up in Class A queue.
    # They do NOT show up in Class B queue unless they have a pass in Class B.
    # The original test assumed "teacher queue" aggregates all their students.
    # New logic is strict join_code.
    # So create a pass for student1 in Class B to verify visibility.
    pass_new = HallPassLog(
        student_id=student1_id,
        reason="Library",
        status="approved",
        join_code="CLASS-B",
        decision_time=datetime.now(timezone.utc)
    )
    db.session.add(pass_new)
    db.session.commit()

    # Login as teacher2
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher2_id

    response2 = client.get(f'/api/hall-pass/queue?join_code=CLASS-B')
    json_data2 = response2.get_json()
    # Teacher2 now has 2 students in queue: Charlie (their original) + Alice (shared)
    assert len(json_data2['queue']) == 2
    student_names = [item['student_name'] for item in json_data2['queue']]
    assert 'Alice A.' in student_names
    assert 'Charlie C.' in student_names


def test_hall_pass_queue_uses_session_admin_id(client, setup_multi_teacher_hall_passes):
    """Test that endpoint uses session admin_id if no teacher_id param provided."""
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
        sess['current_join_code'] = "CLASS-A"

    response = client.get('/api/hall-pass/queue?join_code=CLASS-A')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Should see teacher1's data
    assert len(json_data['queue']) == 1
    assert json_data['queue'][0]['student_name'] == 'Alice A.'


def test_hall_pass_queue_rejects_invalid_join_code(client):
    """Test that endpoint returns 403/404 for non-existent or unauthorized join_code."""
    response = client.get('/api/hall-pass/queue?join_code=INVALID99')
    assert response.status_code in [403, 404]
    data = response.get_json()
    assert data['status'] == 'error'


def test_hall_pass_queue_rejects_cross_teacher_access(client, setup_multi_teacher_hall_passes):
    """Test that teacher1 cannot access teacher2's queue."""
    data = setup_multi_teacher_hall_passes
    teacher2_id = data['teacher2'].id
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = data['teacher1'].id
    
    # Try to access teacher2's queue (Class B)
    response = client.get(f'/api/hall-pass/queue?join_code=CLASS-B')
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'You do not have access to this class' in json_data['message']


def test_hall_pass_queue_allows_student_same_class_scope(client, setup_multi_teacher_hall_passes):
    """Student can read queue for their own class but not another class."""
    data = setup_multi_teacher_hall_passes
    student1_id = data['student1'].id

    with client.session_transaction() as sess:
        sess['student_id'] = student1_id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "CLASS-A"

    own_class_response = client.get("/api/hall-pass/queue?join_code=CLASS-A")
    assert own_class_response.status_code == 200
    own_class_data = own_class_response.get_json()
    assert own_class_data["status"] == "success"
    assert any(item["student_name"] == "Alice A." for item in own_class_data["queue"])

    other_class_response = client.get("/api/hall-pass/queue?join_code=CLASS-B")
    assert other_class_response.status_code == 403
