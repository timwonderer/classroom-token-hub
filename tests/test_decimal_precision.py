"""
Tests for Decimal precision in financial calculations.

These tests verify that the fixes for floating-point rounding bugs work correctly:
1. Transfers that zero out checking account don't trigger -0.00 overdraft fees
2. Partial rent payments with problematic float values can be fully paid off
"""
import pytest
from decimal import Decimal
from datetime import datetime
from app.models import (
    Admin, Student, Transaction, StudentBlock, TeacherBlock,
    RentSettings, RentPayment, BankingSettings, _quantize_currency
)
from app.extensions import db
from app.utils.overdraft import charge_overdraft_fee_if_needed


class TestDecimalPrecision:
    """Test that Decimal types fix floating-point rounding bugs."""

    def test_quantize_currency_helper(self):
        """Test that _quantize_currency properly handles various inputs."""
        assert _quantize_currency(100.00) == Decimal('100.00')
        assert _quantize_currency(100.123456) == Decimal('100.12')
        assert _quantize_currency(0.0) == Decimal('0.00')
        assert _quantize_currency(-0.0) == Decimal('0.00')
        assert _quantize_currency(None) == Decimal('0.00')
        assert _quantize_currency(Decimal('50.50')) == Decimal('50.50')

        # Test rounding (ROUND_HALF_EVEN - banker's rounding)
        assert _quantize_currency(10.125) == Decimal('10.12')  # Rounds to even (2)
        assert _quantize_currency(10.135) == Decimal('10.14')  # Rounds to even (4)
        assert _quantize_currency(10.126) == Decimal('10.13')  # Rounds up (not halfway)

    def test_transfer_to_zero_no_overdraft_fee(self, app):
        """
        CRITICAL BUG FIX TEST: Transfer that zeros out checking should not trigger overdraft fee.

        Bug: Student transfers exact checking balance to savings, balance becomes -0.00 due to
        floating-point errors, triggering $35 overdraft fee.

        Fix: Use Decimal for exact representation and normalize near-zero balances.
        """
        with app.app_context():
            # Create teacher with overdraft fees enabled
            teacher = Admin(
                username='teacher_overdraft_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'OVERDRAFT_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create banking settings with overdraft fees
            banking_settings = BankingSettings(
                teacher_id=teacher.id,
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)

            # Create student
            student = Student(
                first_name='Test',
                last_initial='S',
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

            # Give student $100.00 in checking
            initial_deposit = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('100.00'),
                account_type='checking',
                type='Initial Deposit',
                description='Starting balance'
            )
            db.session.add(initial_deposit)
            db.session.commit()

            # Verify initial balance
            checking_balance = student.get_checking_balance(join_code=join_code)
            assert checking_balance == Decimal('100.00')

            # Transfer EXACT balance to savings (this was triggering the bug)
            transfer_amount = Decimal('100.00')

            # Withdrawal from checking
            withdrawal_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=-transfer_amount,
                account_type='checking',
                type='Withdrawal',
                description='Transfer to savings'
            )
            db.session.add(withdrawal_tx)

            # Deposit to savings
            deposit_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=transfer_amount,
                account_type='savings',
                type='Deposit',
                description='Transfer from checking'
            )
            db.session.add(deposit_tx)
            db.session.commit()

            # Check balance after transfer
            checking_balance_after = student.get_checking_balance(join_code=join_code)
            savings_balance_after = student.get_savings_balance(join_code=join_code)

            # CRITICAL: Balance should be exactly 0.00, not -0.00
            assert checking_balance_after == Decimal('0.00')
            assert savings_balance_after == Decimal('100.00')

            # CRITICAL: No overdraft fee should be charged
            fee_charged, fee_amount = charge_overdraft_fee_if_needed(
                student,
                banking_settings,
                teacher_id=teacher.id,
                join_code=join_code,
                force=False
            )

            assert fee_charged is False
            assert fee_amount == Decimal('0.00')

            # Verify no overdraft fee transaction was created
            overdraft_txs = Transaction.query.filter_by(
                student_id=student.id,
                join_code=join_code,
                type='overdraft_fee'
            ).all()
            assert len(overdraft_txs) == 0

            # Final balance should still be 0.00
            final_checking = student.get_checking_balance(join_code=join_code)
            assert final_checking == Decimal('0.00')

    def test_partial_rent_payment_rounding(self, app):
        """
        CRITICAL BUG FIX TEST: Partial rent payments with float-problematic values should pay off completely.

        Bug: Student pays rent in multiple payments. Due to float precision errors, a tiny
        unpayable balance remains (e.g., $0.0000001).

        Fix: Use Decimal for exact representation in rent calculations.
        """
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_rent_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'RENT_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create rent settings with incremental payments enabled
            rent_settings = RentSettings(
                teacher_id=teacher.id,
                block='A',
                is_enabled=True,
                rent_amount=Decimal('50.00'),  # Total rent
                allow_incremental_payment=True
            )
            db.session.add(rent_settings)

            # Create student
            student = Student(
                first_name='Rent',
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

            # Give student money to pay rent
            initial_deposit = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('60.00'),
                account_type='checking',
                type='Initial Deposit',
                description='Starting balance'
            )
            db.session.add(initial_deposit)
            db.session.commit()

            now = datetime.now()
            current_month = now.month
            current_year = now.year

            # Make first partial payment - problematic float value
            # 33.33 is a repeating decimal in binary, causes precision issues
            payment1_amount = Decimal('33.33')

            payment1 = RentPayment(
                student_id=student.id,
                period='A',
                join_code=join_code,
                amount_paid=payment1_amount,
                period_month=current_month,
                period_year=current_year,
                was_late=False
            )
            db.session.add(payment1)

            rent_tx1 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=-payment1_amount,
                account_type='checking',
                type='Rent Payment',
                description='Partial rent payment 1/2'
            )
            db.session.add(rent_tx1)
            db.session.commit()

            # Calculate remaining rent
            total_due = Decimal('50.00')
            paid_so_far = payment1_amount
            remaining = _quantize_currency(total_due - paid_so_far)

            # Should be exactly $16.67
            assert remaining == Decimal('16.67')

            # Make second payment for exact remaining amount
            payment2_amount = remaining

            payment2 = RentPayment(
                student_id=student.id,
                period='A',
                join_code=join_code,
                amount_paid=payment2_amount,
                period_month=current_month,
                period_year=current_year,
                was_late=False
            )
            db.session.add(payment2)

            rent_tx2 = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=-payment2_amount,
                account_type='checking',
                type='Rent Payment',
                description='Final rent payment 2/2'
            )
            db.session.add(rent_tx2)
            db.session.commit()

            # Calculate total paid
            all_payments = RentPayment.query.filter_by(
                student_id=student.id,
                period='A',
                join_code=join_code,
                period_month=current_month,
                period_year=current_year
            ).all()

            total_paid = sum(_quantize_currency(p.amount_paid) for p in all_payments)

            # CRITICAL: Total should equal exactly $50.00
            assert total_paid == Decimal('50.00')

            # CRITICAL: Remaining balance should be exactly $0.00, not $0.0000001
            remaining_final = _quantize_currency(total_due - total_paid)
            assert remaining_final == Decimal('0.00')

            # Student should have exactly $10.00 left in checking (60 - 50)
            final_checking = student.get_checking_balance(join_code=join_code)
            assert final_checking == Decimal('10.00')

    def test_near_zero_balance_normalization(self, app):
        """Test that near-zero balances are normalized to exactly zero."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_zero_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'ZERO_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create banking settings with overdraft fees
            banking_settings = BankingSettings(
                teacher_id=teacher.id,
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)

            # Create student
            student = Student(
                first_name='Zero',
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

            # Test various near-zero balances
            test_cases = [
                Decimal('0.001'),   # Less than 1 cent positive
                Decimal('-0.001'),  # Less than 1 cent negative
                Decimal('0.009'),   # Almost 1 cent positive
                Decimal('-0.009'),  # Almost 1 cent negative
            ]

            for near_zero_amount in test_cases:
                # Create transaction with near-zero amount
                tx = Transaction(
                    student_id=student.id,
                    teacher_id=teacher.id,
                    join_code=join_code,
                    amount=near_zero_amount,
                    account_type='checking',
                    type='Test',
                    description=f'Near-zero test: {near_zero_amount}'
                )
                db.session.add(tx)
                db.session.commit()

                # Get balance
                balance = student.get_checking_balance(join_code=join_code)

                # Near-zero balances should NOT trigger overdraft fee
                fee_charged, fee_amount = charge_overdraft_fee_if_needed(
                    student,
                    banking_settings,
                    teacher_id=teacher.id,
                    join_code=join_code,
                    force=False
                )

                assert fee_charged is False, f"Fee charged for balance {balance} from amount {near_zero_amount}"
                assert fee_amount == Decimal('0.00')

                # Clean up for next test
                db.session.delete(tx)
                db.session.commit()

    def test_actually_negative_balance_charges_fee(self, app):
        """Test that genuinely negative balances still trigger overdraft fees correctly."""
        with app.app_context():
            # Create teacher
            teacher = Admin(
                username='teacher_negative_test',
                totp_secret='test_secret'
            )
            db.session.add(teacher)
            db.session.flush()

            join_code = 'NEG_TEST'
            block = TeacherBlock(
                teacher_id=teacher.id,
                join_code=join_code,
                block_name='Period A',
                display_name='Test Period'
            )
            db.session.add(block)

            # Create banking settings with overdraft fees
            banking_settings = BankingSettings(
                teacher_id=teacher.id,
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)

            # Create student
            student = Student(
                first_name='Negative',
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

            # Create a genuinely negative balance (-$10.00)
            negative_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=Decimal('-10.00'),
                account_type='checking',
                type='Overdraft',
                description='Genuinely negative balance'
            )
            db.session.add(negative_tx)
            db.session.commit()

            # Check balance
            balance = student.get_checking_balance(join_code=join_code)
            assert balance == Decimal('-10.00')

            # SHOULD trigger overdraft fee
            fee_charged, fee_amount = charge_overdraft_fee_if_needed(
                student,
                banking_settings,
                teacher_id=teacher.id,
                join_code=join_code,
                force=False
            )

            assert fee_charged is True
            assert fee_amount == Decimal('35.00')

            # Verify fee transaction was created
            overdraft_txs = Transaction.query.filter_by(
                student_id=student.id,
                join_code=join_code,
                type='overdraft_fee'
            ).all()
            assert len(overdraft_txs) == 1
            assert overdraft_txs[0].amount == Decimal('-35.00')

            # Final balance should be -$45.00 (-10 - 35)
            final_balance = student.get_checking_balance(join_code=join_code)
            assert final_balance == Decimal('-45.00')
