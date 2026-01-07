"""
Tests for analytics join code scoping endpoint.

Ensures that:
1. Teachers can successfully set current join code for their class periods
2. Invalid join codes are rejected
3. Unauthorized access attempts are blocked
4. Session state is properly maintained
5. Multi-tenancy boundaries are enforced
"""

import pytest
from flask import session
from app.models import Admin, TeacherBlock, Student, StudentBlock
from app.extensions import db
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_teacher_with_classes(client):
    """Create a teacher with multiple class periods."""
    # Create teacher
    teacher = Admin(
        username="teacher_analytics",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.flush()
    
    # Create multiple class periods (TeacherBlocks)
    blocks = []
    join_codes = ["CLASS1A", "CLASS2B", "CLASS3C"]
    
    for i, join_code in enumerate(join_codes):
        teacher_block = TeacherBlock(
            teacher_id=teacher.id,
            block=chr(65 + i),  # A, B, C
            first_name=b"Test",
            last_initial="S",
            last_name_hash_by_part=['hash1'],
            dob_sum=2025,
            salt=get_random_salt(),
            first_half_hash=f'test_hash_{i}',
            join_code=join_code,
            is_claimed=False
        )
        db.session.add(teacher_block)
        blocks.append(teacher_block)
    
    db.session.commit()
    
    return teacher, join_codes, blocks


@pytest.fixture
def setup_two_teachers(client):
    """Create two teachers with different class periods."""
    # Create first teacher
    teacher1 = Admin(
        username="teacher1_analytics",
        totp_secret="SECRET1"
    )
    db.session.add(teacher1)
    db.session.flush()
    
    teacher1_block = TeacherBlock(
        teacher_id=teacher1.id,
        block="A",
        first_name=b"Test",
        last_initial="A",
        last_name_hash_by_part=['hash_t1'],
        dob_sum=2025,
        salt=get_random_salt(),
        first_half_hash='test_hash_t1',
        join_code="TEACHER1A",
        is_claimed=False
    )
    db.session.add(teacher1_block)
    
    # Create second teacher
    teacher2 = Admin(
        username="teacher2_analytics",
        totp_secret="SECRET2"
    )
    db.session.add(teacher2)
    db.session.flush()
    
    teacher2_block = TeacherBlock(
        teacher_id=teacher2.id,
        block="B",
        first_name=b"Test",
        last_initial="B",
        last_name_hash_by_part=['hash_t2'],
        dob_sum=2025,
        salt=get_random_salt(),
        first_half_hash='test_hash_t2',
        join_code="TEACHER2B",
        is_claimed=False
    )
    db.session.add(teacher2_block)
    
    db.session.commit()
    
    return teacher1, teacher2, "TEACHER1A", "TEACHER2B"


# ==================== Success Cases ====================

def test_set_current_class_success(client, setup_teacher_with_classes):
    """Test successful setting of current class join code."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    # Login as teacher
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Set the current class
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    
    # Verify session was updated
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[0]


def test_set_current_class_switches_between_periods(client, setup_teacher_with_classes):
    """Test switching between different class periods."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Set first class
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[0]
    
    # Switch to second class
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[1]},
                          content_type='application/json')
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[1]
    
    # Switch to third class
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[2]},
                          content_type='application/json')
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[2]


