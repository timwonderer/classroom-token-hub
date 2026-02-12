import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Student, TeacherBlock, Admin, StudentTeacher
from app.hash_utils import get_random_salt, hash_username
from app.utils.claim_credentials import compute_primary_claim_hash
from app.utils.money_guard import check_financial_cooldown
from app.utils.time import ensure_utc, utc_now

# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def recovery_data(client):
    """Setup a teacher, student, and class for recovery tests."""
    # 1. Create Teacher
    teacher = Admin(username="teacher_rec", totp_secret="base32secret3232")
    db.session.add(teacher)
    db.session.commit()
    
    # 2. Create Student with initial PII
    salt = get_random_salt()
    student = Student(
        first_name="Original",
        last_initial="O",
        block="A",
        salt=salt,
        username_hash=hash_username("orig_user", salt),
        first_half_hash="hash1",
        dob_sum=2020,
        is_active=True
    )
    db.session.add(student)
    db.session.commit()
    
    # 3. Link Student to Teacher (Join Code A123)
    join_code = "A123"
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        first_name="Original",
        last_initial="O",
        last_name_hash_by_part=[],
        dob_sum=2020,
        salt=salt,
        first_half_hash="hash1",
        student_id=student.id,
        is_claimed=True
    )
    db.session.add(tb)
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    
    return {
        "teacher": teacher,
        "student": student,
        "join_code": join_code,
        "Original_username": "orig_user"
    }

# ----------------------------------------------------------------------
# TESTS
# ----------------------------------------------------------------------

def test_teacher_can_generate_reset_code(client, recovery_data):
    """Test generating a reset code via Admin API."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]
    
    # Login as admin (simulate session)
    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["is_admin"] = True
    
    # Call generate code
    resp = client.post(f"/recovery/admin/generate-code/{student.id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Reset Code for Original O." in resp.data
    
    # Verify DB
    db.session.refresh(student)
    assert student.reset_code is not None
    assert len(student.reset_code) == 8
    assert ensure_utc(student.reset_code_expires_at) > utc_now()
    assert student.recovery_status == 'requested'

def test_student_lookup_flow1_success(client, recovery_data):
    """Test Flow 1: Lookup specific student by Join Code + Valid Reset Code."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]
    
    # Set Reset Code manually
    student.reset_code = "RESET123"
    student.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()
    
    # Attempt Lookup
    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "RESET123"
    }, follow_redirects=False)
    
    # Expect Redirect to Verify Identity
    assert resp.status_code == 302
    assert "/recovery/verify-identity" in resp.location
    
    with client.session_transaction() as sess:
        assert sess["recovery_student_id"] == student.id
        assert sess["recovery_mode"] == "account_reset"

def test_student_lookup_invalid_scope(client, recovery_data):
    """Test Flow 1: Reset code valid, but Join Code doesn't match student."""
    student = recovery_data["student"]
    
    student.reset_code = "RESET123"
    student.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()
    
    # Wrong Join Code
    resp = client.post("/recovery/lookup", data={
        "join_code": "WRONG999",
        "reset_code": "RESET123"
    }, follow_redirects=True)
    
    assert b"Invalid join code for this student" in resp.data

def test_student_lookup_expired(client, recovery_data):
    """Test Flow 1: Reset code expired."""
    student = recovery_data["student"]
    
    student.reset_code = "RESET123"
    student.reset_code_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1) # Expired
    db.session.commit()
    
    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "RESET123"
    }, follow_redirects=True)
    
    assert b"Reset code has expired" in resp.data

def test_verify_identity_updates_pii_and_resets(client, recovery_data):
    """Test Flow 1 Step 2: Update PII, rotate salt, clear credentials."""
    student = recovery_data["student"]
    old_salt = student.salt
    
    # Setup session
    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id
        sess["recovery_mode"] = "account_reset"
    
    # Submit New Identity
    resp = client.post("/recovery/verify-identity", data={
        "first_name": "NewName",
        "last_name": "NewLast",
        "dob": "2025-01-01"
        }, follow_redirects=False) # Should redirect to create-username
    
    assert resp.status_code == 302
    assert "/student/create-username" in resp.location
    
    db.session.refresh(student)
    
    # Check PII Updated
    assert student.first_name == "NewName"
    assert student.last_initial == "N"
    assert student.dob_sum == (1 + 1 + 2025) # 2027
    
    # Check Salt Rotated
    assert student.salt != old_salt
    
    # Check Credentials Cleared
    assert student.username_hash is None
    assert student.pin_hash is None
    assert student.passphrase_hash is None
    assert student.has_completed_setup is False
    assert student.reset_code is None # Cleared

def test_credential_lookup_flow2_success(client, recovery_data):
    """Test Flow 2: Lookup by Username + Reset Code."""
    student = recovery_data["student"]
    
    student.reset_code = "RESET123"
    student.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()
    
    resp = client.post("/recovery/credential-lookup", data={
        "username": "orig_user", # Matches setup
        "reset_code": "RESET123"
    }, follow_redirects=False)
    
    assert resp.status_code == 302
    assert "/recovery/reset" in resp.location
    with client.session_transaction() as sess:
        assert sess["recovery_mode"] == "credential_reset"

def test_credential_lookup_fail_username(client, recovery_data):
    """Test Flow 2: Username mismatch."""
    student = recovery_data["student"]
    
    student.reset_code = "RESET123"
    student.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.session.commit()
    
    resp = client.post("/recovery/credential-lookup", data={
        "username": "wrong_user", 
        "reset_code": "RESET123"
    }, follow_redirects=True)
    
    assert b"Username does not match" in resp.data

def test_reset_credentials_passphrase_cooldown(client, recovery_data):
    """Test Flow 2 Step 2: Changing Passphrase triggers cooldown."""
    student = recovery_data["student"]
    
    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id
        sess["recovery_mode"] = "credential_reset"
    
    resp = client.post("/recovery/reset", data={
        "passphrase": "new_secure_passphrase"
    }, follow_redirects=True)
    
    assert b"Money transfers unlocked in 1 hour" in resp.data
    
    db.session.refresh(student)
    assert student.passphrase_hash is not None
    assert ensure_utc(student.money_action_cooldown_until) > utc_now() + timedelta(minutes=55)

def test_reset_credentials_pin_no_cooldown(client, recovery_data):
    """Test Flow 2 Step 2: Changing PIN only does NOT trigger cooldown."""
    student = recovery_data["student"]
    
    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id
        sess["recovery_mode"] = "credential_reset"
    
    resp = client.post("/recovery/reset", data={
        "pin": "1234"
    }, follow_redirects=True)
    
    assert b"Credentials updated successfully" in resp.data
    
    db.session.refresh(student)
    assert student.money_action_cooldown_until is None

def test_financial_cooldown_enforcement(recovery_data):
    """Test the utility function check_financial_cooldown."""
    student = recovery_data["student"]
    
    # Case 1: No cooldown
    student.money_action_cooldown_until = None
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True
    
    # Case 2: Active cooldown
    student.money_action_cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=30)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is False
    assert "29 min" in msg or "30 min" in msg
    
    # Case 3: Expired cooldown
    student.money_action_cooldown_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True
