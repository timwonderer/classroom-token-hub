import logging
from flask import g
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Transaction, TransactionStatus, BalanceCache, AccountType, _quantize_currency
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


def _authoritative_posted_totals(student_id: int, join_code: str) -> tuple[int, int]:
    """Return authoritative posted balance totals for one student/class context."""
    rows = (
        db.session.query(
            Transaction.account_type,
            db.func.coalesce(db.func.sum(Transaction.amount_cents), 0),
        )
        .filter(
            Transaction.student_id == student_id,
            Transaction.join_code == join_code,
            Transaction.status == TransactionStatus.POSTED,
            Transaction.is_void == False,
            Transaction.account_type.in_(
                [AccountType.CHECKING.value, AccountType.SAVINGS.value]
            ),
        )
        .group_by(Transaction.account_type)
        .all()
    )

    totals = {
        AccountType.CHECKING.value: 0,
        AccountType.SAVINGS.value: 0,
    }
    for account_type, total_cents in rows:
        acct_type = str(account_type).lower()
        if acct_type in totals:
            totals[acct_type] = int(total_cents or 0)

    return totals[AccountType.CHECKING.value], totals[AccountType.SAVINGS.value]


def settle_pending_transaction_contexts(limit: int | None = None) -> dict[str, int]:
    """
    Sweep every student/class context with unsettled ledger activity.

    Commits each context independently so one failing context does not stop the run.
    """
    context_query = (
        db.session.query(Transaction.student_id, Transaction.join_code)
        .filter(
            Transaction.join_code.isnot(None),
            db.or_(
                Transaction.status == TransactionStatus.PENDING,
                db.and_(
                    Transaction.status == TransactionStatus.POSTED,
                    Transaction.posted_at.is_(None),
                ),
            ),
        )
        .distinct()
        .order_by(Transaction.student_id.asc(), Transaction.join_code.asc())
    )
    if limit is not None:
        context_query = context_query.limit(limit)

    settled_contexts = 0
    failed_contexts = 0

    for student_id, join_code in context_query.yield_per(1000):
        try:
            settle_balances(student_id, join_code)
            db.session.commit()
            settled_contexts += 1
        except Exception:
            db.session.rollback()
            failed_contexts += 1
            logger.exception(
                "Settlement sweep failed for student %s in %s",
                student_id,
                join_code,
            )

    return {
        "settled_contexts": settled_contexts,
        "failed_contexts": failed_contexts,
    }


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
        cache_was_created = False
        # 1. Lock (or Create) BalanceCache Row
        # ---------------------------------------------------------
        # We must lock the cache row to prevent concurrent settlements
        # or balance updates for the same student/class.
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
                    cache = BalanceCache(student_id=student_id, join_code=join_code)
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
            .filter_by(
                student_id=student_id, 
                join_code=join_code, 
                status=TransactionStatus.PENDING
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
                .filter_by(
                    student_id=student_id,
                    join_code=join_code,
                    status=TransactionStatus.POSTED,
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .order_by(Transaction.timestamp)
                .with_for_update()
                .all()
            )

        now = utc_now()
        previous_checking_cents = cache.posted_checking_balance_cents
        previous_savings_cents = cache.posted_savings_balance_cents
        cnt_posted = 0
        cnt_voided = 0

        for tx in pending_txs:
            # Fill missing data if needed (defensive)
            if not tx.posted_at:
                tx.posted_at = now
            
            if tx.amount_cents is None:
                # Fallback if validation missed this (should be prevented by strict creation)
                if tx.amount is None:
                    logger.error(
                        "Refusing to derive amount_cents for transaction %s with null amount",
                        tx.id,
                    )
                    raise ValueError(f"Transaction {tx.id} has null amount during settlement")
                tx.amount_cents = int(_quantize_currency(tx.amount) * 100)

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
            cnt_posted += 1

        for tx in unsettled_posted_txs:
            if not tx.posted_at:
                tx.posted_at = now
            if tx.amount_cents is None:
                if tx.amount is None:
                    logger.error(
                        "Refusing to derive amount_cents for posted transaction %s with null amount",
                        tx.id,
                    )
                    raise ValueError(f"Transaction {tx.id} has null amount during settlement")
                tx.amount_cents = int(_quantize_currency(tx.amount) * 100)
            cnt_posted += 1

        authoritative_checking_cents, authoritative_savings_cents = _authoritative_posted_totals(
            student_id,
            join_code,
        )

        balances_changed = (
            previous_checking_cents != authoritative_checking_cents
            or previous_savings_cents != authoritative_savings_cents
        )
        if cache_was_created or pending_txs or unsettled_posted_txs or balances_changed:
            cache.posted_checking_balance_cents = authoritative_checking_cents
            cache.posted_savings_balance_cents = authoritative_savings_cents
            cache.last_settlement_at = now

        logger.info(
            "Settled balances for Student %s (Join: %s): Posted %s, Voided %s. "
            "Checking %s -> %s, Savings %s -> %s",
            student_id,
            join_code,
            cnt_posted,
            cnt_voided,
            previous_checking_cents,
            authoritative_checking_cents,
            previous_savings_cents,
            authoritative_savings_cents,
        )
        
    except Exception as e:
        logger.error(f"Error settling balances for Student {student_id} in {join_code}: {e}")
        raise
