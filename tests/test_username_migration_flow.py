import pytest
from unittest.mock import patch, MagicMock
from app import db, Student
from werkzeug.security import generate_password_hash
from app.hash_utils import hash_username, get_random_salt, hash_username_lookup

@pytest.fixture
def test_student(app):
    """Create a legacy student for testing migration."""
    with app.app_context():
        salt = get_random_salt()
        stu = Student(
            first_name="Legacy",
            last_initial="L",
            block="B",
            salt=salt,
            username_hash=hash_username("legacy_stu1", salt),
            username_lookup_hash=hash_username_lookup("legacy_stu1"),
            pin_hash=generate_password_hash("1234"),
            has_completed_setup=True,
            has_completed_profile_migration=True, # Prevent redirect to complete-profile
            username_migrated=False, # Trigger migration
        )
        db.session.add(stu)
        db.session.commit()
        # Return ID to avoid session-binding issues across processes
        return stu.id

def test_legacy_student_redirect_to_migration(client, test_student):
    """Verify that legacy students are redirected to the migration page."""
    # Login
    client.post('/student/login', data={'username': 'legacy_stu1', 'pin': '1234'})
    
    # Try to access dashboard - should redirect to migration
    resp = client.get('/student/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/student/migrate-username' in resp.headers['Location']

def test_complete_migration_flow(client, test_student):
    """Verify the full two-step migration flow works as expected."""
    # Login
    client.post('/student/login', data={'username': 'legacy_stu1', 'pin': '1234'})
    
    # Step 1: Submit seed word (migrate-username route)
    resp = client.post('/student/migrate-username', data={'write_in_word': 'pizza'}, follow_redirects=True)
    assert b"Your New Username" in resp.data
    
    # Verify session has the new username
    with client.session_transaction() as sess:
        generated_username = sess.get('migration_username')
        assert generated_username is not None
        assert "pizza" in generated_username.lower()
    
    # Step 2: Confirm migration with acknowledgment (confirm-username-migration route)
    # First try without acknowledgment (should fail validation)
    resp = client.post('/student/confirm-username-migration', data={'submit': True}, follow_redirects=True)
    # Depending on how the error is shown, we check for the page title or error class
    assert b"Your New Username" in resp.data 
    
    # Now with acknowledgment
    with patch('app.routes.student.get_current_class_context') as mock_context:
        mock_context.return_value = {
            'join_code': 'ABCDEF',
            'teacher_id': 1,
            'block': 'A',
            'seat_id': 1
        }
        resp = client.post('/student/confirm-username-migration', data={
            'written_down_username': 'y', 
            'submit': True
        }, follow_redirects=True)
    
    assert b"Dashboard" in resp.data
    assert b"Your username has been updated" in resp.data
    
    # Verify PII was cleaned up
    from app.models import Student
    with client.application.app_context():
        student = db.session.get(Student, test_student)
        assert student.username_migrated is True
        assert student.dob_sum is None
        assert student.last_name_hash_by_part is None
    
    # Verify DB state (redundant check but keeping for safety)
    with client.application.app_context():
        stu = db.session.get(Student, test_student)
        assert stu.username_migrated is True
        assert stu.username_hash != hash_username("legacy_stu1", stu.salt)

def test_new_student_bypass_migration(client, app):
    """Verify that students already migrated are NOT redirected."""
    with app.app_context():
        salt = get_random_salt()
        stu = Student(
            first_name="Modern",
            last_initial="M",
            block="C",
            salt=salt,
            username_hash=hash_username("modern_stu1", salt),
            username_lookup_hash=hash_username_lookup("modern_stu1"),
            pin_hash=generate_password_hash("1234"),
            has_completed_setup=True,
            has_completed_profile_migration=True, # Prevent redirect
            username_migrated=True, # Already migrated
        )
        db.session.add(stu)
        db.session.commit()
        
    client.post('/student/login', data={'username': 'modern_stu1', 'pin': '1234'})
    with patch('app.routes.student.get_current_class_context') as mock_context:
        mock_context.return_value = {
            'join_code': 'ABCDEF',
            'teacher_id': 1,
            'block': 'A',
            'seat_id': 1
        }
        resp = client.get('/student/dashboard', follow_redirects=False)
    assert resp.status_code == 200 # No redirect

def test_username_collision_retry(app):
    """Verify that the uniqueness helper retries upon collision."""
    from app.routes.student import _generate_unique_student_username
    with app.app_context():
        # Mocking Student.query.filter_by().first()
        with patch('app.models.Student.query') as mock_query:
            # First 2 calls return a dummy object (simulating collision), 
            # 3rd call returns None (unique)
            mock_query.filter_by.return_value.first.side_effect = [MagicMock(), MagicMock(), None]
            
            username = _generate_unique_student_username("test", "John", "D")
            assert username is not None
            # filter_by should be called exactly 3 times
            assert mock_query.filter_by.call_count == 3
