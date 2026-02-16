"""
Test for handling NULL or invalid transaction amounts in get_total_earnings.

This test verifies the fix for the decimal.InvalidOperation error that occurs
when a transaction has a NULL amount value.
"""
from decimal import Decimal
from unittest.mock import PropertyMock, patch
from app import db
from app.models import Student, Transaction, Admin, ClassEconomy


def test_get_total_earnings_defensive_checks(client, app):
    """Test that get_total_earnings defensive NULL checks don't break normal operations.
    
    This test verifies that the added defensive programming (checking for
    is not None) doesn't break normal transaction processing.
    """
    with app.app_context():
        # Create a teacher
        teacher = Admin(
            username="test_teacher",
            totp_secret="test_secret"
        )
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST123"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            display_name='Test Class',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent",
            last_initial="A",
            block="Period 1",
            salt=get_random_salt(),
            first_half_hash="test_hash_1",
            dob_sum=2025
        )
        db.session.add(student)
        db.session.commit()
        
        # Create a normal transaction with a valid amount
        valid_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('10.50'),
            description="Valid earning",
            is_void=False
        )
        db.session.add(valid_tx)
        db.session.commit()
        
        # Verify normal case works with the is not None check
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 10.50
        
        # Deprecated teacher-only path should not return cross-class aggregates.
        earnings_by_teacher = student.get_total_earnings(teacher_id=teacher.id)
        assert earnings_by_teacher == 0.0
        
        # Unscoped path should not return cross-class aggregates.
        earnings_all = student.get_total_earnings()
        assert earnings_all == 0.0
        
        # Add another transaction to verify aggregation still works
        another_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('5.25'),
            description="Another earning",
            is_void=False
        )
        db.session.add(another_tx)
        db.session.commit()
        
        # Should now be 15.75
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 15.75


def test_get_total_earnings_with_negative_amounts(client, app):
    """Test that get_total_earnings correctly filters negative amounts (expenses)."""
    with app.app_context():
        # Create a teacher
        teacher = Admin(
            username="test_teacher2",
            totp_secret="test_secret"
        )
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST456"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            display_name='Test Class 2',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent2",
            last_initial="B",
            block="Period 2",
            salt=get_random_salt(),
            first_half_hash="test_hash_2",
            dob_sum=2026
        )
        db.session.add(student)
        db.session.commit()
        
        # Create positive transactions (earnings)
        positive_tx1 = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('15.00'),
            description="Earning 1",
            is_void=False
        )
        positive_tx2 = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('25.50'),
            description="Earning 2",
            is_void=False
        )
        
        # Create negative transaction (expense) - should not be counted in earnings
        negative_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('-10.00'),
            description="Expense",
            is_void=False
        )
        
        # Create voided transaction - should not be counted
        voided_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('100.00'),
            description="Voided earning",
            is_void=True
        )
        
        db.session.add_all([positive_tx1, positive_tx2, negative_tx, voided_tx])
        db.session.commit()
        
        # Earnings should only include positive, non-voided transactions
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 40.50  # 15.00 + 25.50


def test_get_total_earnings_with_zero_amount(client, app):
    """Test that get_total_earnings handles zero amounts correctly."""
    with app.app_context():
        # Create a teacher
        teacher = Admin(
            username="test_teacher3",
            totp_secret="test_secret"
        )
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST789"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            display_name='Test Class 3',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent3",
            last_initial="C",
            block="Period 3",
            salt=get_random_salt(),
            first_half_hash="test_hash_3",
            dob_sum=2027
        )
        db.session.add(student)
        db.session.commit()
        
        # Create a transaction with zero amount
        zero_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('0.00'),
            description="Zero transaction",
            is_void=False
        )
        
        # Create a positive transaction
        positive_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('5.00'),
            description="Positive transaction",
            is_void=False
        )
        
        db.session.add_all([zero_tx, positive_tx])
        db.session.commit()
        
        # Earnings should not include zero amounts (> 0 condition)
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 5.00


def test_get_total_earnings_with_mocked_null_amount(client, app):
    """Test that get_total_earnings handles NULL amounts without crashing.
    
    This test mocks the transactions relationship to return transactions with
    NULL amounts, simulating corrupted production data. Verifies that the
    defensive NULL check prevents the crash.
    """
    with app.app_context():
        # Create a teacher
        teacher = Admin(
            username="test_teacher4",
            totp_secret="test_secret"
        )
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST999"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            display_name='Test Class 4',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent4",
            last_initial="D",
            block="Period 4",
            salt=get_random_salt(),
            first_half_hash="test_hash_4",
            dob_sum=2028
        )
        db.session.add(student)
        db.session.commit()
        
        # Create a valid transaction
        valid_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('20.00'),
            description="Valid transaction",
            is_void=False
        )
        db.session.add(valid_tx)
        db.session.commit()
        
        # Create a mock transaction object with NULL amount
        class MockTransaction:
            def __init__(self, amount, join_code, teacher_id, is_void, description):
                self.amount = amount
                self.join_code = join_code
                self.teacher_id = teacher_id
                self.is_void = is_void
                self.description = description
        
        # Mock the transactions relationship to include a NULL amount transaction
        mock_transactions = [
            valid_tx,  # Real transaction with amount=20.00
            MockTransaction(None, join_code, teacher.id, False, "Corrupted"),  # NULL amount
            MockTransaction(Decimal('15.00'), join_code, teacher.id, False, "Valid 2"),
        ]
        
        with patch.object(Student, 'transactions', new_callable=PropertyMock) as mock_txs:
            mock_txs.return_value = mock_transactions
            
            # This should NOT crash - the NULL check should skip the NULL transaction
            earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
            
            # Should return 20.00 + 15.00 = 35.00, skipping the NULL amount
            assert earnings == 35.00
            
            # Deprecated teacher-only path should not return cross-class aggregates.
            earnings_by_teacher = student.get_total_earnings(teacher_id=teacher.id)
            assert earnings_by_teacher == 0.0
            
            # Unscoped path should not return cross-class aggregates.
            earnings_all = student.get_total_earnings()
            assert earnings_all == 0.0
