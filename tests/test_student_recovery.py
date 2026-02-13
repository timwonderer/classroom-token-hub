"""
Tests for the single account recovery flow per the Account Recovery & Reclaim spec.

Covers:
  - Teacher-initiated reset code generation (Step 1)
  - Student lookup via join_code + reset_code (Step 2)
  - Identity re-registration (Step 3)
  - Credential re-establishment (Step 4 — via existing setup flow)
  - Completion (Step 5)
  - State machine transitions
  - Security & edge cases from the spec acceptance tests
"""
import pytest
from datetime import timedelta, timezone
from app import db
from app.models import Student, TeacherBlock, Admin, StudentTeacher, Transaction, StudentBlock
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
    teacher = Admin(username="teacher_rec", totp_secret="base32secret3232")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Original",
        last_initial="O",
        block="A",
        salt=salt,
        username_hash=hash_username("orig_user", salt),
        first_half_hash="hash1",
        dob_sum=2020,
        is_active=True,
        recovery_status='active',
    )
    db.session.add(student)
    db.session.commit()

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
        is_claimed=True,
    )
    db.session.add(tb)
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()

    return {
        "teacher": teacher,
        "student": student,
        "join_code": join_code,
    }


# ------------------------------------------------------------------
# Step 1 — Teacher Initiates Reset
# ------------------------------------------------------------------

def test_teacher_generates_reset_code(client, recovery_data):
    """Teacher clicks 'Reset Student Account' -> system generates code."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["is_admin"] = True

    resp = client.post(
        f"/recovery/admin/generate-code/{student.id}",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Reset code generated" in resp.data

    db.session.refresh(student)
    assert student.reset_code is not None
    assert len(student.reset_code) == 8
    assert ensure_utc(student.reset_code_expires_at) > utc_now()
    assert student.recovery_status == 'to_be_claimed'


def test_multiple_resets_invalidate_prior_codes(client, recovery_data):
    """Multiple reset attempts regenerate and invalidate prior codes."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["is_admin"] = True

    # First reset
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    first_code = student.reset_code

    # Second reset
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    second_code = student.reset_code

    assert first_code != second_code
    assert student.recovery_status == 'to_be_claimed'


# ------------------------------------------------------------------
# Step 2 — Student Enters Join Code + Reset Code
# ------------------------------------------------------------------

def test_student_lookup_success(client, recovery_data):
    """Valid join_code + reset_code -> redirect to verify-identity."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "RESET123",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert "/recovery/verify-identity" in resp.location

    with client.session_transaction() as sess:
        assert sess["recovery_student_id"] == student.id


def test_student_lookup_wrong_join_code(client, recovery_data):
    """Reset code valid but join_code doesn't match -> generic error."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": "WRONG999",
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_expired_code(client, recovery_data):
    """Expired reset_code -> generic error."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() - timedelta(minutes=1)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_wrong_status(client, recovery_data):
    """Reset code present but student not in to_be_claimed -> fail."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'active'   # Not to_be_claimed
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_nonexistent_code(client, recovery_data):
    """Completely invalid code -> generic error, no identity revealed."""
    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "NOTEXIST",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


# ------------------------------------------------------------------
# Step 3 — Identity Re-Registration
# ------------------------------------------------------------------

