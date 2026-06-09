from __future__ import annotations

from app.extensions import db
from app.models import (
    EntitlementEvent,
    InsuranceClaim,
    InsuranceEnrollment,
    ObligationAssessment,
    ObligationLifecycle,
    ObligationSatisfaction,
    RentPayment,
    StudentInsurance,
)
from app.utils.time import utc_now


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
    transaction_id: int | None = None,
):
    """Obligations-owned mutation for rent payment truth.

    Dual-writes to both the legacy rent_payments table (backward-compatible reads)
    and the canonical assessment_events + obligation_satisfaction tables.
    The canonical tables are the authoritative write target; legacy tables will be
    dropped in Wave 7-B once all reads are migrated.
    """
    now = utc_now()

    # --- Canonical write ---
    period_key = f"{coverage_year}-{coverage_month:02d}" if coverage_year is not None and coverage_month is not None else None
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        obligation_type="RENT",
        amount_snap=amount_paid,
        assessed_at=now,
        period_key=period_key,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
    )
    db.session.add(assessment)
    db.session.flush()

    lifecycle = ObligationLifecycle(
        assessment_id=assessment.id,
        status="PAID",
        updated_at=now,
    )
    db.session.add(lifecycle)

    satisfaction = ObligationSatisfaction(
        assessment_id=assessment.id,
        method="PAYMENT",
        amount_paid=amount_paid,
        was_late=was_late,
        late_fee_charged=late_fee_charged,
        transaction_id=transaction_id,
        satisfied_at=now,
    )
    db.session.add(satisfaction)

    # --- Legacy write (kept for backward-compatible reads) ---
    payment = RentPayment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
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
):
    """Obligations-owned mutation for insurance enrollment truth.

    Dual-writes to both the legacy student_insurance table and the canonical
    insurance_enrollments table while also recording the enrollment in the
    canonical assessment/lifecycle hierarchy. Returns the legacy
    StudentInsurance row for backward-compatible callers.
    """
    # --- Canonical write ---
    enrollment = InsuranceEnrollment(
        seat_id=seat_id,
        class_id=class_id,
        policy_id=policy.id,
        status='active',
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=next_payment_due,
        coverage_start_date=coverage_start_date,
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_ENROLLMENT",
        amount_snap=0,
        due_at=next_payment_due,
        assessed_at=purchase_date,
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=purchase_date,
        )
    )

    # --- Legacy write (kept for backward-compatible reads) ---
    legacy_enrollment = StudentInsurance(
        seat_id=seat_id,
        class_id=class_id,
        policy_id=policy.id,
        status='active',
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=next_payment_due,
        coverage_start_date=coverage_start_date,
        payment_current=True,
    )
    legacy_enrollment.freeze_policy_snapshot(policy)
    db.session.add(legacy_enrollment)
    return legacy_enrollment


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
):
    """Obligations-owned mutation for filed insurance claims."""
    claim = InsuranceClaim(
        student_insurance_id=student_insurance_id,
        policy_id=policy_id,
        seat_id=seat_id,
        class_id=class_id,
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


def record_entitlement_grant(
    *,
    seat_id: int,
    class_id: str,
    quantity: int,
    trigger_id: str | None = None,
    assessment_id: int | None = None,
) -> EntitlementEvent:
    """Record a GRANT entitlement event for obligation-linked perks (e.g., hall passes from rent)."""
    event = EntitlementEvent(
        seat_id=seat_id,
        class_id=class_id,
        assessment_id=assessment_id,
        trigger_id=trigger_id,
        quantity_delta=quantity,
        event_type="GRANT",
        occurred_at=utc_now(),
    )
    db.session.add(event)
    return event
