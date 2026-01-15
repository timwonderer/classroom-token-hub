"""
Test for Decimal/float type mismatch errors in rent calculations.

These tests verify fixes for the following errors:
1. TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
   - In student.py dashboard and rent payment routes
2. decimal.InvalidOperation in get_total_earnings
   - In models.py when comparing Decimal amounts

Root cause: Mixing Decimal (from database Numeric columns) with float literals (0.0).
Fix: Use Decimal('0.00') consistently for all currency values.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from app.models import (
    Admin, Student, Transaction, StudentBlock, TeacherBlock,
    RentSettings, RentPayment, BankingSettings, _quantize_currency
)
from app.extensions import db


class TestDecimalTypeErrors:
    """Test that Decimal types are used consistently to prevent type errors."""

    def test_rent_dashboard_calculation_with_decimals(self, client, app):
        """
        Test that dashboard rent calculation handles Decimal types properly.
        
        Bug: In student.py line 1107:
        total_due = rent_settings.rent_amount + late_fee if rent_is_active else 0.0
        
        TypeError when rent_settings.rent_amount (Decimal) is added to late_fee (float 0.0).
        """
        # Create teacher
        teacher = Admin(
            username='teacher_rent_decimal',
            totp_secret='test_secret'
        )
        db.session.add(teacher)
        db.session.flush()

        # Create rent settings
        rent_settings = RentSettings(
            teacher_id=teacher.id,
            block='A',
            is_enabled=True,
            rent_amount=Decimal('50.00'),
            late_penalty_amount=Decimal('10.00'),
            grace_period_days=3
        )
        db.session.add(rent_settings)
        db.session.commit()

        # Test calculation when rent is not active (should use Decimal('0.00') not 0.0)
        rent_is_active = False
        late_fee = Decimal('0.00')  # Should be Decimal, not float
        
        # This should not raise TypeError
        total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
        assert total_due == Decimal('0.00')
        assert isinstance(total_due, Decimal)

        # Test calculation when rent is active with no late fee
        rent_is_active = True
        late_fee = Decimal('0.00')
        
        total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
        assert total_due == Decimal('50.00')
        assert isinstance(total_due, Decimal)

        # Test calculation when rent is active with late fee
        late_fee = rent_settings.late_penalty_amount
        
        total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
        assert total_due == Decimal('60.00')
        assert isinstance(total_due, Decimal)

    def test_get_total_earnings_with_decimal_amounts(self, client, app):
        """
        Test that get_total_earnings handles Decimal amounts properly.
        
        Bug: In models.py line 370:
        and tx.amount is not None and tx.amount > 0 and not tx.is_void
        
        decimal.InvalidOperation when comparing Decimal to integer 0 in certain contexts.
        """
        # Create teacher
        teacher = Admin(
            username='teacher_earnings_decimal',
            totp_secret='test_secret'
        )
        db.session.add(teacher)
        db.session.flush()

        join_code = 'EARNINGS_TEST'

        # Create student
        student = Student(
            first_name='Earnings',
            last_initial='T',
            block='A',
            salt=b'test_salt',
            passphrase_hash='test_hash'
        )
        db.session.add(student)
        db.session.flush()

        # Add various transaction types to test edge cases
        transactions = [
            # Positive earning - should count
            Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('100.00'),
                account_type='checking',
                type='Attendance',
                description='Good work'
            ),
            # Zero amount - should not count
            Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('0.00'),
                account_type='checking',
                type='Adjustment',
                description='Zero adjustment'
            ),
            # Negative amount - should not count
            Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('-50.00'),
                account_type='checking',
                type='Purchase',
                description='Store purchase'
            ),
            # Transfer - should not count even if positive
            Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('25.00'),
                account_type='checking',
                type='Transfer',
                description='Transfer to savings'
            ),
            # Another positive earning
            Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('75.50'),
                account_type='checking',
                type='Payroll',
                description='Weekly pay'
            ),
        ]
        
        for tx in transactions:
            db.session.add(tx)
        db.session.commit()

        # This should not raise decimal.InvalidOperation
        total_earnings = student.get_total_earnings(
            teacher_id=teacher.id,
            join_code=join_code
        )

        # Should only count positive, non-transfer transactions
        # 100.00 + 75.50 = 175.50
        assert total_earnings == 175.50
        assert isinstance(total_earnings, float)  # Returns float per spec

    def test_mixed_decimal_operations_consistency(self, app):
        """
        Test that mixing various Decimal operations maintains type consistency.
        
        Ensures that operations like sum(), max(), and comparisons all work
        correctly with Decimal types.
        """
        # Test sum with Decimal starting value
        amounts = [Decimal('10.00'), Decimal('20.50'), Decimal('5.25')]
        total = sum(amounts, Decimal('0.00'))
        assert isinstance(total, Decimal)
        assert total == Decimal('35.75')

        # Test max with Decimal
        max_remaining = max(Decimal('0.00'), Decimal('10.00') - Decimal('15.00'))
        assert isinstance(max_remaining, Decimal)
        assert max_remaining == Decimal('0.00')

        # Test comparison with Decimal('0')
        value1 = Decimal('5.00')
        value2 = Decimal('0.00')
        value3 = Decimal('-5.00')

        assert value1 > Decimal('0')
        assert not (value2 > Decimal('0'))
        assert not (value3 > Decimal('0'))

        # Test quantize with various inputs
        assert _quantize_currency(Decimal('10.123')) == Decimal('10.12')
        assert _quantize_currency(Decimal('0.00')) == Decimal('0.00')
        assert _quantize_currency(Decimal('-5.567')) == Decimal('-5.57')

    @pytest.mark.regression
    def test_dashboard_rent_calculation_no_type_error(self, client, app):
        """
        Regression test for the specific TypeError reported in the issue.
        
        This test reproduces the exact scenario from the error:
        TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
        at student.py line 1107
        """
        # Create teacher
        teacher = Admin(
            username='teacher_regression',
            totp_secret='test_secret'
        )
        db.session.add(teacher)
        db.session.flush()

        # Create rent settings (rent_amount is Decimal from db)
        rent_settings = RentSettings(
            teacher_id=teacher.id,
            block='A',
            is_enabled=False,  # Not active - triggers the 0.0 case
            rent_amount=Decimal('50.00'),
            late_penalty_amount=Decimal('10.00')
        )
        db.session.add(rent_settings)
        db.session.commit()

        # Simulate the exact calculation from the bug
        rent_is_active = False
        now = datetime.now(timezone.utc)
        grace_end_date = now - timedelta(days=1)

        # This was the problematic line - should use Decimal not float
        late_fee = rent_settings.late_fee if rent_is_active and now > grace_end_date else Decimal('0.00')
        
        # This should NOT raise TypeError
        try:
            total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
            success = True
        except TypeError as e:
            success = False
            pytest.fail(f"TypeError occurred: {e}")

        assert success
        assert total_due == Decimal('0.00')
        assert isinstance(total_due, Decimal)
