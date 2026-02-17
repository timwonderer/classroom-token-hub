
from decimal import Decimal
import pytest
from app.models import Student, Transaction, TransactionStatus, BalanceCache, Admin
from app.extensions import db
from app.utils.banking import settle_balances

def test_ledger_flow(client):
    """Test full flow: Create PENDING -> Settle -> Verify Cache."""
    # Setup
    student = Student(first_name="Test", last_initial="S", block="A", 
                      salt=b'123', first_half_hash="hash", dob_sum=123)
    teacher = Admin(username="teacher", totp_secret="secret")
    db.session.add(student)
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "MATH101"

    # 1. Create Transaction (PENDING)
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('10.50'),
        account_type='checking',
        status=TransactionStatus.PENDING,
        description="Initial deposit"
    )
    db.session.add(tx)
    db.session.commit()
    
    # Verify Pending state
    assert tx.status == TransactionStatus.PENDING
    assert tx.posted_at is None
    
    # 2. Verify Balance Read triggers Settlement
    # Student.get_checking_balance calls settle_balances
    bal = student.get_checking_balance(join_code=join_code)
    assert bal == Decimal('10.50')
    
    # 3. Verify Settlement Effects
    db.session.expire_all()
    tx = Transaction.query.get(tx.id)
    assert tx.status == TransactionStatus.POSTED
    assert tx.posted_at is not None
    
    cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    assert cache is not None
    assert cache.posted_checking_balance_cents == 1050
    assert cache.last_settlement_at is not None

def test_void_pending(client):
    """Test voiding a PENDING transaction (no reversal)."""
    student = Student(first_name="Test2", last_initial="B", block="B", 
                      salt=b'456', first_half_hash="hash2", dob_sum=456)
    teacher = Admin(username="teacher2", totp_secret="secret")
    db.session.add(student)
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "SCI202"
    
    # 1. Create PENDING
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('50.00'),
        status=TransactionStatus.PENDING
    )
    db.session.add(tx)
    db.session.commit()
    
    # 2. Simulate Void Logic (Admin Button)
    # Pending voids are marked is_void and resolved during settlement.
    tx.is_void = True
    db.session.commit()
    
    # 3. Read Balance
    bal = student.get_checking_balance(join_code=join_code)
    
    # Should be 0.00 (settlement ignores VOID pending)
    assert bal == Decimal('0.00')
    
    # Verify no reversal created
    reversals = Transaction.query.filter_by(original_transaction_id=tx.id).all()
    assert len(reversals) == 0

    # Verify pending transaction was settled as VOID.
    db.session.expire_all()
    tx = Transaction.query.get(tx.id)
    assert tx.status == TransactionStatus.VOID
    assert tx.voided_at is not None
    
    # Verify Cache state (should be 0)
    cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    # Cache might exist if get_checking_balance triggered settlement (which creates it if missing)
    if cache:
        assert cache.posted_checking_balance_cents == 0

def test_void_posted_with_reversal(client):
    """Test voiding a POSTED transaction (creates reversal)."""
    student = Student(first_name="Test3", last_initial="C", block="C", 
                      salt=b'789', first_half_hash="hash3", dob_sum=789)
    teacher = Admin(username="teacher3", totp_secret="secret")
    db.session.add(student)
    db.session.add(teacher)
    db.session.commit()
    
    join_code = "ENG303"
    
    # 1. Create PENDING then Settle -> POSTED
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('100.00'),
        status=TransactionStatus.PENDING
    )
    db.session.add(tx)
    db.session.commit()
    
    student.get_checking_balance(join_code=join_code) # Trigger settlement
    
    db.session.expire_all()
    tx = Transaction.query.get(tx.id)
    assert tx.status == TransactionStatus.POSTED
    
    # 2. Simulate Void Logic (Admin Button)
    # Since status is POSTED, logic should match admin.py:
    # Mark is_void=True
    # Create Reversal (status=PENDING)
    
    tx.is_void = True
    
    reversal = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-tx.amount,
        status=TransactionStatus.PENDING,
        original_transaction_id=tx.id
    )
    db.session.add(reversal)
    db.session.commit()
    
    # 3. Read Balance (Should be 0)
    # 100 (POSTED) + (-100) (PENDING) = 0
    bal_after_void = student.get_checking_balance(join_code=join_code)
    assert bal_after_void == Decimal('0.00')
    
    # 4. Trigger Settlement again (processes Reversal)
    # get_checking_balance triggered it above.
    # Check cache.
    
    db.session.expire_all()
    reversal = Transaction.query.get(reversal.id)
    assert reversal.status == TransactionStatus.POSTED
    
    cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    # Cache should be updated: 100 + (-100) = 0
    assert cache.posted_checking_balance_cents == 0
