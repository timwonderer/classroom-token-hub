"""
app/feats/store_purchase_feat.py – Store Purchase FEAT.

This is the authoritative write path for standard (non-rent-perk) store
item purchases.

Route → execute_store_purchase() → services (ledger_service, …)

Rules:
• All Transaction creation goes through ledger_service.
• db.session.commit() is called exactly once, at the end.
• Validation (affordability, quantity limits, etc.) is done by the route
  before calling this FEAT.
• The route passes in the pre-validated context and item data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.extensions import db
from app.models import StudentItem, _quantize_currency
from app.services import ledger_service
from app.utils.overdraft import charge_overdraft_fee_if_needed
from app.utils.time import utc_now


@dataclass
class StorePurchaseResult:
    """Returned by execute_store_purchase so the route can build a response."""
    transaction_id: int
    student_item_ids: list[int] = field(default_factory=list)
    success_message: str = ""


def execute_store_purchase(
    *,
    student,
    teacher_id: int,
    join_code: str,
    item,
    quantity: int,
    total_price: Decimal,
    purchase_description: str,
    banking_settings=None,
    expiry_date=None,
    uses_remaining=None,
    bundle_remaining=None,
    student_item_status: str = "purchased",
    collective_goal_instance_code: Optional[str] = None,
    purchase_transaction_id_hint: Optional[int] = None,
) -> StorePurchaseResult:
    """
    Execute the write path for a standard store item purchase.

    Callers must have:
      1. Validated affordability via ledger_service.get_available_balances.
      2. Validated quantity limits.
      3. NOT yet written any Transaction or StudentItem rows.

    This function owns the single db.session.commit().
    """
    # 1. Create the ledger debit via the canonical write path.
    purchase_tx = ledger_service.create_pending_transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=-total_price,
        account_type="checking",
        type="purchase",
        description=purchase_description,
    )
    db.session.flush()  # Ensure purchase_tx.id is available for StudentItem FK.

    # 2. Update inventory.
    if item.inventory is not None:
        item.inventory -= quantity

    # 3. Halt pass quantity update (hall_pass items only).
    if item.item_type == "hall_pass":
        student.hall_passes += quantity
        db.session.flush()

    # 4. Create StudentItem record(s).
    created_item_ids: list[int] = []
    if item.is_bundle and item.bundle_quantity is not None:
        si = StudentItem(
            student_id=student.id,
            store_item_id=item.id,
            join_code=join_code,
            purchase_date=utc_now(),
            expiry_date=expiry_date,
            status=student_item_status,
            purchase_transaction_id=purchase_tx.id,
            is_from_bundle=True,
            bundle_remaining=item.bundle_quantity * quantity,
            quantity_purchased=quantity,
            uses_remaining=uses_remaining,
            collective_goal_instance_code=collective_goal_instance_code,
        )
        db.session.add(si)
        db.session.flush()
        created_item_ids.append(si.id)
    else:
        for _ in range(quantity):
            si = StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                join_code=join_code,
                purchase_date=utc_now(),
                expiry_date=expiry_date,
                status=student_item_status,
                purchase_transaction_id=purchase_tx.id,
                is_from_bundle=False,
                quantity_purchased=1,
                uses_remaining=uses_remaining,
                collective_goal_instance_code=collective_goal_instance_code,
            )
            db.session.add(si)
            db.session.flush()
            created_item_ids.append(si.id)

    # 5. Overdraft protection transfer if checking went negative.
    from app.services.ledger_service import get_available_balances
    checking_balance, savings_balance = get_available_balances(student.id, join_code)
    if banking_settings and banking_settings.overdraft_protection_enabled and checking_balance < 0:
        shortfall = abs(checking_balance)
        if savings_balance >= shortfall:
            ledger_service.create_transfer_pair(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,
                amount=shortfall,
                from_account="savings",
                to_account="checking",
                withdraw_description="Overdraft protection transfer to checking",
                deposit_description="Overdraft protection transfer from savings",
            )
            db.session.flush()

    # 6. Overdraft fee if balance is still negative.
    charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=teacher_id, join_code=join_code)

    # 7. Collective-goal threshold check.
    if item.item_type == "collective":
        _process_collective_goal_threshold(item, join_code, teacher_id)

    # 8. Single commit.
    db.session.commit()

    return StorePurchaseResult(
        transaction_id=purchase_tx.id,
        student_item_ids=created_item_ids,
    )


def _process_collective_goal_threshold(item, join_code: str, teacher_id: int) -> None:
    """Unlock pending collective-goal items if the class threshold is met."""
    from app.models import TeacherBlock, Student as _Student

    class_size = (
        db.session.query(db.func.count(db.func.distinct(_Student.id)))
        .join(TeacherBlock, TeacherBlock.student_id == _Student.id)
        .filter(
            TeacherBlock.teacher_id == teacher_id,
            TeacherBlock.join_code == join_code,
            TeacherBlock.is_claimed == True,
        )
        .scalar()
        or 0
    )

    purchased_students_count = (
        db.session.query(db.func.count(db.func.distinct(StudentItem.student_id)))
        .filter(
            StudentItem.store_item_id == item.id,
            StudentItem.join_code == join_code,
            StudentItem.status.in_(["pending", "processing", "purchased", "redeemed", "completed"]),
            StudentItem.collective_goal_instance_code == item.collective_goal_instance_code,
        )
        .scalar()
        or 0
    )

    if item.collective_goal_type == "fixed":
        target = int(item.collective_goal_target or 0)
    else:
        target = class_size

    if target > 0 and purchased_students_count >= target:
        StudentItem.query.filter(
            StudentItem.store_item_id == item.id,
            StudentItem.join_code == join_code,
            StudentItem.status == "pending",
            StudentItem.collective_goal_instance_code == item.collective_goal_instance_code,
        ).update({"status": "processing"})
