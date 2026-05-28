from collections import defaultdict
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, tuple_
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


def _empty_balance_dict():
    return {'checking_cents': 0, 'savings_cents': 0, 'earnings': Decimal('0.00')}


def get_batch_balances_by_class_seat(class_seat_pairs):
    """
    Fetch balances keyed by canonical scope tuple (class_id, seat_id).

    Args:
        class_seat_pairs (iterable): Iterable of (class_id, seat_id) tuples.

    Returns:
        defaultdict: Mapping of (class_id, seat_id) ->
            {'checking_cents': int, 'savings_cents': int, 'earnings': Decimal}
    """
    raw_balances = defaultdict(_empty_balance_dict)

    normalized_pairs = {
        (str(class_id), int(seat_id))
        for class_id, seat_id in (class_seat_pairs or [])
        if class_id and seat_id
    }
    if not normalized_pairs:
        return raw_balances

    class_ids = sorted({class_id for class_id, _ in normalized_pairs})
    seat_ids = sorted({seat_id for _, seat_id in normalized_pairs})
    scope_tuple = tuple_(BalanceCache.class_id, BalanceCache.seat_id)
    tx_scope_tuple = tuple_(Transaction.class_id, Transaction.seat_id)

    cache_records = db.session.query(
        BalanceCache.class_id,
        BalanceCache.seat_id,
        BalanceCache.posted_checking_balance_cents,
        BalanceCache.posted_savings_balance_cents
    ).filter(
        BalanceCache.class_id.in_(class_ids),
        BalanceCache.seat_id.in_(seat_ids),
        scope_tuple.in_(list(normalized_pairs)),
    ).all()

    for rec in cache_records:
        key = (str(rec.class_id), int(rec.seat_id))
        raw_balances[key]['checking_cents'] = rec.posted_checking_balance_cents
        raw_balances[key]['savings_cents'] = rec.posted_savings_balance_cents

    pending_sums = db.session.query(
        Transaction.class_id,
        Transaction.seat_id,
        Transaction.account_type,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.class_id.in_(class_ids),
        Transaction.seat_id.in_(seat_ids),
        tx_scope_tuple.in_(list(normalized_pairs)),
        Transaction.status == TransactionStatus.PENDING,
        Transaction.is_void == False
    ).group_by(
        Transaction.class_id,
        Transaction.seat_id,
        Transaction.account_type
    ).all()

    for rec in pending_sums:
        key = (str(rec.class_id), int(rec.seat_id))
        amount_cents = int(_quantize_currency(rec[3]) * 100)
        acct_type = str(rec.account_type).lower()

        if acct_type == 'checking':
            raw_balances[key]['checking_cents'] += amount_cents
        elif acct_type == 'savings':
            raw_balances[key]['savings_cents'] += amount_cents

    earnings_sums = db.session.query(
        Transaction.class_id,
        Transaction.seat_id,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.class_id.in_(class_ids),
        Transaction.seat_id.in_(seat_ids),
        tx_scope_tuple.in_(list(normalized_pairs)),
        Transaction.amount > 0,
        Transaction.is_void == False,
        ~Transaction.description.ilike('Transfer%')
    ).group_by(
        Transaction.class_id,
        Transaction.seat_id
    ).all()

    for rec in earnings_sums:
        key = (str(rec.class_id), int(rec.seat_id))
        raw_balances[key]['earnings'] = _quantize_currency(rec[2])

    return raw_balances


def get_batch_balances_by_student_class(student_class_pairs):
    """
    Fetch balances keyed by (student_id, class_id), backed by canonical seat scope.

    Args:
        student_class_pairs (iterable): Iterable of (student_id, class_id) tuples.

    Returns:
        defaultdict: Mapping of (student_id, class_id) ->
            {'checking_cents': int, 'savings_cents': int, 'earnings': Decimal}
    """
    balances = defaultdict(_empty_balance_dict)
    normalized_pairs = {
        (int(student_id), str(class_id))
        for student_id, class_id in (student_class_pairs or [])
        if student_id and class_id
    }
    if not normalized_pairs:
        return balances

    student_ids = sorted({student_id for student_id, _ in normalized_pairs})
    class_ids = sorted({class_id for _, class_id in normalized_pairs})

    pair_filter = tuple_(BalanceCache.student_id, BalanceCache.class_id).in_(list(normalized_pairs))
    cache_records = db.session.query(
        BalanceCache.student_id,
        BalanceCache.class_id,
        BalanceCache.posted_checking_balance_cents,
        BalanceCache.posted_savings_balance_cents,
    ).filter(
        BalanceCache.student_id.in_(student_ids),
        BalanceCache.class_id.in_(class_ids),
        pair_filter,
    ).all()
    for rec in cache_records:
        key = (int(rec.student_id), str(rec.class_id))
        balances[key]['checking_cents'] += rec.posted_checking_balance_cents
        balances[key]['savings_cents'] += rec.posted_savings_balance_cents

    tx_pair_filter = tuple_(Transaction.student_id, Transaction.class_id).in_(list(normalized_pairs))
    pending_sums = db.session.query(
        Transaction.student_id,
        Transaction.class_id,
        Transaction.account_type,
        func.sum(Transaction.amount),
    ).filter(
        Transaction.student_id.in_(student_ids),
        Transaction.class_id.in_(class_ids),
        tx_pair_filter,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.is_void == False,
    ).group_by(
        Transaction.student_id,
        Transaction.class_id,
        Transaction.account_type,
    ).all()
    for rec in pending_sums:
        key = (int(rec.student_id), str(rec.class_id))
        amount_cents = int(_quantize_currency(rec[3]) * 100)
        acct_type = str(rec.account_type).lower()
        if acct_type == 'checking':
            balances[key]['checking_cents'] += amount_cents
        elif acct_type == 'savings':
            balances[key]['savings_cents'] += amount_cents

    earnings_sums = db.session.query(
        Transaction.student_id,
        Transaction.class_id,
        func.sum(Transaction.amount),
    ).filter(
        Transaction.student_id.in_(student_ids),
        Transaction.class_id.in_(class_ids),
        tx_pair_filter,
        Transaction.amount > 0,
        Transaction.is_void == False,
        ~Transaction.description.ilike('Transfer%'),
    ).group_by(
        Transaction.student_id,
        Transaction.class_id,
    ).all()
    for rec in earnings_sums:
        key = (int(rec.student_id), str(rec.class_id))
        balances[key]['earnings'] += _quantize_currency(rec[2])

    return balances
