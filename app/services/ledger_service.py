from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import BalanceCache, Transaction, TransactionStatus, _quantize_currency
from app.utils.seat_scope import get_seat_ids_for_student_join, transaction_scope_filter
from app.utils.time import ensure_utc, utc_now


def _non_void_filter():
    return Transaction.is_void.isnot(True)


def get_last_payroll_time(student_id: int | None = None, join_code: str | None = None):
    """Return the most recent payroll anchor without mutating any state."""
    if student_id:
        query = Transaction.query.filter(
            Transaction.student_id == student_id,
            Transaction.type.in_(["payroll", "manual_payment"]),
        )
    else:
        query = Transaction.query.filter_by(type="payroll")

    if join_code:
        query = query.filter(Transaction.join_code == join_code)

    last_payroll_tx = query.order_by(Transaction.timestamp.desc()).first()
    return ensure_utc(last_payroll_tx.timestamp) if last_payroll_tx else None


def _get_balance_cache(student_id: int, join_code: str):
    seat_ids = get_seat_ids_for_student_join(student_id, join_code)
    if seat_ids:
        cache = BalanceCache.query.filter(
            BalanceCache.join_code == join_code,
            BalanceCache.seat_id.in_(seat_ids),
        ).first()
        if cache:
            return cache
    return BalanceCache.query.filter_by(student_id=student_id, join_code=join_code).first()


def _transaction_scope(student_id: int, join_code: str):
    seat_ids = get_seat_ids_for_student_join(student_id, join_code)
    if seat_ids:
        return transaction_scope_filter(Transaction, student_id, seat_ids)
    return Transaction.student_id == student_id


def _get_posted_balance_fallback(student_id: int, join_code: str, account_type: str) -> Decimal:
    tx_scope = _transaction_scope(student_id, join_code)
    all_non_void = db.session.query(db.func.sum(Transaction.amount)).filter(
        tx_scope,
        Transaction.join_code == join_code,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        tx_scope,
        Transaction.join_code == join_code,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(all_non_void - pending)


def get_posted_balance(student_id: int, join_code: str, account_type: str) -> Decimal:
    """Read the posted balance snapshot for a single account without side effects."""
    if not join_code:
        return Decimal("0.00")

    cache = _get_balance_cache(student_id, join_code)
    if cache:
        cents = (
            cache.posted_checking_balance_cents
            if account_type == "checking"
            else cache.posted_savings_balance_cents
        )
        return _quantize_currency(Decimal(cents) / 100)

    return _get_posted_balance_fallback(student_id, join_code, account_type)


def get_pending_balance_delta(student_id: int, join_code: str, account_type: str) -> Decimal:
    """Return the pending delta for an account without mutating settlement state."""
    if not join_code:
        return Decimal("0.00")

    tx_scope = _transaction_scope(student_id, join_code)
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        tx_scope,
        Transaction.join_code == join_code,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(pending)


def get_available_balance(student_id: int, join_code: str, account_type: str) -> Decimal:
    """Return posted + pending balance for an account under the current policy model."""
    return _quantize_currency(
        get_posted_balance(student_id, join_code, account_type)
        + get_pending_balance_delta(student_id, join_code, account_type)
    )


def get_available_balances(student_id: int, join_code: str) -> tuple[Decimal, Decimal]:
    """Return checking and savings available balances without side effects."""
    return (
        get_available_balance(student_id, join_code, "checking"),
        get_available_balance(student_id, join_code, "savings"),
    )


def create_pending_transaction(
    *,
    student_id: int,
    teacher_id: int | None,
    join_code: str | None,
    amount,
    account_type: str,
    type: str,
    description: str,
    original_transaction_id: int | None = None,
    policy_id: int | None = None,
) -> Transaction:
    """Create a pending transaction row as the canonical write path for ledger mutations."""
    transaction = Transaction(
        student_id=student_id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=_quantize_currency(amount),
        account_type=account_type,
        status=TransactionStatus.PENDING,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )
    db.session.add(transaction)
    return transaction


def create_transfer_pair(
    *,
    student_id: int,
    teacher_id: int | None,
    join_code: str | None,
    amount,
    from_account: str,
    to_account: str,
    withdraw_description: str,
    deposit_description: str,
) -> tuple[Transaction, Transaction]:
    """Create the canonical pending transfer pair."""
    quantized_amount = _quantize_currency(amount)
    withdraw_tx = create_pending_transaction(
        student_id=student_id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=-quantized_amount,
        account_type=from_account,
        type="Withdrawal",
        description=withdraw_description,
    )
    deposit_tx = create_pending_transaction(
        student_id=student_id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=quantized_amount,
        account_type=to_account,
        type="Deposit",
        description=deposit_description,
    )
    return withdraw_tx, deposit_tx


def apply_monthly_savings_interest(student, *, teacher_id: int | None, join_code: str | None, annual_rate=Decimal("0.045")):
    """Command to post monthly savings interest through the ledger authority."""
    if not student or not join_code:
        return None

    now = utc_now()
    this_month = now.month
    this_year = now.year

    for tx in student.transactions:
        tx_timestamp = ensure_utc(tx.timestamp)
        if (
            tx.join_code == join_code
            and tx.account_type == "savings"
            and tx.description == "Monthly Savings Interest"
            and tx_timestamp
            and tx_timestamp.month == this_month
            and tx_timestamp.year == this_year
        ):
            return None

    eligible_balance = Decimal("0.00")
    for tx in student.transactions:
        if tx.join_code != join_code or tx.account_type != "savings" or tx.is_void or tx.amount is None:
            continue
        if tx.amount <= Decimal("0.00"):
            continue
        if tx.type == "Interest" or "Interest" in (tx.description or ""):
            continue
        available_at = ensure_utc(tx.date_funds_available)
        if available_at and (now - available_at).days >= 30:
            eligible_balance += _quantize_currency(tx.amount)

    monthly_rate = annual_rate / Decimal("12")
    interest = _quantize_currency(eligible_balance * monthly_rate)
    if interest <= Decimal("0.00"):
        return None

    return create_pending_transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=interest,
        account_type="savings",
        type="Interest",
        description="Monthly Savings Interest",
    )
