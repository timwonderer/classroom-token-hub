from datetime import datetime, timezone
from app.utils.time import utc_now
from decimal import Decimal, InvalidOperation

from sqlalchemy import func

from app.extensions import db
from app.models import Transaction, TransactionStatus, _quantize_currency


def evaluate_overdraft_allowance(student, debit_amount, banking_settings, teacher_id=None, join_code=None):
    """
    Check whether a checking debit can proceed based on balances and overdraft protection.

    Returns (allowed, shortfall, checking_balance, savings_balance).
    """
    from app.services.ledger_service import get_available_balances

    checking_balance, savings_balance = get_available_balances(student.id, join_code) if join_code else (Decimal('0.00'), Decimal('0.00'))
    try:
        debit_amount = Decimal(str(debit_amount))
    except (TypeError, InvalidOperation):
        return False, Decimal('0.00'), checking_balance, savings_balance

    if debit_amount <= 0:
        return True, Decimal('0.00'), checking_balance, savings_balance

    if checking_balance >= debit_amount:
        return True, Decimal('0.00'), checking_balance, savings_balance

    shortfall = debit_amount - checking_balance
    if banking_settings and banking_settings.overdraft_protection_enabled and savings_balance >= shortfall:
        return True, shortfall, checking_balance, savings_balance

    return False, shortfall, checking_balance, savings_balance


def charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=None, join_code=None, force=False, actor_membership_id=None):
    """
    Charge an overdraft fee if enabled.

    Args:
        force: Charge fee even if balance is non-negative (declined transaction).
        actor_membership_id: ClassMembership.id of the admin who triggered the declined
            transaction, for audit trail purposes.
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, Decimal('0.00')

    from app.services.ledger_service import create_pending_transaction, get_available_balance

    current_balance = _quantize_currency(
        get_available_balance(student.id, join_code, 'checking') if join_code else Decimal('0.00')
    )

    # CRITICAL FIX: Normalize near-zero balances to exactly zero
    # This prevents floating-point errors from triggering fees on -0.00 or -0.0001
    if abs(current_balance) < Decimal('0.01'):  # Less than 1 cent
        current_balance = Decimal('0.00')

    # Only charge if balance is negative unless forced (declined transaction).
    if not force and current_balance >= Decimal('0.00'):
        return False, Decimal('0.00')

    fee_amount = Decimal('0.00')

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = _quantize_currency(banking_settings.overdraft_fee_flat_amount)
    elif banking_settings.overdraft_fee_type == 'progressive':
        now = utc_now()
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
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_1 or 0)
        elif overdraft_fee_count == 1:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_2 or 0)
        elif overdraft_fee_count >= 2:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_3 or 0)

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
            ).scalar()
            total_fees_this_month = _quantize_currency(total_fees_this_month) if total_fees_this_month else Decimal('0.00')
            cap = _quantize_currency(banking_settings.overdraft_fee_progressive_cap)

            # total_fees_this_month is negative, so we negate it
            if abs(total_fees_this_month) + fee_amount > cap:
                fee_amount = max(Decimal('0.00'), cap - abs(total_fees_this_month))

    if fee_amount > 0:
        tx_kwargs = dict(
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
            ),
        )
        overdraft_fee_tx = create_pending_transaction(**tx_kwargs)
        if hasattr(overdraft_fee_tx, 'actor_membership_id'):
            overdraft_fee_tx.actor_membership_id = actor_membership_id
        db.session.flush()
        return True, fee_amount

    return False, Decimal('0.00')
