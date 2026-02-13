import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models import Admin, Student, TeacherBlock, StudentBlock, Transaction
from app.hash_utils import hash_username, hash_username_lookup
from app.utils.name_utils import hash_last_name_parts
from app.utils.claim_credentials import compute_primary_claim_hash
import os

@pytest.fixture
def test_data(app):
    """Setup test data: Admin, Class, Student (Completed Setup)"""
    with app.app_context():
        # Setup encryption key if missing (needed for PIIEncryptedType)
        if not os.environ.get('ENCRYPTION_KEY'):
            os.environ['ENCRYPTION_KEY'] = 'mock_key_must_be_32_bytes_long!!!!'

        # 1. Create Admin
        admin = Admin(username='admin_flow2', totp_secret='dummy_secret')
        db.session.add(admin)
        db.session.commit()

        # Generate shared salt for test
        salt = os.urandom(16)
        dob_sum = 20100101

        # Calculate TeacherBlock hashes
        last_name_hashes = hash_last_name_parts('TeacherLast', salt) 
        first_half = compute_primary_claim_hash('F', dob_sum, salt)

        # 2. Create Class (TeacherBlock)
        tb = TeacherBlock(
            teacher_id=admin.id,
            block='A',
            join_code='FLOW2A',
            is_claimed=True,
            first_name='Admin',
            last_initial='F',
            # Required hashing fields
            salt=salt,
            dob_sum=dob_sum,
            last_name_hash_by_part=last_name_hashes,
            first_half_hash=first_half
        )
        db.session.add(tb)
        db.session.commit()

        # 3. Create Student (Completed Setup)
        u_hash = hash_username('olduser', salt)
        ul_hash = hash_username_lookup('olduser')
        p_hash = generate_password_hash('1234')
        pp_hash = generate_password_hash('old-passphrase-word')

        student = Student(
            first_name='Flow',
            last_initial='T',
            block='A',
            salt=salt,
            dob_sum=dob_sum,
            username_hash=u_hash,
            username_lookup_hash=ul_hash,
            pin_hash=p_hash,
            passphrase_hash=pp_hash,
            has_completed_setup=True
        )
        db.session.add(student)
        db.session.commit()
        
        # Link Student to TeacherBlock
        tb.student_id = student.id
        
        # Manual Link to Admin (student_teachers M2M)
        student.teachers.append(admin)
        
        # StudentBlock
        db.session.add(StudentBlock(student_id=student.id, period='A', join_code='FLOW2A'))
        
        # Give some initial balance to verify preservation
        tx = Transaction(
            student_id=student.id,
            teacher_id=admin.id,
            amount=100.0,
            type='deposit',
            description='Initial Balance',
            account_type='checking',
            join_code='FLOW2A'
        )
        db.session.add(tx)
        db.session.commit()

        return {
            'admin_id': admin.id,
            'student_id': student.id,
            'join_code': 'FLOW2A'
        }

def test_credential_reset_flow(client, test_data):
    """
    Test Flow 2:
    1. Admin Resets Student Login.
    2. Verify Admin View shows Join Code.
    3. Student Re-claims Account.
    4. Verify New Credentials work.
    5. Verify Data Preserved.
    """
    admin_id = test_data['admin_id']
    student_id = test_data['student_id']
    
    # Login as Admin
    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['role'] = 'admin'
        sess['admin_id'] = admin_id
        sess['is_admin'] = True # REQUIRED by admin_required decorator

    # 1. Admin resets student login
    resp = client.post('/admin/student/edit', data={
        'student_id': student_id,
        'first_name': 'Flow', 
        'last_name': 'T',
        'reset_login': 'on', # THE ACTION
        'blocks': ['A']
    }, follow_redirects=True)
    
    # Check if reset actually happened confirmation is present
    if b"login has been reset" not in resp.data:
        print("\nDEBUG: Response Data:\n", resp.data.decode('utf-8'))
        
    assert resp.status_code == 200, f"Reset failed: {resp.data}"
    
    # 2. Verify Student State & Admin View
    with client.application.app_context():
        s = db.session.get(Student, student_id)
        # Debug print
        print(f"DEBUG: Student State: has_completed_setup={s.has_completed_setup}")
        
        assert s.has_completed_setup is False, f"Reset did not happen. Response: {resp.data[:200]}"
        assert s.username_hash is None
        assert s.pin_hash is None
    
    # Check student_detail page for Join Code visibility
    resp = client.get(f'/admin/students/{student_id}')
    assert resp.status_code == 200
    assert b"FLOW2A" in resp.data
    assert b"Account Recovery / Setup" in resp.data

    # 3. Student Re-claims Account
    # Simulate the DB update that happens after claim
    with client.application.app_context():
        s = db.session.get(Student, student_id)
        # New credentials
        salt = s.salt 
        s.username_hash = hash_username('newuser', salt)
        s.username_lookup_hash = hash_username_lookup('newuser')
        s.pin_hash = generate_password_hash('9999')
        s.passphrase_hash = generate_password_hash('new-passphrase-word')
        s.has_completed_setup = True
        
        # Also mark seat as claimed (mimic claim_account behavior)
        TeacherBlock.query.filter_by(student_id=student_id).update({'is_claimed': True})
        
        db.session.commit()

    # 4. Verify New Credentials Work (Login)
    client.get('/logout')
    
    resp = client.post('/student/login', data={
        'username': 'newuser',
        'pin': '9999'
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    assert b"Flow" in resp.data 

    # 5. Verify Data Preserved
    if b"100.00" not in resp.data:
        print("\nDEBUG: Student Dashboard HTML (Balance Check Failed):\n", resp.data.decode('utf-8'))
    assert b"100.00" in resp.data 
