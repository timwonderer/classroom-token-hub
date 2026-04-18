from __future__ import annotations

from app.extensions import db
from app.models import RentPayment, StudentInsurance


def record_rent_payment(
    *,
    student_id: int,
    period: str,
    join_code: str,
    amount_paid,
    period_month: int,
    period_year: int,
    coverage_month: int,
    coverage_year: int,
    was_late: bool,
    late_fee_charged,
):
    """Obligations-owned mutation for rent payment truth."""
    payment = RentPayment(
        student_id=student_id,
        period=period,
        join_code=join_code,
        amount_paid=amount_paid,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        was_late=was_late,
        late_fee_charged=late_fee_charged,
    )
    db.session.add(payment)
    return payment


def record_insurance_enrollment(
    *,
    student_id: int,
    policy,
    join_code: str,
    purchase_date,
    next_payment_due,
    coverage_start_date,
):
    """Obligations-owned mutation for insurance enrollment truth."""
    enrollment = StudentInsurance(
        student_id=student_id,
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
