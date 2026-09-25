"""The canonical obligation state — DOM-OBL-001 §VIII.

``obligations_service.get_obligation_state`` is the one derivation of paid /
outstanding / waived for an obligation; consumers read it instead of recomputing
from assessment events and Ledger rows (INV-ARC-009 §V). These tests hold that
derivation and the two defects that centralizing it removed:

- an insurance premium resolved to an amount of 0, so an unpaid premium read as
  SATISFIED;
- the per-seat rent assessment view summed the signed Ledger amount of a payment
  (rent posts as a negative debit), so paid rent read as outstanding and appeared
  on the teacher's waive list with a remainder larger than the bill.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_waiver
from app.models import ObligationAssessment
from app.services import insurance_definition_service
from app.services import obligations_service
from app.services.obligation_view_model import (
    get_outstanding_rent_by_seat,
    get_rent_assessments_for_seat_class,
)
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction


_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_INITIAL = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
# Class timezone is America/Los_Angeles: the Jan 1 due boundary is 08:00 UTC.
_BEFORE_DUE = datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)
_AFTER_DUE = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def _rent_class(classroom, *, allow_incremental=False):
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    customize_rent_settings(
        classroom.class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE,
        grace_period_days=3,
        rent_amount=Decimal("50.00"),
        late_penalty_amount=Decimal("0.00"),
        allow_incremental_payment=allow_incremental,
    )
    execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)


def _fund(classroom, student, amount=Decimal("100.00")):
    seat_id = student.seat.id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund-seat:{seat_id}",
            seat_id=seat_id,
            class_id=classroom.class_id,
            amount=amount,
            account_type="checking",
            type="payroll",
            description="Test funding",
        )


def _rent_correlation(classroom, student):
    return (
        ObligationAssessment.query.filter_by(
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            obligation_type="RENT",
            event_type="ASSESSMENT",
        )
        .one()
        .correlation_id
    )


def _pay(classroom, student, correlation_id, amount=None):
    result = execute_rent_payment(
        classroom.class_id,
        student.seat.id,
        correlation_id,
        idempotency_key=f"pay:{uuid4().hex}",
        payment_amount=amount,
    )
    assert result.success, result.error_message
    return result


def test_unpaid_rent_is_outstanding_for_its_full_amount(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom)
        state = obligations_service.get_obligation_state(_rent_correlation(classroom, student))

        assert state.is_outstanding and state.is_payable and not state.is_satisfied
        assert state.assessed_amount == Decimal("50.00")
        assert state.satisfied_amount == Decimal("0.00")
        assert state.remaining_amount == Decimal("50.00")
        assert state.due_at is not None


def test_partial_payment_leaves_the_remainder_outstanding(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom, allow_incremental=True)
        _fund(classroom, student)
        correlation_id = _rent_correlation(classroom, student)
        _pay(classroom, student, correlation_id, Decimal("20.00"))

        state = obligations_service.get_obligation_state(correlation_id)
        assert state.is_outstanding
        assert state.satisfied_amount == Decimal("20.00")
        assert state.remaining_amount == Decimal("30.00")


def test_full_payment_satisfies_and_zeroes_the_remainder(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom)
        _fund(classroom, student)
        correlation_id = _rent_correlation(classroom, student)
        _pay(classroom, student, correlation_id)

        state = obligations_service.get_obligation_state(correlation_id)
        assert state.is_satisfied and not state.is_payable
        assert state.satisfied_amount == Decimal("50.00")
        assert state.remaining_amount == Decimal("0.00")


def test_waiver_satisfies_without_payment(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom)
        correlation_id = _rent_correlation(classroom, student)
        execute_satisfy_obligation_waiver(
            correlation_id=correlation_id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            idempotency_key=f"waive:{correlation_id}",
        )
        db.session.commit()

        state = obligations_service.get_obligation_state(correlation_id)
        assert state.is_satisfied and state.is_waived
        assert state.satisfied_amount == Decimal("0.00")
        assert state.remaining_amount == Decimal("0.00")


def test_as_of_counts_only_facts_recorded_by_then(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom)
        _fund(classroom, student)
        correlation_id = _rent_correlation(classroom, student)
        _pay(classroom, student, correlation_id)
        payment = obligations_service.get_satisfaction_events(correlation_id)[0]

        before = obligations_service.get_obligation_state(
            correlation_id, as_of=_T_INITIAL.replace(year=2025)
        )
        at = obligations_service.get_obligation_state(correlation_id, as_of=payment.timestamp)
        assert before.is_outstanding
        assert at.is_satisfied


def test_past_due_is_evaluated_against_the_reference_time(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _rent_class(classroom)
        state = obligations_service.get_obligation_state(_rent_correlation(classroom, student))

        assert not obligations_service.is_obligation_past_due(state, reference_time_utc=_BEFORE_DUE)
        assert obligations_service.is_obligation_past_due(state, reference_time_utc=_AFTER_DUE)


def test_paid_rent_is_not_outstanding_in_the_per_seat_view_or_the_waive_list(app):
    """Regression: the per-seat view summed the signed (negative) payment amount."""
    classroom = initialize("chemistry_p1", app)
    paid, unpaid = classroom.students[0], classroom.students[1]
    with app.app_context():
        _rent_class(classroom)
        _fund(classroom, paid)
        _pay(classroom, paid, _rent_correlation(classroom, paid))

        [view] = get_rent_assessments_for_seat_class(paid.seat.id, classroom.class_id)
        assert view.is_satisfied and not view.is_outstanding
        assert view.total_paid == Decimal("50.00")

        waive_list_seats = {row["seat_id"] for row in get_outstanding_rent_by_seat(classroom.class_id)}
        assert paid.seat.id not in waive_list_seats
        assert unpaid.seat.id in waive_list_seats


def test_unpaid_insurance_premium_is_outstanding_for_the_frozen_premium(app):
    """Regression: the premium resolved to 0, so an unpaid premium read as SATISFIED."""
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="obligation-state:premium"):
            policy = insurance_definition_service.create_insurance_definition(
                class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat_id,
                definition={
                    "insurance_type": "TRANSACTION",
                    "premium": "12.50",
                    "charge_frequency": "MONTHLY",
                    "reimbursement_percentage": "100",
                    "payout_multiple": "1",
                    "claims_per_week_equivalent": "1",
                    "claim_window_days": 7,
                    "title": "Premium state",
                },
            )
            correlation_id = f"premium:{uuid4().hex}"
            assess_obligation(
                AssessmentRequest(
                    seat_id=student.seat.id,
                    class_id=classroom.class_id,
                    internal_ref=f"insurance:{uuid4().hex}",
                    correlation_id=correlation_id,
                    obligation_type="INSURANCE_PREMIUM",
                    policy_uuid=policy.policy_uuid,
                ),
                context=None,
            )

        state = obligations_service.get_obligation_state(correlation_id)
        assert state.assessed_amount == Decimal("12.50")
        assert state.is_outstanding
        assert state.remaining_amount == Decimal("12.50")
