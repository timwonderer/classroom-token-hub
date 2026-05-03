from __future__ import annotations

from app.extensions import db
from app.models import InsuranceClaim, RentPayment, StudentInsurance


def record_rent_payment(
    *,
    seat_id: int,
    class_id: str,
    period: str,
    amount_paid,
    period_month: int,
    period_year: int,
    coverage_month: int,
    coverage_year: int,
    was_late: bool,
    late_fee_charged,
    coverage_start_time=None,
    coverage_end_time=None,
    cycle_idempotency_key: str | None = None,
    join_code: str | None = None,
):
    """Obligations-owned mutation for rent payment truth."""
    payment = RentPayment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        join_code=join_code,
        amount_paid=amount_paid,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        was_late=was_late,
        late_fee_charged=late_fee_charged,
    )
    db.session.add(payment)
    return payment


def record_insurance_enrollment(
    *,
    seat_id: int,
    class_id: str,
    policy,
    purchase_date,
    next_payment_due,
    coverage_start_date,
    join_code: str | None = None,
):
    """Obligations-owned mutation for insurance enrollment truth."""
    enrollment = StudentInsurance(
        seat_id=seat_id,
        class_id=class_id,
        policy_id=policy.id,
        join_code=join_code,
        status='active',
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=next_payment_due,
        coverage_start_date=coverage_start_date,
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)
    return enrollment


def apply_claim_resolution(
    claim: InsuranceClaim,
    *,
    status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_teacher_id: int | None,
    processed_at,
    approved_amount=None,
):
    """Obligations-owned mutation for insurance-claim resolution state."""
    claim.status = status
    claim.teacher_notes = teacher_notes
    claim.rejection_reason = rejection_reason if status == 'rejected' else None
    claim.processed_date = processed_at
    claim.processed_by_teacher_id = processed_by_teacher_id
    claim.approved_amount = approved_amount
    return claim


def record_insurance_claim(
    *,
    student_insurance_id: int,
    policy_id: int,
    seat_id: int,
    class_id: str,
    incident_date,
    description: str,
    claim_amount,
    claim_item: str | None,
    comments: str | None,
    transaction_id: int | None,
    join_code: str | None = None,
):
    """Obligations-owned mutation for filed insurance claims."""
    claim = InsuranceClaim(
        student_insurance_id=student_insurance_id,
        policy_id=policy_id,
        seat_id=seat_id,
        class_id=class_id,
        join_code=join_code,
        incident_date=incident_date,
        description=description,
        claim_amount=claim_amount,
        claim_item=claim_item,
        comments=comments,
        status='pending',
        transaction_id=transaction_id,
    )
    db.session.add(claim)
    return claim
