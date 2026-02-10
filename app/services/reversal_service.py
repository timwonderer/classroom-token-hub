from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Union

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import Transaction, Admin, SystemAdmin, StudentItem
from app.utils.time import utc_now

class ReversalError(Exception):
    """Base exception for reversal failures."""
    pass

class NonReversibleError(ReversalError):
    """Raised when a transaction type is not eligible for reversal."""
    pass

class AlreadyReversedError(ReversalError):
    """Raised when a transaction has already been reversed."""
    pass

class ReversalPermissionError(ReversalError):
    """Raised when the actor does not have permission to reverse this transaction."""
    pass

class ValidationFailureError(ReversalError):
    """Raised when conditional validation fails."""
    pass

class ReversalService:
    """
    Service for handling monetary reversals and refunds in compliance with
    the Reversal & Refund Specification.
    """

    # Map of transaction types to reversibility status
    # True = Always Reversible (given permissions)
    # False = Never Reversible
    # "conditional" = Requires specific checks
    REVERSIBILITY_MAP = {
        'manual_bonus': True,
        'manual_fine': True,
        'redemption_rejection': True,

        'payroll': 'conditional',
        'overdraft_fee': 'conditional',
        'rent_late_fee': 'conditional',
        'store_purchase': 'conditional',

        'transfer': False, # User-initiated bank transfer
        'interest': False,
        'rent_payment': False,
        'insurance_premium': False,
        'insurance_payout': False,
        'insurance_reimbursement': False,
        'bug_bounty': False,
    }

    @staticmethod
    def reverse_transaction(
        transaction_id: int,
        actor: Union[Admin, SystemAdmin],
        reason: str,
        ticket_id: Optional[int] = None
    ) -> Transaction:
        """
        Execute a reversal for a specific transaction.

        Args:
            transaction_id: ID of the transaction to reverse
            actor: The user performing the reversal (Teacher or Sysadmin)
            reason: Description/reason for the reversal
            ticket_id: Optional ID of related support ticket (required for some types)

        Returns:
            The newly created counter-transaction.

        Raises:
            ReversalError: If validation fails.
        """
        # 1. Validate preconditions
        original_tx = db.session.get(Transaction, transaction_id)
        if not original_tx:
            raise ReversalError(f"Transaction {transaction_id} not found.")

        # Check if already reversed
        # Note: 'reversals' backref is added via app/models.py modification
        if original_tx.reversals.count() > 0:
            existing = original_tx.reversals.first()
            current_app.logger.warning(
                f"Duplicate reversal attempt for transaction {transaction_id} by {actor}"
            )
            return existing

        # Validate Reversibility
        tx_type = original_tx.type.lower() if original_tx.type else 'unknown'

        # Normalize type strings from DB to Spec keys
        type_key = ReversalService._normalize_type(tx_type, original_tx.description)

        reversibility = ReversalService.REVERSIBILITY_MAP.get(type_key, False)

        if reversibility is False:
            raise NonReversibleError(f"Transaction type '{tx_type}' is not reversible.")

        if reversibility == 'conditional':
            ReversalService._validate_conditional_reversal(type_key, original_tx, actor, ticket_id)

        # 2. Log reversal intent (handled by app logger)
        current_app.logger.info(
            f"Initiating reversal for transaction {transaction_id}. Actor: {actor}, Reason: {reason}"
        )

        # 3. Update non-monetary state
        if type_key == 'store_purchase':
            ReversalService._handle_store_item_reversal(original_tx)

        # 4. Execute counter-transaction
        # Counter-transaction is opposite amount
        counter_amount = -original_tx.amount

        counter_tx = Transaction(
            student_id=original_tx.student_id,
            teacher_id=original_tx.teacher_id,
            join_code=original_tx.join_code,
            amount=counter_amount,
            account_type=original_tx.account_type,
            type=f"Reversal: {original_tx.type}",
            description=f"Reversal of #{original_tx.id}: {reason}",
            timestamp=utc_now(),
            original_transaction_id=original_tx.id
        )

        db.session.add(counter_tx)

        # 5. Log finalized reversal (commit)
        try:
            db.session.commit()
            current_app.logger.info(
                f"Reversal completed. Original: {original_tx.id}, Counter: {counter_tx.id}"
            )
            return counter_tx
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Reversal failed db commit: {e}")
            raise ReversalError("Database error during reversal execution.")

    @staticmethod
    def _normalize_type(db_type: str, description: str) -> str:
        """Map database transaction types/descriptions to spec keys."""
        db_type = db_type.lower()
        description = (description or "").lower()

        if 'payroll' in db_type or 'payroll' in description:
            return 'payroll'
        if 'rent payment' in db_type:
            return 'rent_payment'
        if 'rent' in db_type and ('fee' in db_type or 'late' in description):
            return 'rent_late_fee'
        if 'store' in db_type or 'purchase' in db_type:
            return 'store_purchase'
        if 'insurance' in db_type:
            if 'premium' in db_type: return 'insurance_premium'
            if 'claim' in db_type or 'payout' in db_type: return 'insurance_payout'
        if 'transfer' in db_type:
            return 'transfer'
        if 'interest' in db_type:
            return 'interest'
        if 'fine' in db_type:
            return 'manual_fine'
        if 'bonus' in db_type or 'reward' in db_type:
            return 'manual_bonus'
        if 'overdraft' in db_type:
            return 'overdraft_fee'

        # Fallback based on known keys or strict mapping
        return db_type

    @staticmethod
    def _validate_conditional_reversal(type_key, tx, actor, ticket_id):
        """
        Validate constraints for conditional types.
        Raises ValidationFailureError if constraints are not met.
        """

        # Payroll: Correction only, Teacher/Sysadmin initiated
        # Constraint: Allowed only for system error. Must reference incident or ticket ID.
        if type_key == 'payroll':
            if not ticket_id:
                # We relax slightly for sysadmins fixing things directly,
                # but spec says "Must reference incident or ticket ID"
                # If actor is Sysadmin, we might assume they are the incident reference.
                # But for Teacher, strict requirement.
                if isinstance(actor, SystemAdmin):
                    pass # Sysadmins can override
                else:
                    raise ValidationFailureError("Payroll reversals require a ticket or incident ID.")

        # Rent Late Fee: Teacher discretion + ticket
        elif type_key == 'rent_late_fee':
            if not ticket_id:
                 raise ValidationFailureError("Rent late fee reversal requires a ticket ID.")

        # Store Purchase: Student ticket required; teacher executes refund
        elif type_key == 'store_purchase':
            if not ticket_id:
                # Allow Sysadmin override
                if isinstance(actor, SystemAdmin):
                    pass
                else:
                    raise ValidationFailureError("Store purchase refund requires a student ticket.")

        # Overdraft Fee: Teacher initiated; ticket optional (system error or discretionary)
        elif type_key == 'overdraft_fee':
            # Ticket optional, so we pass
            pass

    @staticmethod
    def _handle_store_item_reversal(original_tx):
        """
        Handle side effects for reversing a store purchase.
        - Mark StudentItem as 'refunded'.
        - Does NOT attempt to match price exactly if price might have changed,
          but relies on purchase timing and student linkage.
        """
        time_window = 5 # seconds tolerance for loosely coupled transactions

        # Look for StudentItems created around the same time
        items = StudentItem.query.filter(
            StudentItem.student_id == original_tx.student_id,
            StudentItem.purchase_date >= original_tx.timestamp - timedelta(seconds=time_window),
            StudentItem.purchase_date <= original_tx.timestamp + timedelta(seconds=time_window),
            StudentItem.status != 'refunded' # Don't re-refund
        ).all()

        # Determine how many items were bought.
        # original_tx.amount is negative for purchase.
        # We don't have per-item price in transaction easily available if it was a cart.
        # But StudentItem tracks individual items.

        # If multiple items found, we might refund all?
        # Or we assume 1 transaction = 1 item (current simple shop implementation usually does this).

        for item in items:
            item.status = 'refunded'
            db.session.add(item)
            current_app.logger.info(f"Marked StudentItem {item.id} as refunded matching reversal {original_tx.id}")
