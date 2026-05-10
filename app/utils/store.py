"""
Shared utility functions for store collective goal management.

Provides refund and expiration processing for collective goal items,
called from both admin and student route handlers.
"""
from app.extensions import db
from app.models import StoreItem, StudentItem, Transaction
from app.services import ledger_service
from app.utils.time import utc_now


def refund_pending_collective_purchases(item, description_suffix="Goal Expired"):
    """
    Refund all 'pending' StudentItems for a collective goal item.

    For each pending purchase, creates a refund Transaction and marks the
    StudentItem as 'voided'. Does NOT commit — caller is responsible for
    committing (or the caller may batch multiple items before committing).

    Args:
        item: StoreItem instance with item_type='collective'.
        description_suffix: Reason appended to refund transaction description.

    Returns:
        int: Number of StudentItems refunded.
    """
    pending_items = StudentItem.query.filter(
        StudentItem.store_item_id == item.id,
        StudentItem.status == 'pending',
        StudentItem.collective_goal_instance_code == item.collective_goal_instance_code,
    ).all()

    refunded = 0
    for si in pending_items:
        # Prefer direct transaction linkage for stable matching.
        purchase_tx = None
        if si.purchase_transaction_id:
            purchase_tx = db.session.get(Transaction, si.purchase_transaction_id)
            if purchase_tx and (
                purchase_tx.seat_id != si.seat_id
                or purchase_tx.teacher_id != item.teacher_id
            ):
                purchase_tx = None

        # Legacy fallback for rows created before purchase_transaction_id existed.
        if purchase_tx is None and si.class_id:
            purchase_tx = (
                Transaction.query
                .filter_by(
                    seat_id=si.seat_id,
                    teacher_id=item.teacher_id,
                    type='purchase',
                    reversal_transaction_id=None,
                )
                .filter(
                    Transaction.class_id == si.class_id,
                    Transaction.description.like(f"Purchase: {item.name}%"),
                )
                .order_by(Transaction.timestamp.desc())
                .first()
            )

        # Use the original purchase amount for the refund; fall back to current price.
        if purchase_tx and purchase_tx.amount is not None:
            refund_amount = abs(purchase_tx.amount)
        else:
            refund_amount = item.price

        refund_tx = ledger_service.create_pending_transaction(
            seat_id=si.seat_id,
            class_id=si.class_id,
            teacher_id=item.teacher_id,
            amount=refund_amount,
            account_type='checking',
            type='refund',
            original_transaction_id=purchase_tx.id if purchase_tx else None,
            description=f"Refund: {item.name} ({description_suffix})",
        )
        db.session.add(refund_tx)
        if purchase_tx:
            # Assign ID before linking reverse pointer.
            db.session.flush()
            purchase_tx.reversal_transaction_id = refund_tx.id

        si.status = 'voided'
        si.redemption_details = description_suffix
        refunded += 1

    return refunded

from app.feats.base import feat_shell


@feat_shell("FEAT-STOR-003")
def process_expired_collective_goals(teacher_id, correlation_id=None, idempotency_key=None):
    """
    Find all expired collective goals for a teacher, refund pending purchases,
    and deactivate the items. Commits to the database if any items are processed.

    This is designed to be called lazily from route handlers (shop page, store
    management page) so that expiration is applied as soon as a user loads a
    relevant page, even without a background scheduler.

    Args:
        teacher_id: ID of the Admin (teacher) whose items should be checked.

    Returns:
        int: Number of collective goal items that were expired and processed.
    """
    now = utc_now()
    pending_exists = db.session.query(StudentItem.id).filter(
        StudentItem.store_item_id == StoreItem.id,
        StudentItem.status == 'pending',
        StudentItem.collective_goal_instance_code == StoreItem.collective_goal_instance_code,
    ).exists()

    expired_items = StoreItem.query.filter(
        StoreItem.teacher_id == teacher_id,
        StoreItem.item_type == 'collective',
        StoreItem.is_active == True,
        StoreItem.collective_goal_expires_at.isnot(None),
        StoreItem.collective_goal_expires_at <= now,
        pending_exists,
    ).all()

    if not expired_items:
        return 0

    for item in expired_items:
        refund_pending_collective_purchases(item, description_suffix="Collective Goal Expired")
        item.is_active = False

    db.session.flush()  # FEAT-LEGACY-WRAP: commit removed
    return len(expired_items)