def test_verify_identity_updates_pii_and_clears_credentials(client, recovery_data):
    """PII is replaced, salt rotated, credentials cleared, code consumed."""
    student = recovery_data["student"]
    old_salt = student.salt
    original_id = student.id

    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id

    resp = client.post("/recovery/verify-identity", data={
        "first_name": "NewFirst",
        "last_name": "NewLast",
        "dob": "2015-06-15",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    db.session.refresh(student)

    # Identity integrity: student_id unchanged
    assert student.id == original_id

    # PII updated
    assert student.first_name == "NewFirst"
    assert student.last_initial == "N"
    assert student.dob_sum == (6 + 15 + 2015)  # 2036

    # Salt rotated
    assert student.salt != old_salt

    # Credentials cleared
    assert student.username_hash is None
    assert student.pin_hash is None
    assert student.passphrase_hash is None
    assert student.has_completed_setup is False

    # Recovery state cleared (Step 5 completion)
    assert student.reset_code is None
    assert student.reset_code_expires_at is None
    assert student.recovery_status == 'active'


def test_verify_identity_no_new_student_row(client, recovery_data):
    """Recovering an account must not create a new student row."""
    student = recovery_data["student"]
    original_id = student.id
    original_count = Student.query.count()

    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id

    client.post("/recovery/verify-identity", data={
        "first_name": "Changed",
        "last_name": "Name",
        "dob": "2010-03-20",
    }, follow_redirects=True)

    assert Student.query.count() == original_count
    db.session.refresh(student)
    assert student.id == original_id


def test_verify_identity_redirects_without_session(client, recovery_data):
    """Accessing verify-identity without recovery session -> redirect."""
    resp = client.get("/recovery/verify-identity", follow_redirects=False)
    assert resp.status_code == 302
    assert "/recovery/lookup" in resp.location


def test_verify_identity_missing_fields(client, recovery_data):
    """All fields required for identity re-registration."""
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id

    resp = client.post("/recovery/verify-identity", data={
        "first_name": "Only",
        "last_name": "",
        "dob": "2015-01-01",
    }, follow_redirects=True)

    assert b"All fields are required" in resp.data


# ------------------------------------------------------------------
# Economic Invariance Tests
# ------------------------------------------------------------------

def test_recovery_preserves_balance_and_transactions(client, recovery_data):
    """Balance and transaction count unchanged through recovery."""
    student = recovery_data["student"]
    teacher = recovery_data["teacher"]
    join_code = recovery_data["join_code"]

    # Give student a balance
    db.session.add(StudentBlock(
        student_id=student.id,
        period="A",
        join_code=join_code,
    ))
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        amount=200.0,
        type='deposit',
        description='Initial deposit',
        account_type='checking',
        join_code=join_code,
    )
    db.session.add(tx)
    db.session.commit()

    tx_count_before = Transaction.query.filter_by(
        student_id=student.id, join_code=join_code
    ).count()

    # Run recovery
    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id

    client.post("/recovery/verify-identity", data={
        "first_name": "Recovered",
        "last_name": "Student",
        "dob": "2012-07-04",
    }, follow_redirects=True)

    # Verify economic data untouched
    tx_count_after = Transaction.query.filter_by(
        student_id=student.id, join_code=join_code
    ).count()
    assert tx_count_after == tx_count_before

    # No new economic transactions created during recovery
    recovery_txns = Transaction.query.filter_by(
        student_id=student.id, type='recovery'
    ).count()
    assert recovery_txns == 0


# ------------------------------------------------------------------
# Reset Code Security Tests
# ------------------------------------------------------------------

def test_reset_code_invalid_after_use(client, recovery_data):
    """Reset code is single-use — invalid after successful recovery."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "ONETIME1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    # Use the code successfully
    with client.session_transaction() as sess:
        sess["recovery_student_id"] = student.id

    client.post("/recovery/verify-identity", data={
        "first_name": "Test",
        "last_name": "User",
        "dob": "2010-01-01",
    }, follow_redirects=True)

    db.session.refresh(student)
    assert student.reset_code is None
    assert student.recovery_status == 'active'

    # Attempt reuse
    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "ONETIME1",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_only_one_active_reset_code_per_student(client, recovery_data):
    """Only one active reset_code per student at a time."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["is_admin"] = True

    # Generate first code
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    first_code = student.reset_code

    # Generate second code (overwrites first)
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)

    assert student.reset_code != first_code
    # Only one reset_code stored
    students_with_first = Student.query.filter_by(reset_code=first_code).count()
    assert students_with_first == 0


# ------------------------------------------------------------------
# Edge Case Tests
# ------------------------------------------------------------------

def test_reclaim_when_not_to_be_claimed_fails(client, recovery_data):
    """Attempt reclaim when status != to_be_claimed -> fail."""
    student = recovery_data["student"]
    student.reset_code = "EDGECASE"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'active'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "EDGECASE",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_interrupting_reclaim_does_not_corrupt_record(client, recovery_data):
    """Interrupting mid-flow does not corrupt student record."""
    student = recovery_data["student"]
    original_name = student.first_name
    original_hash = student.username_hash

    student.reset_code = "MIDFLOW1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    # Complete Step 2 (lookup) but abandon before Step 3
    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "MIDFLOW1",
    }, follow_redirects=False)
    assert resp.status_code == 302

    # Abandon: don't complete verify_identity
    db.session.refresh(student)

    # Student record unchanged
    assert student.first_name == original_name
    assert student.username_hash == original_hash
    # Reset code still valid (can try again)
    assert student.reset_code == "MIDFLOW1"
    assert student.recovery_status == 'to_be_claimed'


# ------------------------------------------------------------------
# Financial Cooldown Utility (preserved from original)
# ------------------------------------------------------------------

def test_financial_cooldown_enforcement(recovery_data):
    """Test the utility function check_financial_cooldown."""
    student = recovery_data["student"]

    # No cooldown
    student.money_action_cooldown_until = None
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True

    # Active cooldown
    student.money_action_cooldown_until = utc_now() + timedelta(minutes=30)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is False
    assert "29 min" in msg or "30 min" in msg

    # Expired cooldown
    student.money_action_cooldown_until = utc_now() - timedelta(minutes=1)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True
