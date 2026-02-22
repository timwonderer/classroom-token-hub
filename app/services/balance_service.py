from collections import defaultdict
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from app.extensions import db
from app.models import BalanceCache, Transaction, TransactionStatus

def _quantize_currency(value):
    """
    Convert a value to Decimal and quantize to 2 decimal places for currency.
    """
    if value is None:
        return Decimal('0.00')
    try:
        if isinstance(value, Decimal):
            if not value.is_finite():
                return Decimal('0.00')
            return value.quantize(Decimal('0.01'))
        else:
            quantized = Decimal(str(value)).quantize(Decimal('0.01'))
            if not quantized.is_finite():
                return Decimal('0.00')
            return quantized
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')

def get_batch_balances(join_codes, student_ids):
    """
    Fetch balances for a set of students across specified join codes in batch.

    Args:
        join_codes (list): List of join codes to query.
        student_ids (list): List of student IDs to query.

    Returns:
        dict: Mapping of (student_id, join_code) -> {'checking_cents': int, 'savings_cents': int, 'earnings': Decimal}
    """
    # Initialize balances with cached values
    # Structure: (student_id, join_code) -> {checking_cents, savings_cents, earnings}
    raw_balances = defaultdict(lambda: {'checking_cents': 0, 'savings_cents': 0, 'earnings_cents': 0, 'earnings': Decimal('0.00')})

    if not join_codes or not student_ids:
        return raw_balances

    # 1. Batch fetch POSTED balances from BalanceCache
    cache_records = db.session.query(
        BalanceCache.student_id,
        BalanceCache.join_code,
        BalanceCache.posted_checking_balance_cents,
        BalanceCache.posted_savings_balance_cents
    ).filter(
        BalanceCache.join_code.in_(join_codes),
        BalanceCache.student_id.in_(student_ids)
    ).all()

    for rec in cache_records:
        key = (rec.student_id, rec.join_code)
        raw_balances[key]['checking_cents'] = rec.posted_checking_balance_cents
        raw_balances[key]['savings_cents'] = rec.posted_savings_balance_cents

    # 2. Batch fetch PENDING transactions (sum by student/join_code/account)
    pending_sums = db.session.query(
        Transaction.student_id,
        Transaction.join_code,
        Transaction.account_type,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.join_code.in_(join_codes),
        Transaction.student_id.in_(student_ids),
        Transaction.status == TransactionStatus.PENDING,
        Transaction.is_void == False
    ).group_by(
        Transaction.student_id,
        Transaction.join_code,
        Transaction.account_type
    ).all()

    for rec in pending_sums:
        key = (rec.student_id, rec.join_code)
        amount_cents = int(_quantize_currency(rec[3]) * 100)
        acct_type = str(rec.account_type).lower()

        if acct_type == 'checking':
            raw_balances[key]['checking_cents'] += amount_cents
        elif acct_type == 'savings':
            raw_balances[key]['savings_cents'] += amount_cents

    # 3. Batch fetch TOTAL EARNINGS (legacy calculation logic compatibility)
    # Sum of all positive, non-transfer, non-void transactions
    earnings_sums = db.session.query(
        Transaction.student_id,
        Transaction.join_code,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.join_code.in_(join_codes),
        Transaction.student_id.in_(student_ids),
        Transaction.amount > 0,
        Transaction.is_void == False,
        ~Transaction.description.ilike('Transfer%')
    ).group_by(
        Transaction.student_id,
        Transaction.join_code
    ).all()

    for rec in earnings_sums:
        key = (rec.student_id, rec.join_code)
        # Earnings are just displayed, no need for cent conversion usually but sticking to pattern
        # Note: earnings are derived from sum(amount), so we use that directly.
        raw_balances[key]['earnings'] = _quantize_currency(rec[2])

    return raw_balances
