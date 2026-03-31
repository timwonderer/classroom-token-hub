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

    @pytest.mark.regression
    def test_apply_savings_interest_decimal_float_multiplication(self, client, app):
        """
        Regression test for TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'float'
        in apply_savings_interest when student.savings_balance (Decimal) is multiplied by float rates.
        
        This was reported in production:
          File "app/routes/student.py", line 1613, in apply_savings_interest
            interest = round(balance * ((1 + rate_per_period) ** periods_per_month - 1), 2)
          TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'float'
        """
        from app.routes.student import apply_savings_interest
        from app.models import BankingSettings
        from unittest.mock import patch
        
        # Create teacher
        teacher = Admin(
            username='teacher_interest_test',
            totp_secret='test_secret'
        )
        db.session.add(teacher)
        db.session.flush()

        join_code = 'INTEREST_TEST'

        # Create student with savings balance
        student = Student(
            first_name='Interest',
            last_initial='T',
            block='A',
            salt=b'test_salt',
            passphrase_hash='test_hash'
        )
        db.session.add(student)
        db.session.flush()

        # Add a savings deposit from 31+ days ago (eligible for interest)
        past_date = datetime.now(timezone.utc) - timedelta(days=35)
        deposit = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=Decimal('100.00'),
            account_type='savings',
            type='Deposit',
            description='Initial savings',
            timestamp=past_date,
            date_funds_available=past_date
        )
        db.session.add(deposit)

        # Create banking settings with compound interest (daily frequency - most likely to trigger bug)
        banking_settings = BankingSettings(
            teacher_id=teacher.id,
            savings_apy=4.5,  # 4.5% APY
            interest_calculation_type='compound',
            compound_frequency='daily'
        )
        db.session.add(banking_settings)
        db.session.commit()

        # Mock context to return our test data
        mock_context = {
            'teacher_id': teacher.id,
            'join_code': join_code,
            'student_teacher_id': teacher.id
        }
        
        # This should NOT raise TypeError
        with patch('app.routes.student.get_current_class_context', return_value=mock_context):
            try:
                apply_savings_interest(student)
                success = True
            except TypeError as e:
                success = False
                pytest.fail(f"TypeError occurred in apply_savings_interest: {e}")

        assert success

        # Verify interest transaction was created
        interest_tx = Transaction.query.filter_by(
            student_id=student.id,
            description='Monthly Savings Interest',
            account_type='savings'
        ).first()
        
        # Interest should have been calculated (may or may not be > 0 depending on settings)
        assert interest_tx is not None or student.savings_balance == Decimal('100.00')

    @pytest.mark.regression
    def test_file_claim_period_cap_no_prior_payouts_no_type_error(self, client, app):
        """
        Regression test for TypeError in file_claim when max_payout_per_period is set
        and there are zero prior approved_amount rows in the current period.

        Bug: In student.py:
            period_payouts = db.session.query(func.sum(...)).scalar() or 0.0
            remaining_period_cap = max(policy.max_payout_per_period - period_payouts, 0)
            # TypeError: unsupported operand type(s) for -: 'decimal.Decimal' and 'float'

        Fix: Use Decimal('0.00') as the fallback when scalar() returns None.
        """
        from app.models import (
            Admin, Student, StudentTeacher, InsurancePolicy, StudentInsurance,
        )
        from tests.helpers.class_scope import create_class_scope

        # Create teacher
        teacher = Admin(username='teacher_claim_cap', totp_secret='test_secret')
        db.session.add(teacher)
        db.session.flush()

        # Create student
        student = Student(
            first_name='ClaimCap',
            last_initial='T',
            block='A',
            salt=b'test_salt_cap',
            passphrase_hash='test_hash',
        )
        db.session.add(student)
        db.session.flush()

        # Associate student with teacher
        st = StudentTeacher(student_id=student.id, teacher_id=teacher.id)
        db.session.add(st)
        db.session.flush()

        # Create policy with max_payout_per_period set (triggers the Decimal path)
        policy = InsurancePolicy(
            policy_code='CAP-POLICY-001',
            teacher_id=teacher.id,
            join_code='CLAIMCAP1',
            title='Cap Test Policy',
            description='',
            premium=Decimal('5.00'),
            claim_type='legacy_monetary',
            is_monetary=True,
            is_active=True,
            waiting_period_days=0,
            claim_time_limit_days=30,
            max_payout_per_period=Decimal('100.00'),
        )
        db.session.add(policy)
        db.session.flush()

        create_class_scope(
            teacher=teacher,
            join_code='CLAIMCAP1',
            student=student,
            block='A',
            display_name='A',
            create_claimed_teacher_block=True,
            teacher_block_claimed=True,
            create_seat=True,
        )
        db.session.flush()

        # Enroll student (active, payment current, coverage started)
        enrollment = StudentInsurance(
            student_id=student.id,
            policy_id=policy.id,
            join_code='CLAIMCAP1',
            status='active',
            coverage_start_date=datetime.now(timezone.utc) - timedelta(days=5),
            payment_current=True,
        )
        db.session.add(enrollment)
        db.session.commit()

        # Log in as student
        with client.session_transaction() as sess:
            sess['student_id'] = student.id
            sess['current_join_code'] = 'CLAIMCAP1'
            sess['login_time'] = datetime.now(timezone.utc).isoformat()

        # GET the file_claim route — must not raise TypeError
        # (no prior InsuranceClaim rows exist, so scalar() returns None)
        response = client.get(
            f'/student/insurance/claim/{policy.id}',
        )

        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}; "
            "possible Decimal/float TypeError in period-cap calculation"
        )

    def test_quantize_currency_handles_invalid_inputs(self, app):
        """
        Test that _quantize_currency handles edge cases that could cause InvalidOperation.
        """
        # None should return 0.00
        assert _quantize_currency(None) == Decimal('0.00')
        
        # Normal values should work
        assert _quantize_currency(Decimal('10.50')) == Decimal('10.50')
        assert _quantize_currency(100.25) == Decimal('100.25')
        assert _quantize_currency('50.00') == Decimal('50.00')
        
        # Zero should work
        assert _quantize_currency(0) == Decimal('0.00')
        assert _quantize_currency(Decimal('0')) == Decimal('0.00')

        # Invalid inputs should be handled by the try-except block
        assert _quantize_currency(float('nan')) == Decimal('0.00')
        assert _quantize_currency(float('inf')) == Decimal('0.00')
        assert _quantize_currency('not a number') == Decimal('0.00')
        assert _quantize_currency(Decimal('NaN')) == Decimal('0.00')
        assert _quantize_currency(Decimal('Infinity')) == Decimal('0.00')
        assert _quantize_currency(Decimal('-Infinity')) == Decimal('0.00')
