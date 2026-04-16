"""
app/feats/rent_payment_feat.py – Rent Payment FEAT.

This is the single authoritative write path for student rent payments.

Route → execute_rent_payment() → services (ledger_service, …)

Rules:
• All Transaction creation goes through ledger_service.
• db.session.commit() is called exactly once, at the end of execute_rent_payment().
• The FEAT accepts pre-validated domain inputs from the route.
• The route becomes a thin adapter: validate → call FEAT → flash → redirect.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import RentPayment, StudentItem, _quantize_currency
from app.services import ledger_service
from app.utils.overdraft import charge_overdraft_fee_if_needed
from app.utils.time import utc_now


@dataclass
class RentPaymentResult:
    """Returned by execute_rent_payment so the route can build a response."""
    transaction_id: int
    payment_id: int
    passes_awarded: int
    per_use_items_granted: int
    is_partial: bool
    amount_paid: Decimal
    new_remaining: Decimal


def execute_rent_payment(
    *,
    student,
    context: dict,
    payment_amount: Decimal,
    period: str,
    settings,
    is_late: bool,
    late_fee: Decimal,
    total_paid_so_far: Decimal,
    total_due: Decimal,
    remaining_amount: Decimal,
    coverage_month: int,
    coverage_year: int,
    current_month: int,
    current_year: int,
    payment_due_date,
    banking_settings=None,
    overdraft_shortfall: Decimal = Decimal("0.00"),
    now=None,
) -> RentPaymentResult:
    """
    Execute the full rent payment write path.

    Callers (the rent_pay route) must have:
      1. Validated the student, period, and payment amount.
      2. Run the overdraft allowance check and set overdraft_shortfall.
      3. NOT yet written any Transaction or RentPayment rows.

    This function owns the single db.session.commit().
    """
    now = now or utc_now()
    teacher_id = context.get("teacher_id")
    join_code = context.get("join_code")

    is_partial = payment_amount < remaining_amount
    billed_period_date = payment_due_date or now
    payment_description = f"Rent for Period {period} - {billed_period_date.strftime('%B %Y')}"
    if is_partial and settings.allow_incremental_payment:
        payment_description += f" (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})"
    elif late_fee > Decimal("0"):
        payment_description += f" (includes ${late_fee:.2f} late fee)"

    # 1. Create the ledger debit via the canonical write path.
    transaction = ledger_service.create_pending_transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=-payment_amount,
        account_type="checking",
        type="Rent Payment",
        description=payment_description,
    )

    # 2. Calculate late-fee portion for the obligation record.
    late_fee_for_this_payment = Decimal("0.00")
    if is_late and late_fee > Decimal("0.00"):
        if is_partial:
            late_fee_for_this_payment = _quantize_currency((payment_amount / total_due) * late_fee)
        else:
            late_fee_for_this_payment = _quantize_currency(late_fee)

    # 3. Record the rent obligation row.
    payment = RentPayment(
        student_id=student.id,
        period=period,
        join_code=join_code,
        amount_paid=payment_amount,
        period_month=current_month,
        period_year=current_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        was_late=is_late,
        late_fee_charged=late_fee_for_this_payment,
    )
    db.session.add(payment)
    db.session.flush()

    # 4. Overdraft protection transfer (savings → checking) if needed.
    if banking_settings and banking_settings.overdraft_protection_enabled and overdraft_shortfall > 0:
        ledger_service.create_transfer_pair(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=overdraft_shortfall,
            from_account="savings",
            to_account="checking",
            withdraw_description="Overdraft protection transfer to checking",
            deposit_description="Overdraft protection transfer from savings",
        )
        db.session.flush()

    # 5. Overdraft fee (if the account is still negative after protection).
    charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=teacher_id, join_code=join_code)

    # 6. Hall-pass top-off when this payment completes the rent obligation.
    passes_awarded = 0
    newly_fully_paid = total_paid_so_far < total_due and (total_paid_so_far + payment_amount >= total_due)
    if newly_fully_paid:
        from app.routes.student import _ensure_rent_hall_pass_top_off
        passes_awarded, _, _ = _ensure_rent_hall_pass_top_off(student, context, settings=settings, now=now)

    # 7. Per-use rent-item grants when payment completes the obligation.
    per_use_items_granted = 0
    if newly_fully_paid:
        per_use_items_granted = _grant_per_use_rent_items(student, join_code, settings)

    # 8. Single commit for everything above.
    db.session.commit()

    return RentPaymentResult(
        transaction_id=transaction.id,
        payment_id=payment.id,
        passes_awarded=passes_awarded,
        per_use_items_granted=per_use_items_granted,
        is_partial=is_partial,
        amount_paid=payment_amount,
        new_remaining=_quantize_currency(total_due - (total_paid_so_far + payment_amount)),
    )


def _grant_per_use_rent_items(student, join_code: str, settings) -> int:
    """
    Grant or top-off per-use StudentItems when rent becomes fully paid.
    Returns the number of new StudentItem rows created.
    """
    from app.models import RentItem
    from app.routes.api import _calculate_due_dates

    per_use_items = RentItem.query.filter_by(
        rent_setting_id=settings.id,
        rent_item_type="per_use",
    ).all()

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        if not pu_item.store_item_id:
            continue

        existing = StudentItem.query.filter(
            StudentItem.student_id == student.id,
            StudentItem.store_item_id == pu_item.store_item_id,
            db.or_(
                StudentItem.uses_remaining > 0,
                StudentItem.uses_remaining == -1,
            ),
            StudentItem.join_code == join_code,
            db.or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > now,
            ),
        ).first()

        if existing:
            # Top-off: reset uses_remaining to the granted amount.
            existing.uses_remaining = pu_item.use_limit if pu_item.use_limit else -1
            continue

        # Calculate expiry from the next rent due date.
        expiry_date = None
        if settings.first_rent_due_date:
            _, next_due = _calculate_due_dates(settings, now)
            if next_due:
                expiry_date = next_due

        db.session.add(StudentItem(
            student_id=student.id,
            store_item_id=pu_item.store_item_id,
            join_code=join_code,
            purchase_date=now,
            expiry_date=expiry_date,
            status="purchased",
            is_from_bundle=False,
            quantity_purchased=1,
            uses_remaining=pu_item.use_limit if pu_item.use_limit else -1,
        ))
        granted += 1

    return granted
