import pytest

pytestmark = [pytest.mark.critical, pytest.mark.regression]

"""
Test transfer behavior when legacy transactions (NULL join_code) are present.

Current behavior is strict join_code scoping: legacy NULL-join_code records do
not count toward balances in a class-scoped student session.
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.routes.student import TRANSFER_SUBMISSION_TOKEN_KEY
from app.models import Student, Admin, BankingSettings, Transaction, TeacherBlock, TransactionStatus
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username

def _set_transfer_submission_token(client, token="test-transfer-token"):
    with client.session_transaction() as sess:
        sess[TRANSFER_SUBMISSION_TOKEN_KEY] = [token]
    return token


@pytest.fixture
def setup_student_with_legacy_transactions(client):
    """Create a student with both legacy (NULL join_code) and new transactions."""
    # Create teacher
    teacher = Admin(
        username="teacher1",
        totp_secret="secret123"
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
        passphrase_hash=generate_password_hash("alice_pass"),
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teacher
    from app.models import StudentTeacher
    st = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    db.session.add(st)
    db.session.commit()


    join_code = "MATH1A"
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Alice",
        last_initial="A",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt,
        first_half_hash="hash1",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    db.session.commit()

    # Add first transaction as a legacy row with NULL join_code.
    # It should be excluded from class-scoped balance calculations.
    tx1 = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=None,
        amount=100.0,
        account_type='checking',
        status=TransactionStatus.POSTED,
        type='Initial',
        description='Legacy balance without join_code'
    )
    
    # Add second transaction with current class join_code.
    tx2 = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=50.0,
        account_type='checking',
        status=TransactionStatus.PENDING,  # PENDING so it gets settled
        type='Deposit',
        description='Additional deposit'
    )
    
    db.session.add_all([tx1, tx2])
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_uses_only_join_code_scoped_balance(client, setup_student_with_legacy_transactions):
    """Transfer should use only join_code-scoped balance (legacy rows ignored)."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Student has $50 join_code-scoped checking ($100 legacy row is ignored)
    # Try to transfer exactly $50 from checking to savings
    submission_token = _set_transfer_submission_token(client)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'alice_pass',
        'transfer_submission_token': submission_token,
    }, follow_redirects=False)
    
    # Should succeed (redirect to dashboard)
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Verify transactions were created
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).limit(2).all()
    
    # Should have 2 new transactions (withdrawal and deposit)
    assert len(transactions) == 2
    
    # Find withdrawal and deposit
    withdrawal = next((tx for tx in transactions if tx.amount < 0), None)
    deposit = next((tx for tx in transactions if tx.amount > 0), None)
    
    assert withdrawal is not None
    assert withdrawal.amount == -50.0
    assert withdrawal.account_type == 'checking'
    
    assert deposit is not None
    assert deposit.amount == 50.0
    assert deposit.account_type == 'savings'


def test_insufficient_funds_with_only_new_transactions(client, setup_student_with_legacy_transactions):
    """Test that insufficient funds check works correctly."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Student has only $50 join_code-scoped checking.
    # Try to transfer $200 (more than available)
    submission_token = _set_transfer_submission_token(client)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '200.00',
        'passphrase': 'alice_pass',
        'transfer_submission_token': submission_token,
    }, follow_redirects=True)
    
    # Should fail with insufficient funds error
    assert response.status_code == 200
    assert b'Insufficient checking funds' in response.data


def test_transfer_does_not_include_legacy_null_join_code_balance(client, setup_student_with_legacy_transactions):
    """Legacy NULL-join_code balance should not be spendable in class context."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Try to transfer $150 (legacy $100 + new $50). Should fail now.
    submission_token = _set_transfer_submission_token(client)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '150.00',
        'passphrase': 'alice_pass',
        'transfer_submission_token': submission_token,
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Insufficient checking funds' in response.data


def test_declined_transfer_does_not_charge_overdraft_fee(client):
    """A failed self-transfer should not create an overdraft fee transaction."""
    teacher = Admin(
        username="teacher_transfer_fee_test",
        totp_secret="secret123",
    )
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt,
        username_hash=hash_username("bob_b", salt),
        passphrase_hash=generate_password_hash("bob_pass"),
    )
    db.session.add(student)
    db.session.commit()

    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))

    join_code = "FEEFREE1"
    db.session.add(
        TeacherBlock(
            teacher_id=teacher.id,
            block="Period1",
            first_name="Bob",
            last_initial="B",
            last_name_hash_by_part=[],
            dob_sum=2000,
            salt=salt,
            first_half_hash="hash1",
            join_code=join_code,
            student_id=student.id,
            is_claimed=True,
            claimed_at=datetime.now(timezone.utc),
        )
    )
    db.session.add(
        BankingSettings(
            teacher_id=teacher.id,
            block="Period1",
            overdraft_fee_enabled=True,
            overdraft_fee_type="flat",
            overdraft_fee_flat_amount=35,
        )
    )
    db.session.add(
        Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=50,
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Initial deposit",
        )
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    submission_token = _set_transfer_submission_token(client, "first-transfer-token")
    response = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "50.00",
            "passphrase": "bob_pass",
            "transfer_submission_token": submission_token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    submission_token = _set_transfer_submission_token(client, "second-transfer-token")
    response = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "1.00",
            "passphrase": "bob_pass",
            "transfer_submission_token": submission_token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Insufficient checking funds" in response.data

    overdraft_txs = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code,
        type="overdraft_fee",
        is_void=False,
    ).all()
    assert overdraft_txs == []


def test_transfer_submission_token_cannot_be_reused(client, setup_student_with_legacy_transactions):
    """A transfer submission token should be consumed after the first successful use."""
    data = setup_student_with_legacy_transactions
    student = data["student"]
    teacher = data["teacher"]
    join_code = data["join_code"]

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    submission_token = _set_transfer_submission_token(client, "single-use-token")
    first_response = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "10.00",
            "passphrase": "alice_pass",
            "transfer_submission_token": submission_token,
        },
        follow_redirects=False,
    )
    assert first_response.status_code == 302

    second_response = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "10.00",
            "passphrase": "alice_pass",
            "transfer_submission_token": submission_token,
        },
        follow_redirects=True,
    )
    assert second_response.status_code == 200
    assert b"already been processed or expired" in second_response.data

    transfer_txs = Transaction.query.filter_by(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        is_void=False,
    ).all()
    withdrawal_count = sum(1 for tx in transfer_txs if tx.type == "Withdrawal")
    deposit_count = sum(
        1
        for tx in transfer_txs
        if tx.type == "Deposit" and tx.description == "Transfer from checking"
    )
    assert withdrawal_count == 1
    assert deposit_count == 1


def test_transfer_json_request_uses_submission_token(client, setup_student_with_legacy_transactions):
    """JSON transfer requests should validate the same one-time submission token."""
    data = setup_student_with_legacy_transactions
    student = data["student"]
    teacher = data["teacher"]
    join_code = data["join_code"]

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    submission_token = _set_transfer_submission_token(client, "json-transfer-token")
    response = client.post(
        "/student/transfer",
        json={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "10.00",
            "passphrase": "alice_pass",
            "transfer_submission_token": submission_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "message": "Transfer completed successfully!",
    }

    transfer_txs = Transaction.query.filter_by(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        is_void=False,
    ).all()
    withdrawal_count = sum(1 for tx in transfer_txs if tx.type == "Withdrawal")
    deposit_count = sum(
        1
        for tx in transfer_txs
        if tx.type == "Deposit" and tx.description == "Transfer from checking"
    )
    assert withdrawal_count == 1
    assert deposit_count == 1