def test_set_current_class_preserves_other_session_data(client, setup_teacher_with_classes):
    """Test that setting current class doesn't affect other session data."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
        sess['other_data'] = 'should_be_preserved'
        sess['another_key'] = 12345
    
    # Set current class
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    assert response.status_code == 200
    
    # Verify other session data is preserved
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[0]
        assert sess['other_data'] == 'should_be_preserved'
        assert sess['another_key'] == 12345
        assert sess['is_admin'] is True
        assert sess['admin_id'] == teacher.id


# ==================== Error Cases ====================

def test_set_current_class_missing_join_code(client, setup_teacher_with_classes):
    """Test that missing join code returns 400 error."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Send empty join code
    response = client.post('/admin/current-class',
                          json={'join_code': ''},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'required' in data['message'].lower()


def test_set_current_class_no_json_body(client, setup_teacher_with_classes):
    """Test that request without JSON body returns 400 error."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Send request with no JSON body
    response = client.post('/admin/current-class')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'


def test_set_current_class_nonexistent_join_code(client, setup_teacher_with_classes):
    """Test that non-existent join code returns 404 error."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Try to set a join code that doesn't exist
    response = client.post('/admin/current-class',
                          json={'join_code': 'NOTEXIST'},
                          content_type='application/json')
    
    assert response.status_code == 404
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'not found' in data['message'].lower()


def test_set_current_class_unauthorized_teacher(client, setup_two_teachers):
    """Test that teacher cannot set join code for another teacher's class."""
    teacher1, teacher2, join_code1, join_code2 = setup_two_teachers
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1.id
    
    # Try to set teacher2's join code
    response = client.post('/admin/current-class',
                          json={'join_code': join_code2},
                          content_type='application/json')
    
    assert response.status_code == 404
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'not found' in data['message'].lower()
    
    # Verify session was NOT updated
    with client.session_transaction() as sess:
        # Session should not have current_join_code or it should not be teacher2's
        current = sess.get('current_join_code')
        assert current != join_code2


def test_set_current_class_unauthenticated(client, setup_teacher_with_classes):
    """Test that unauthenticated requests are rejected."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    # Don't set session (not logged in)
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    
    # Should redirect to login or return 401/403
    # The @admin_required decorator typically redirects to login
    assert response.status_code in [302, 401, 403]


# ==================== Edge Cases ====================

def test_set_current_class_whitespace_handling(client, setup_teacher_with_classes):
    """Test that whitespace in join code is properly stripped."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Send join code with leading/trailing whitespace
    response = client.post('/admin/current-class',
                          json={'join_code': f'  {join_codes[0]}  '},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    
    # Verify session has clean join code (stripped)
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[0]


def test_set_current_class_case_sensitive(client, setup_teacher_with_classes):
    """Test that join codes are case-sensitive."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Try lowercase version of join code
    lowercase_code = join_codes[0].lower()
    response = client.post('/admin/current-class',
                          json={'join_code': lowercase_code},
                          content_type='application/json')
    
    # Should fail if case-sensitive (404), or succeed if case-insensitive
    # Based on the code, it appears to be case-sensitive
    assert response.status_code == 404


def test_set_current_class_json_key_missing(client, setup_teacher_with_classes):
    """Test that missing 'join_code' key in JSON returns 400 error."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Send JSON without 'join_code' key
    response = client.post('/admin/current-class',
                          json={'wrong_key': 'value'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'


# ==================== Session State Validation ====================

def test_set_current_class_session_persistence_across_requests(client, setup_teacher_with_classes):
    """Test that session persists across multiple requests."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    # Set join code in first request
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    assert response.status_code == 200
    
    # Make another request (simulating navigation)
    # Session should still have the join code
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[0]
    
    # Set different join code in second request
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[1]},
                          content_type='application/json')
    assert response.status_code == 200
    
    # Verify session was updated to new join code
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_codes[1]


def test_set_current_class_multiple_teachers_isolated_sessions(client, setup_two_teachers):
    """Test that different teachers' sessions are isolated."""
    teacher1, teacher2, join_code1, join_code2 = setup_two_teachers
    
    # Simulate teacher1 setting their class
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1.id
    
    response = client.post('/admin/current-class',
                          json={'join_code': join_code1},
                          content_type='application/json')
    assert response.status_code == 200
    
    # Now simulate teacher2 in a different session
    # Clear session to simulate different client
    with client.session_transaction() as sess:
        sess.clear()
        sess['is_admin'] = True
        sess['admin_id'] = teacher2.id
    
    response = client.post('/admin/current-class',
                          json={'join_code': join_code2},
                          content_type='application/json')
    assert response.status_code == 200
    
    # Verify teacher2's session has their join code
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == join_code2
        assert sess['admin_id'] == teacher2.id


def test_set_current_class_response_format(client, setup_teacher_with_classes):
    """Test that response has correct format."""
    teacher, join_codes, blocks = setup_teacher_with_classes
    
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
    
    response = client.post('/admin/current-class',
                          json={'join_code': join_codes[0]},
                          content_type='application/json')
    
    assert response.status_code == 200
    assert response.content_type == 'application/json'
    
    data = response.get_json()
    assert 'status' in data
    assert data['status'] == 'success'
    assert isinstance(data, dict)
