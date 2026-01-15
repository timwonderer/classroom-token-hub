"""
Tests for Decimal operation fixes to prevent TypeError and InvalidOperation.

These tests verify that operations on Decimal amounts don't raise:
1. TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'float'
2. decimal.InvalidOperation when using round(sum(...)) with Decimal values
"""
import pytest
from decimal import Decimal
from app.models import (
    Admin, Student, Transaction, StudentBlock, TeacherBlock,
    PayrollSettings, _quantize_currency
)
from app.extensions import db
from app.payroll import get_pay_rate_for_block, calculate_payroll


class TestDecimalOperationsFix:
    """Test that Decimal operations don't cause type errors."""

    def test_get_total_earnings_empty_transactions(self, app):
        """Test get_total_earnings with no transactions (empty sum)."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_empty_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'EMPTY_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create student with no transactions
            student = Student(
                first_name='Empty',
                last_initial='T',
                block='A',
                salt=b'test_salt',
                passphrase_hash='test_hash'
            )
            db.session.add(student)
            db.session.flush()

            student_block = StudentBlock(
                student_id=student.id,
                period='A',
                join_code=join_code
            )
            db.session.add(student_block)
            db.session.commit()

            # Should not raise InvalidOperation
            earnings = student.get_total_earnings(join_code=join_code)
            assert earnings == 0.0
            assert isinstance(earnings, float)

            # Test property as well
            total = student.total_earnings
            assert total == 0.0
            assert isinstance(total, float)

    def test_get_total_earnings_with_decimal_amounts(self, app):
        """Test get_total_earnings with Decimal transaction amounts."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_decimal_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'DECIMAL_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create student
            student = Student(
                first_name='Decimal',
                last_initial='T',
                block='A',
                salt=b'test_salt',
                passphrase_hash='test_hash'
            )
            db.session.add(student)
            db.session.flush()

            student_block = StudentBlock(
                student_id=student.id,
                period='A',
                join_code=join_code
            )
            db.session.add(student_block)
            db.session.commit()

            # Add transactions with Decimal amounts
            tx1 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('25.50'),
                account_type='checking',
                type='Attendance',
                description='Payroll'
            )
            tx2 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('30.25'),
                account_type='checking',
                type='Attendance',
                description='Payroll'
            )
            # Negative amount (should not count as earnings)
            tx3 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('-10.00'),
                account_type='checking',
                type='Purchase',
                description='Store purchase'
            )
            db.session.add_all([tx1, tx2, tx3])
            db.session.commit()

            # Should not raise InvalidOperation or TypeError
            earnings = student.get_total_earnings(join_code=join_code)
            assert earnings == 55.75  # 25.50 + 30.25
            assert isinstance(earnings, float)

    def test_get_total_earnings_with_none_description(self, app):
        """Test get_total_earnings with None description (AttributeError fix)."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_none_desc_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'NONE_DESC_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create student
            student = Student(
                first_name='NoneDesc',
                last_initial='T',
                block='A',
                salt=b'test_salt',
                passphrase_hash='test_hash'
            )
            db.session.add(student)
            db.session.flush()

            student_block = StudentBlock(
                student_id=student.id,
                period='A',
                join_code=join_code
            )
            db.session.add(student_block)
            db.session.commit()

            # Add transaction with None description
            tx = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('15.00'),
                account_type='checking',
                type='Attendance',
                description=None  # This was causing AttributeError
            )
            db.session.add(tx)
            db.session.commit()

            # Should not raise AttributeError
            earnings = student.get_total_earnings(join_code=join_code)
            assert earnings == 15.0

            # Test property as well
            total = student.total_earnings
            assert total == 15.0

    def test_pay_rate_decimal_division(self, app):
        """Test that pay_rate division works with Decimal values."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_payrate_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            # Create payroll settings with Decimal pay_rate
            payroll_settings = PayrollSettings(
                teacher_id=teacher.id,
                block='A',
                is_active=True,
                pay_rate=Decimal('0.50'),  # $0.50 per minute
                settings_mode='simple'
            )
            db.session.add(payroll_settings)
            db.session.commit()

            # Should not raise TypeError
            rate_per_second = get_pay_rate_for_block('A', teacher_id=teacher.id)
            
            # $0.50 per minute = $0.50 / 60 per second
            expected = 0.50 / 60.0
            assert abs(rate_per_second - expected) < 0.0001
            assert isinstance(rate_per_second, float)

    def test_student_balances_with_decimals(self, app):
        """Test student balance calculations with Decimal amounts."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_balance_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'BALANCE_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create student
            student = Student(
                first_name='Balance',
                last_initial='T',
                block='A',
                salt=b'test_salt',
                passphrase_hash='test_hash'
            )
            db.session.add(student)
            db.session.flush()

            student_block = StudentBlock(
                student_id=student.id,
                period='A',
                join_code=join_code
            )
            db.session.add(student_block)
            db.session.commit()

            # Add checking transaction
            tx1 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('100.00'),
                account_type='checking',
                type='Deposit',
                description='Initial deposit'
            )
            # Add savings transaction
            tx2 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('50.00'),
                account_type='savings',
                type='Deposit',
                description='Savings deposit'
            )
            db.session.add_all([tx1, tx2])
            db.session.commit()

            # Should not raise any errors
            checking = student.get_checking_balance(join_code=join_code)
            savings = student.get_savings_balance(join_code=join_code)

            assert checking == Decimal('100.00')
            assert savings == Decimal('50.00')

    def test_calculate_payroll_with_decimal_settings(self, app):
        """Test payroll calculation with Decimal pay_rate settings."""
        with app.app_context():
            from datetime import datetime, timezone, timedelta
            from app.models import TapEvent

            # Create teacher
            teacher = Admin(
                username='teacher_payroll_calc_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'PAYROLL_CALC_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create payroll settings
            payroll_settings = PayrollSettings(
                teacher_id=teacher.id,
                block='A',
                is_active=True,
                pay_rate=Decimal('0.60'),  # $0.60 per minute
                settings_mode='simple'
            )
            db.session.add(payroll_settings)

            # Create student
            student = Student(
                first_name='Payroll',
                last_initial='T',
                block='A',
                salt=b'test_salt',
                passphrase_hash='test_hash'
            )
            db.session.add(student)
            db.session.flush()

            student_block = StudentBlock(
                student_id=student.id,
                period='A',
                join_code=join_code
            )
            db.session.add(student_block)
            db.session.commit()

            # Create tap events (10 minutes of work)
            now = datetime.now(timezone.utc)
            tap_in = TapEvent(
                student_id=student.id,
                event_type='in',
                timestamp=now - timedelta(minutes=10),
                block='A',
                join_code=join_code
            )
            tap_out = TapEvent(
                student_id=student.id,
                event_type='out',
                timestamp=now,
                block='A',
                join_code=join_code
            )
            db.session.add_all([tap_in, tap_out])
            db.session.commit()

            # Calculate payroll - should not raise TypeError
            last_payroll = now - timedelta(hours=1)
            summary = calculate_payroll([student], last_payroll, teacher_id=teacher.id)

            # 10 minutes * $0.60/min = $6.00
            assert student.id in summary
            assert abs(summary[student.id] - 6.00) < 0.01
