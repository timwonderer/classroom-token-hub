from datetime import datetime, timezone
import logging
from app import db
from app.models import Transaction, TransactionStatus, BalanceCache, AccountType

logger = logging.getLogger(__name__)

def settle_balances(student_id: int, join_code: str) -> None:
    """
    Atomic settlement of pending transactions into the balance cache.
    
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
    try:
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
                cache = BalanceCache(student_id=student_id, join_code=join_code)
                db.session.add(cache)
                db.session.flush() # Persist to get ID and lock
            except Exception as e:
                # If race condition leads to IntegrityError, retry fetch 
                # (though usually handled by application retries)
                logger.warning(f"Race condition creating BalanceCache, retrying fetch: {e}")
                db.session.rollback()
                cache = (
                    BalanceCache.query
                    .filter_by(student_id=student_id, join_code=join_code)
                    .with_for_update()
                    .first()
                )
                if not cache:
                    raise e # Re-raise if still failing

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
        
        if not pending_txs:
            # Nothing to settle
            return

        checking_delta_cents = 0
        savings_delta_cents = 0
        now = datetime.now(timezone.utc)
        
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
                logger.warning(f"Unknown account type '{tx.account_type}' for transaction {tx.id}")
                # Default to checking or ignore? Better to log and assume checking to avoid money loss?
                # For safety, we'll log strict warning but maybe track it in checking?
                # Let's assume checking to be safe, or just skip? 
                # Skiping loses money track. Defaulting to checking is safer for student.
                checking_delta_cents += tx.amount_cents

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
        raise e
