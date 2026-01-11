from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db
from app.models import Transaction


def evaluate_overdraft_allowance(student, debit_amount, banking_settings, teacher_id=None, join_code=None):
    """
    Check whether a checking debit can proceed based on balances and overdraft protection.

    Returns (allowed, shortfall, checking_balance, savings_balance).
    """
    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)

    if debit_amount <= 0:
        return True, 0.0, checking_balance, savings_balance

    if checking_balance >= debit_amount:
        return True, 0.0, checking_balance, savings_balance

    shortfall = debit_amount - checking_balance
    if banking_settings and banking_settings.overdraft_protection_enabled and savings_balance >= shortfall:
        return True, shortfall, checking_balance, savings_balance

    return False, shortfall, checking_balance, savings_balance


def charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=None, join_code=None, force=False):
    """
    Charge an overdraft fee if enabled.

    Args:
        force: Charge fee even if balance is non-negative (declined transaction).
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, 0.0

    current_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)

    # Only charge if balance is negative unless forced (declined transaction).
    if not force and current_balance >= 0:
        return False, 0.0

    fee_amount = 0.0

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = banking_settings.overdraft_fee_flat_amount
    elif banking_settings.overdraft_fee_type == 'progressive':
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        fee_filters = [
            Transaction.student_id == student.id,
            Transaction.type == 'overdraft_fee',
            Transaction.timestamp >= month_start
        ]
        if join_code:
            fee_filters.append(Transaction.join_code == join_code)
        elif teacher_id:
            fee_filters.append(Transaction.teacher_id == teacher_id)

        overdraft_fee_count = Transaction.query.filter(*fee_filters).count()

        if overdraft_fee_count == 0:
            fee_amount = banking_settings.overdraft_fee_progressive_1 or 0.0
        elif overdraft_fee_count == 1:
            fee_amount = banking_settings.overdraft_fee_progressive_2 or 0.0
        elif overdraft_fee_count >= 2:
            fee_amount = banking_settings.overdraft_fee_progressive_3 or 0.0

        if banking_settings.overdraft_fee_progressive_cap:
            total_filters = [
                Transaction.student_id == student.id,
                Transaction.type == 'overdraft_fee',
                Transaction.timestamp >= month_start
            ]
            if join_code:
                total_filters.append(Transaction.join_code == join_code)
            elif teacher_id:
                total_filters.append(Transaction.teacher_id == teacher_id)

            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                *total_filters
            ).scalar() or 0.0

            # total_fees_this_month is negative, so we negate it
            if abs(total_fees_this_month) + fee_amount > banking_settings.overdraft_fee_progressive_cap:
                fee_amount = max(0, banking_settings.overdraft_fee_progressive_cap - abs(total_fees_this_month))

    if fee_amount > 0:
        overdraft_fee_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=-fee_amount,
            account_type='checking',
            type='overdraft_fee',
            description=(
                f'Overdraft fee (declined transaction balance: ${current_balance:.2f})'
                if force else
                f'Overdraft fee (balance: ${current_balance:.2f})'
            )
        )
        db.session.add(overdraft_fee_tx)
        db.session.flush()
        return True, fee_amount

    return False, 0.0
