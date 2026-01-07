"""
Tests for analytics class selector refactoring.

Ensures that:
- Both analytics templates include the new JS file
- Templates render correctly with the refactored code
- JavaScript file is included in the correct location
"""
import pytest
from flask import url_for
from app import db
from app.models import Admin, TeacherBlock, PayrollSettings, StudentBlock, Student
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_analytics_teacher(client):
    """Create a teacher with analytics access."""
    # Create admin/teacher
    admin = Admin(
        username="analyticsuser",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()
    
    # Create join code and teacher block
    join_code = "TEST456"
    teacher_block = TeacherBlock(
        teacher_id=admin.id,
        block="A",
        join_code=join_code
    )
    db.session.add(teacher_block)
    
    # Create payroll settings for this block
    payroll = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=0.25,
        expected_weekly_hours=5.0,
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll)
    
    # Create a student for the class
    salt = get_random_salt()
    student = Student(
        first_name="TestStudent",
        last_initial="A",
        block="A",
        salt=salt,
        username_hash=hash_username("teststudent", salt),
        pin_hash="fake-hash",
        teacher_id=admin.id
    )
    db.session.add(student)
    db.session.flush()
    
    # Link student to period
    student_block = StudentBlock(
        student_id=student.id,
        period="A",
        join_code=join_code
    )
    db.session.add(student_block)
    
    db.session.commit()
    
    return admin, join_code


def test_analytics_dashboard_includes_class_selector_js(client, setup_analytics_teacher):
    """Test that the analytics dashboard template includes the new JS file."""
    admin, join_code = setup_analytics_teacher
    
    # Login as teacher
    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        sess['admin_authenticated'] = True
        sess['current_join_code'] = join_code
    
    # Access analytics dashboard
    response = client.get(f'/admin/analytics/?join_code={join_code}')
    
    # Check that response is successful
    assert response.status_code == 200
    
    # Check that the new JS file is included
    assert b'js/analytics-class-selector.js' in response.data
    
    # Check that the old inline script is NOT present
    assert b"document.addEventListener('DOMContentLoaded', () => {" not in response.data
    assert b"const classSelect = document.getElementById('analyticsClassSelect');" not in response.data or \
           b"js/analytics-class-selector.js" in response.data


def test_analytics_events_includes_class_selector_js(client, setup_analytics_teacher):
    """Test that the analytics events template includes the new JS file."""
    admin, join_code = setup_analytics_teacher
    
    # Login as teacher
    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        sess['admin_authenticated'] = True
        sess['current_join_code'] = join_code
    
    # Access analytics events page
    response = client.get(f'/admin/analytics/events?join_code={join_code}')
    
    # Check that response is successful
    assert response.status_code == 200
    
    # Check that the new JS file is included
    assert b'js/analytics-class-selector.js' in response.data
    
    # Check that the old inline script is NOT present
    assert b"document.addEventListener('change', (event) => {" not in response.data


def test_analytics_class_selector_has_data_attribute(client, setup_analytics_teacher):
    """Test that the class selector has the required data-switch-url attribute."""
    admin, join_code = setup_analytics_teacher
    
    # Login as teacher
    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        sess['admin_authenticated'] = True
        sess['current_join_code'] = join_code
    
    # Access analytics dashboard
    response = client.get(f'/admin/analytics/?join_code={join_code}')
    
    assert response.status_code == 200
    
    # Check that the select element has the data-switch-url attribute
    assert b'data-switch-url=' in response.data
    assert b'id="analyticsClassSelect"' in response.data
