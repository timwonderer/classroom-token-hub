from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import (
    EntitlementEvent,
    InsuranceClaim,
    InsuranceEnrollment,
    ObligationAssessment,
    ObligationLifecycle,
    ObligationReversal,
    ObligationSatisfaction,
)
from app.utils.time import utc_now


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claim_assessment_key(claim_id: int) -> str:
    return f"insurance-claim:{claim_id}"


def _get_claim_assessment(assessment_key: str, seat_id: int, class_id: str) -> ObligationAssessment | None:
    return (
        ObligationAssessment.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            cycle_idempotency_key=assessment_key,
        )
        .order_by(ObligationAssessment.id.desc())
        .first()
    )


def _create_claim_assessment(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    claim_amount,
    incident_date,
    assessed_at,
) -> ObligationAssessment:
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_CLAIM",
        amount_snap=claim_amount,
        due_at=incident_date,
        assessed_at=assessed_at,
        cycle_idempotency_key=_claim_assessment_key(claim_id),
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=assessed_at,
        )
    )
    return assessment


def _require_claim_assessment(claim_id: int, seat_id: int, class_id: str) -> ObligationAssessment:
    key = _claim_assessment_key(claim_id)
    assessment = _get_claim_assessment(key, seat_id, class_id)
    if assessment is None:
        raise ValueError(f"Missing canonical claim assessment for insurance claim {claim_id}")
    return assessment


def _set_assessment_lifecycle(assessment: ObligationAssessment, *, status: str, updated_at):
    lifecycle = assessment.lifecycle
    if lifecycle is None:
        lifecycle = ObligationLifecycle(
            assessment_id=assessment.id,
            status=status,
            updated_at=updated_at,
        )
        db.session.add(lifecycle)
        return lifecycle
    lifecycle.status = status
    lifecycle.updated_at = updated_at
    return lifecycle


# ---------------------------------------------------------------------------
# Rent mutations
# ---------------------------------------------------------------------------

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
) -> ObligationAssessment:
    """Record a rent payment as a canonical assessment + satisfaction."""
    now = utc_now()
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

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="PAID",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=amount_paid,
            was_late=was_late,
            late_fee_charged=late_fee_charged,
            transaction_id=transaction_id,
            satisfied_at=now,
        )
    )
    return assessment


def record_rent_waiver(
    *,
    seat_id: int,
    class_id: str,
    waiver_start_date,
    waiver_end_date,
    periods_count: int,
    reason: str | None = None,
    created_by_user_id: int | None = None,
) -> ObligationAssessment:
    """Record a rent waiver as a canonical assessment + reversal."""
    now = utc_now()

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="RENT_WAIVER",
        amount_snap=Decimal("0.00"),
        due_at=waiver_start_date,
        assessed_at=now,
        coverage_start_time=waiver_start_date,
        coverage_end_time=waiver_end_date,
        cycle_idempotency_key=f"rent-waiver:{seat_id}:{class_id}:{waiver_start_date.isoformat()}",
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="REVERSED",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationReversal(
            assessment_id=assessment.id,
            reason=reason,
            reversed_at=now,
            reversed_by_user_id=created_by_user_id,
        )
    )
    return assessment


# ---------------------------------------------------------------------------
# Insurance mutations
# ---------------------------------------------------------------------------

def record_insurance_enrollment(
    *,
    seat_id: int,
    class_id: str,
    policy,
    purchase_date,
    next_payment_due,
    coverage_start_date,
) -> InsuranceEnrollment:
    """Record an insurance enrollment in canonical tables only."""
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
    return enrollment


def record_insurance_claim(
    *,
    enrollment_id: int,
    policy_id: int,
    seat_id: int,
    class_id: str,
    incident_date,
    description: str,
    claim_amount,
    claim_item: str | None,
    comments: str | None,
    transaction_id: int | None,
) -> InsuranceClaim:
    """Record an insurance claim.

    InsuranceClaim is retained as the claim metadata store until its columns
    are migrated onto assessment_events. The canonical assessment/lifecycle
    rows are created alongside it.
    """
    claim = InsuranceClaim(
        enrollment_id=enrollment_id,
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
    db.session.flush()

    _create_claim_assessment(
        seat_id=seat_id,
        class_id=class_id,
        claim_id=claim.id,
        claim_amount=claim_amount,
        incident_date=incident_date,
        assessed_at=utc_now(),
    )
    return claim


def apply_claim_resolution(
    claim: InsuranceClaim,
    *,
    status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_user_id: int | None,
    processed_at,
    approved_amount=None,
):
    """Advance claim state and its canonical lifecycle."""
    claim.status = status
    claim.teacher_notes = teacher_notes
    claim.rejection_reason = rejection_reason if status == 'rejected' else None
    claim.processed_date = processed_at
    claim.processed_by_user_id = processed_by_user_id
    claim.approved_amount = approved_amount

    assessment = _require_claim_assessment(claim.id, claim.seat_id, claim.class_id)

    if status in {"approved", "paid"}:
        _set_assessment_lifecycle(assessment, status="PAID", updated_at=processed_at)
        if assessment.satisfaction is None:
            db.session.add(
                ObligationSatisfaction(
                    assessment_id=assessment.id,
                    method="PAYMENT",
                    amount_paid=approved_amount,
                    satisfied_at=processed_at,
                )
            )
        else:
            assessment.satisfaction.amount_paid = approved_amount
            assessment.satisfaction.satisfied_at = processed_at
    elif status == "rejected":
        _set_assessment_lifecycle(assessment, status="REVERSED", updated_at=processed_at)
        if assessment.reversal is None:
            db.session.add(
                ObligationReversal(
                    assessment_id=assessment.id,
                    reason=rejection_reason or teacher_notes,
                    reversed_at=processed_at,
                    reversed_by_user_id=processed_by_user_id,
                )
            )
        else:
            assessment.reversal.reason = rejection_reason or teacher_notes
            assessment.reversal.reversed_at = processed_at
            assessment.reversal.reversed_by_user_id = processed_by_user_id
    return claim


# ---------------------------------------------------------------------------
# Canonical read helpers
# ---------------------------------------------------------------------------

def has_rent_coverage(
    seat_id: int,
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> bool:
    """Check whether a seat has a PAID rent assessment for the given cycle."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .first()
    ) is not None


def get_rent_payments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> list[ObligationAssessment]:
    """Return all PAID rent assessments for a class + cycle."""
    return (
        ObligationAssessment.query
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .order_by(ObligationAssessment.assessed_at.asc())
        .all()
    )


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    *,
    limit: int | None = None,
) -> list[ObligationAssessment]:
    """Return rent assessments for a seat, newest first."""
    q = (
        ObligationAssessment.query
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
        )
        .order_by(ObligationAssessment.assessed_at.desc())
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def has_active_rent_waiver(
    seat_id: int,
    class_id: str,
    coverage_date,
) -> bool:
    """Check whether a seat has a canonical rent waiver covering the given date."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .first()
    ) is not None


def get_claim_status(claim_id: int) -> str | None:
    """Return the canonical lifecycle status for an insurance claim."""
    assessment = (
        ObligationAssessment.query
        .filter_by(
            obligation_type="INSURANCE_CLAIM",
            cycle_idempotency_key=_claim_assessment_key(claim_id),
        )
        .first()
    )
    if assessment is None:
        return None
    return assessment.lifecycle.status if assessment.lifecycle else None


# ---------------------------------------------------------------------------
# Entitlement mutations
# ---------------------------------------------------------------------------

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
