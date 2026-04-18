from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import _quantize_currency
from app.services import identity_service, ledger_service, obligations_service, store_service
from app.utils.time import utc_now


@dataclass
class RentPaymentResult:
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
    calculate_due_dates_fn=None,
) -> RentPaymentResult:
    """Obligations-led FEAT for rent payment orchestration."""
    now = now or utc_now()
    teacher_id = context.get("teacher_id")
    join_code = context.get("join_code")
    current_block = (context.get("block") or period or "").strip().upper()
    is_partial = payment_amount < remaining_amount

    billed_period_date = payment_due_date or now
    payment_description = f'Rent for Period {period} - {billed_period_date.strftime("%B %Y")}'
    if is_partial and settings.allow_incremental_payment:
        payment_description += f' (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})'
    elif late_fee > Decimal('0'):
        payment_description += f' (includes ${late_fee:.2f} late fee)'

    transaction = ledger_service.create_pending_transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=-payment_amount,
        account_type='checking',
        type='Rent Payment',
        description=payment_description,
    )

    late_fee_for_this_payment = Decimal('0.00')
    if is_late and late_fee > Decimal('0.00'):
        late_fee_for_this_payment = (
            _quantize_currency((payment_amount / total_due) * late_fee)
            if is_partial
            else _quantize_currency(late_fee)
        )

    payment = obligations_service.record_rent_payment(
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
    db.session.flush()

    if banking_settings and banking_settings.overdraft_protection_enabled and overdraft_shortfall > 0:
        ledger_service.create_transfer_pair(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=overdraft_shortfall,
            from_account='savings',
            to_account='checking',
            withdraw_description='Overdraft protection transfer to checking',
            deposit_description='Overdraft protection transfer from savings',
        )
        db.session.flush()

    ledger_service.apply_overdraft_fee_if_needed(
        student,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code,
        commit=False,
    )

    passes_awarded = 0
    per_use_items_granted = 0
    newly_fully_paid = total_paid_so_far < total_due and (total_paid_so_far + payment_amount >= total_due)
    if newly_fully_paid:
        target_rent_passes = store_service.get_rent_hall_pass_grant_total(settings.id)
        passes_awarded, _, _ = identity_service.reconcile_rent_hall_pass_top_off(
            student=student,
            join_code=join_code,
            current_block=current_block,
            target_rent_passes=target_rent_passes,
        )
        if calculate_due_dates_fn is not None:
            per_use_items_granted = store_service.grant_rent_per_use_items(
                student=student,
                join_code=join_code,
                settings=settings,
                calculate_due_dates_fn=calculate_due_dates_fn,
            )

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
