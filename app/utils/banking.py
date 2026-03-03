from decimal import Decimal
import logging
from flask import g
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Transaction, TransactionStatus, BalanceCache, AccountType
from app.utils.time import utc_now
from app.utils.seat_scope import get_seat_ids_for_student_join, transaction_scope_filter

logger = logging.getLogger(__name__)

def settle_balances(student_id: int, join_code: str) -> None:
    """
    Atomic settlement of pending transactions into the balance cache.
    
    CRITICAL SAFETY GUARD:
    Raises RuntimeError if called during a read-only request (g.read_only=True).

    This function:
    1. Locks the BalanceCache row for the student/class context (creating if needed).
    2. Fetches all PENDING transactions for this context.
    3. Aggregates their amounts by account type.
    4. Updates the BalanceCache with the net changes.
    5. Transitions transactions to POSTED (or VOID if marked as void).
    
    Args:
        student_id: The ID of the student.
        join_code: The class join code.
    """
    # Guard against write-on-read
    if getattr(g, "read_only", False):
        raise RuntimeError("Settlement attempted during read-only request context")

    try:
        seat_ids = get_seat_ids_for_student_join(student_id, join_code)
        scope_filter = transaction_scope_filter(Transaction, student_id, seat_ids)

        cache_was_created = False
        # 1. Lock (or Create) BalanceCache Row
        # ---------------------------------------------------------
        # We must lock the cache row to prevent concurrent settlements
        # or balance updates for the same student/class.
        cache = None
        if seat_ids:
            cache = (
                BalanceCache.query
                .filter(
                    BalanceCache.join_code == join_code,
                    BalanceCache.seat_id.in_(seat_ids),
                )
                .with_for_update()
                .first()
            )
        if not cache:
            cache = (
                BalanceCache.query
                .filter_by(student_id=student_id, join_code=join_code)
                .with_for_update()
                .first()
            )
        
        if not cache:
            # If cache doesn't exist (e.g. new student), create it.
            # We assume unique constraint protects against race condition insert
            # but usually we're inside a transaction so this insert blocks others.
            try:
                with db.session.begin_nested():
                    cache = BalanceCache(
                        student_id=student_id,
                        seat_id=(seat_ids[0] if seat_ids else None),
                        join_code=join_code,
                    )
                    db.session.add(cache)
                    db.session.flush() # Persist to get ID and lock
                    cache_was_created = True
            except IntegrityError as e:
                # Handle duplicate row races without rolling back the outer transaction.
                logger.warning(f"Race condition creating BalanceCache, retrying fetch: {e}")
                cache = (
                    BalanceCache.query
                    .filter_by(student_id=student_id, join_code=join_code)
                    .with_for_update()
                    .first()
                )
                if not cache:
                    raise

        # 2. Fetch PENDING transactions
        # ---------------------------------------------------------
        pending_txs = (
            Transaction.query
            .filter(
                scope_filter,
                Transaction.join_code == join_code,
                Transaction.status == TransactionStatus.PENDING,
            )
            .order_by(Transaction.timestamp)
            .with_for_update()
            .all()
        )

        # Legacy/direct-write compatibility:
        # absorb posted rows that were written outside settlement and not yet folded into cache.
        unsettled_posted_txs = []
        if not cache_was_created:
            unsettled_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.join_code == join_code,
                    Transaction.status == TransactionStatus.POSTED,
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .order_by(Transaction.timestamp)
                .with_for_update()
                .all()
            )

        # Seed a newly created cache from existing posted/non-pending ledger rows.
        # This preserves legacy balances when cache rows are introduced lazily at read time.
        if cache_was_created:
            seed_time = utc_now()
            all_checking = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.join_code == join_code,
                Transaction.account_type == 'checking',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')
            pending_checking = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.join_code == join_code,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.account_type == 'checking',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')

            all_savings = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.join_code == join_code,
                Transaction.account_type == 'savings',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')
            pending_savings = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.join_code == join_code,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.account_type == 'savings',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')

            cache.posted_checking_balance_cents = int((all_checking - pending_checking) * 100)
            cache.posted_savings_balance_cents = int((all_savings - pending_savings) * 100)
            cache.last_settlement_at = seed_time

            seeded_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.join_code == join_code,
                    Transaction.status == TransactionStatus.POSTED,
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .with_for_update()
                .all()
            )
            for tx in seeded_posted_txs:
                tx.posted_at = seed_time

        if not pending_txs and not unsettled_posted_txs:
            # Nothing to settle
            return

        checking_delta_cents = 0
        savings_delta_cents = 0
        now = utc_now()
        
        cnt_posted = 0
        cnt_voided = 0
        
        for tx in pending_txs:
            # Fill missing data if needed (defensive)
            if not tx.posted_at:
                tx.posted_at = now
            
            if tx.amount_cents is None:
                # Fallback if validation missed this (should be prevented by strict creation)
                tx.amount_cents = int(tx.amount * 100)

            # Handle Void Logic for Pending
            if tx.is_void:
                # If a transaction is pending AND is_void, it means it was voided
                # before it ever posted. We simply mark it as VOID status and
                # do NOT add its amount to the ledger balance.
                tx.status = TransactionStatus.VOID
                if not tx.voided_at:
                    tx.voided_at = now
                cnt_voided += 1
                continue
            
            # Process Valid Transaction
            tx.status = TransactionStatus.POSTED
            
            # Account Type Check (handle string or Enum)
            # Database stores string 'checking'/'savings'
            acct_type = str(tx.account_type).lower()
            if acct_type == 'checking' or acct_type == AccountType.CHECKING.value:
                checking_delta_cents += tx.amount_cents
            elif acct_type == 'savings' or acct_type == AccountType.SAVINGS.value:
                savings_delta_cents += tx.amount_cents
            else:
                raise ValueError(
                    f"Unknown account type '{tx.account_type}' for transaction {tx.id}"
                )

            cnt_posted += 1

        for tx in unsettled_posted_txs:
            if not tx.posted_at:
                tx.posted_at = now
            if tx.amount_cents is None:
                tx.amount_cents = int(tx.amount * 100)

            acct_type = str(tx.account_type).lower()
            if acct_type == 'checking' or acct_type == AccountType.CHECKING.value:
                checking_delta_cents += tx.amount_cents
            elif acct_type == 'savings' or acct_type == AccountType.SAVINGS.value:
                savings_delta_cents += tx.amount_cents
            else:
                raise ValueError(
                    f"Unknown account type '{tx.account_type}' for transaction {tx.id}"
                )
            cnt_posted += 1
            
        # 3. Update Cache
        # ---------------------------------------------------------
        cache.posted_checking_balance_cents += checking_delta_cents
        cache.posted_savings_balance_cents += savings_delta_cents
        cache.last_settlement_at = now
        
        logger.info(f"Settled balances for Student {student_id} (Join: {join_code}): "
                    f"Posted {cnt_posted}, Voided {cnt_voided}. "
                    f"Checking Net: {checking_delta_cents}, Savings Net: {savings_delta_cents}")
        
    except Exception as e:
        logger.error(f"Error settling balances for Student {student_id} in {join_code}: {e}")
        raise
