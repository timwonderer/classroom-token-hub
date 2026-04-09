
from decimal import Decimal
import importlib.util
from pathlib import Path
import pytest
from app.models import Student, Transaction, TransactionStatus, BalanceCache, Admin
from app.extensions import db
from app.utils.banking import settle_balances, settle_pending_transaction_contexts

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
    
    # 2. Verify Balance Read
    # Student.get_checking_balance NO LONGER calls settle_balances (Write-on-Read fix)
    bal = student.get_checking_balance(join_code=join_code)
    assert bal == Decimal('10.50')

    # Trigger explicit settlement for test purposes
    settle_balances(student.id, join_code)
    db.session.commit()
    
    # 3. Verify Settlement Effects
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
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
    
    # Trigger explicit settlement for test purposes
    settle_balances(student.id, join_code)
    db.session.commit()

    # Verify no reversal created
    reversals = Transaction.query.filter_by(original_transaction_id=tx.id).all()
    assert len(reversals) == 0

    # Verify pending transaction was settled as VOID.
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
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
    
    # student.get_checking_balance(join_code=join_code) # NO LONGER Triggers settlement
    settle_balances(student.id, join_code) # Explicit settlement
    db.session.commit()
    
    db.session.expire_all()
    tx = db.session.get(Transaction, tx.id)
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
    # get_checking_balance NO LONGER triggers it.
    settle_balances(student.id, join_code)
    db.session.commit()
    
    db.session.expire_all()
    reversal = db.session.get(Transaction, reversal.id)
    assert reversal.status == TransactionStatus.POSTED
    
    cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    # Ledger semantics exclude the voided original and keep the posted reversal.
    assert cache.posted_checking_balance_cents == -10000


def test_settlement_sweep_processes_each_pending_context_once(client):
    teacher = Admin(username="teacher-sweep", totp_secret="secret")
    student_one = Student(first_name="Sweep", last_initial="A", block="A", salt=b'111', first_half_hash="hasha", dob_sum=111)
    student_two = Student(first_name="Sweep", last_initial="B", block="B", salt=b'222', first_half_hash="hashb", dob_sum=222)
    db.session.add_all([teacher, student_one, student_two])
    db.session.commit()

    db.session.add_all([
        Transaction(
            student_id=student_one.id,
            teacher_id=teacher.id,
            join_code="SWEEP-A",
            amount=Decimal('12.34'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A',
        ),
        Transaction(
            student_id=student_one.id,
            teacher_id=teacher.id,
            join_code="SWEEP-A",
            amount=Decimal('1.66'),
            account_type='savings',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending A savings',
        ),
        Transaction(
            student_id=student_two.id,
            teacher_id=teacher.id,
            join_code="SWEEP-B",
            amount=Decimal('9.99'),
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='deposit',
            description='Pending B',
        ),
    ])
    db.session.commit()

    summary = settle_pending_transaction_contexts()

    assert summary == {"settled_contexts": 2, "failed_contexts": 0}

    posted_statuses = {
        (tx.student_id, tx.join_code, tx.account_type): tx.status
        for tx in Transaction.query.all()
    }
    assert posted_statuses[(student_one.id, "SWEEP-A", "checking")] == TransactionStatus.POSTED
    assert posted_statuses[(student_one.id, "SWEEP-A", "savings")] == TransactionStatus.POSTED
    assert posted_statuses[(student_two.id, "SWEEP-B", "checking")] == TransactionStatus.POSTED

    cache_one = BalanceCache.query.filter_by(student_id=student_one.id, join_code="SWEEP-A").first()
    cache_two = BalanceCache.query.filter_by(student_id=student_two.id, join_code="SWEEP-B").first()
    assert cache_one.posted_checking_balance_cents == 1234
    assert cache_one.posted_savings_balance_cents == 166
    assert cache_two.posted_checking_balance_cents == 999


def test_settle_balances_reconciles_existing_stale_cache_without_pending(client):
    teacher = Admin(username="teacher-reconcile", totp_secret="secret")
    student = Student(first_name="Recon", last_initial="C", block="C", salt=b'333', first_half_hash="hashc", dob_sum=333)
    db.session.add_all([teacher, student])
    db.session.commit()

    join_code = "RECON-1"
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('20.00'),
        account_type='checking',
        status=TransactionStatus.POSTED,
        description="Historical posted transaction",
    )
    cache = BalanceCache(
        student_id=student.id,
        join_code=join_code,
        posted_checking_balance_cents=0,
        posted_savings_balance_cents=0,
    )
    db.session.add_all([tx, cache])
    db.session.commit()

    settle_balances(student.id, join_code)
    db.session.commit()

    db.session.expire_all()
    refreshed_cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    refreshed_tx = db.session.get(Transaction, tx.id)
    assert refreshed_cache.posted_checking_balance_cents == 2000
    assert refreshed_cache.posted_savings_balance_cents == 0
    assert refreshed_cache.last_settlement_at is not None
    assert refreshed_tx.posted_at is not None


def test_settlement_script_returns_nonzero_when_failures(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "settle_pending_transactions.py"
    spec = importlib.util.spec_from_file_location("settle_pending_transactions_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class DummyAppContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyApp:
        def app_context(self):
            return DummyAppContext()

    monkeypatch.setattr(module, "create_app", lambda: DummyApp())
    monkeypatch.setattr(
        module,
        "settle_pending_transaction_contexts",
        lambda limit=None: {"settled_contexts": 1, "failed_contexts": 2},
    )
    monkeypatch.setattr(module, "parse_args", lambda: type("Args", (), {"limit": None})())

    assert module.main() == 1
