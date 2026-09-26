"""Advance assessment, withdrawal, current cycle, termination — DOM-OBL-001 v3.2.

Holds the ratified rules:

- §V.7 a successor is assessed at ``next_assessment_at − preview``, the preview
  read from the predecessor's OWN frozen policy version; a later policy
  submission cannot move it;
- §V.7 the current cycle is the one whose period contains the reference time,
  never simply the latest; a scheduled cycle beginning at or after the
  termination instant never becomes effective;
- §V.7 stop-renewal terminates at the end of the last committed period, and a
  not-yet-begun period is committed once any satisfaction is applied;
- §V.8 WITHDRAWN: only for an untouched, not-yet-begun period; never owed, not
  satisfied, not payable, never required; nothing may satisfy it afterwards;
- §VIII "required obligations satisfied" and the oldest-outstanding default.

Events are stamped with the real clock while these tests inject January 2026
reference times, so a read evaluated as of a January reference does not see
facts recorded "today". Each test states which it relies on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.base import FEATContext
from app.feats.rent_payment_feat import execute_rent_payment
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_waiver
from app.feats.schedule_next_bill_cycle_feat import execute_schedule_next_bill_cycle
from app.feats.terminate_bill_cycle_feat import TerminateBillCycleRequest, terminate_bill_cycle
from app.feats.withdraw_obligation_feat import (
    ObligationNotWithdrawableError,
    WithdrawAssessmentRequest,
    withdraw_assessment,
)
from app.models import BillCycle
from app.services import obligations_service
from app.services.obligations_service import SuccessionEligibility
from tests.helpers.class_domain import customize_rent_settings
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction


# chemistry_p1 is America/Los_Angeles (UTC-8 in winter): local midnight = 08:00 UTC.
def _local_midnight(month, day):
    return datetime(2026, month, day, 8, 0, tzinfo=timezone.utc)


JAN_1, FEB_1, MAR_1 = _local_midnight(1, 1), _local_midnight(2, 1), _local_midnight(3, 1)
PREVIEW_POINT = _local_midnight(1, 25)  # FEB_1 minus 7 local days
IN_PREVIEW = _local_midnight(1, 26)
LINEAGE = "lineage:advance"


def _policy(classroom, preview_days, *, incremental=False):
    return customize_rent_settings(
        classroom.class_id,
        rent_amount=Decimal("50.00"),
        late_penalty_amount=Decimal("0.00"),
        bill_preview_enabled=preview_days > 0,
        bill_preview_days=preview_days or 7,
        allow_incremental_payment=incremental,
    )


def _cycle(classroom, policy, start, end, reference):
    return execute_schedule_next_bill_cycle(
        classroom.class_id, LINEAGE,
        cycle_boundary_at=start, next_assessment_at=end,
        policy_uuid=policy.policy_uuid,
        idempotency_key=f"cycle:{uuid4().hex}", reference_time_utc=reference,
    )


def _assess(classroom, student, cycle, policy):
    correlation_id = f"rent-test:{student.seat.id}:{cycle.cycle_number}:{uuid4().hex[:6]}"
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"assess:{correlation_id}"):
        assess_obligation(
            AssessmentRequest(
                seat_id=student.seat.id, class_id=classroom.class_id,
                internal_ref=f"rent-test:{student.seat.id}", correlation_id=correlation_id,
                obligation_type="RENT", policy_uuid=policy.policy_uuid, bill_cycle_id=cycle.id,
            ),
            context=None,
        )
    return correlation_id


def _fund(classroom, student):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund:{uuid4().hex}", seat_id=student.seat.id,
            class_id=classroom.class_id, amount=Decimal("200.00"),
            account_type="checking", type="payroll", description="Test funding",
        )


def _pay(classroom, student, correlation_id, amount=None):
    return execute_rent_payment(
        classroom.class_id, student.seat.id, correlation_id,
        idempotency_key=f"pay:{uuid4().hex}", payment_amount=amount,
    )


def _withdraw(classroom, correlation_id, reference):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"withdraw:{uuid4().hex}"):
        return withdraw_assessment(WithdrawAssessmentRequest(
            class_id=classroom.class_id, correlation_id=correlation_id,
            reference_time_utc=reference,
        ))


def _terminate(classroom, reference, termination_at=None):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"terminate:{uuid4().hex}"):
        return terminate_bill_cycle(TerminateBillCycleRequest(
            class_id=classroom.class_id, internal_ref=LINEAGE,
            termination_at=termination_at, reference_time_utc=reference,
        ))


def _current(classroom, reference):
    return obligations_service.get_current_bill_cycle(
        classroom.class_id, LINEAGE, reference_time_utc=reference
    )


@pytest.fixture
def advance(app):
    """Cycle 1 (Jan 1 → Feb 1) and, advance-assessed during the preview window,
    cycle 2 (Feb 1 → Mar 1), each with one student's rent assessment."""
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        policy = _policy(classroom, 7, incremental=True)
        cycle1 = _cycle(classroom, policy, JAN_1, FEB_1, JAN_1)
        first = _assess(classroom, student, cycle1, policy)
        cycle2 = _cycle(classroom, policy, FEB_1, MAR_1, IN_PREVIEW)
        second = _assess(classroom, student, cycle2, policy)
        db.session.commit()
        yield classroom, student, policy, cycle1.id, cycle2.id, first, second


# --------------------------------------------------------------------------- #
# Advance assessment (succession at the preview point)                         #
# --------------------------------------------------------------------------- #


def test_succession_waits_for_the_preview_point(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _cycle(classroom, _policy(classroom, 7), JAN_1, FEB_1, JAN_1)

        def eligibility(reference):
            return obligations_service.get_succession_eligibility(
                classroom.class_id, LINEAGE, reference_time_utc=reference
            )[0]

        assert eligibility(PREVIEW_POINT - timedelta(seconds=1)) is SuccessionEligibility.NOT_DUE
        assert eligibility(PREVIEW_POINT) is SuccessionEligibility.DUE


def test_zero_preview_assesses_at_the_boundary_itself(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cycle = _cycle(classroom, _policy(classroom, 0), JAN_1, FEB_1, JAN_1)
        assert obligations_service.get_assessment_point(cycle) == FEB_1


def test_a_later_policy_version_does_not_move_an_existing_cycles_assessment_point(app):
    """DOM-POL-001 §VII: the cycle resolves its OWN frozen policy version."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cycle = _cycle(classroom, _policy(classroom, 7), JAN_1, FEB_1, JAN_1)
        _policy(classroom, 2)  # teacher submits a new version with a 2-day preview
        assert obligations_service.get_assessment_point(cycle) == PREVIEW_POINT


# --------------------------------------------------------------------------- #
# Current cycle                                                                #
# --------------------------------------------------------------------------- #


def test_current_cycle_is_the_period_containing_the_reference_not_the_latest(app, advance):
    classroom, _, _, cycle1_id, cycle2_id, _, _ = advance
    with app.app_context():
        latest = obligations_service.get_latest_bill_cycle(LINEAGE)
        assert latest.id == cycle2_id
        assert _current(classroom, IN_PREVIEW).id == cycle1_id
        assert _current(classroom, FEB_1 - timedelta(seconds=1)).id == cycle1_id
        assert _current(classroom, FEB_1).id == cycle2_id


# --------------------------------------------------------------------------- #
# Withdrawal                                                                   #
# --------------------------------------------------------------------------- #


def test_withdrawn_assessment_is_neither_owed_nor_satisfied(app, advance):
    classroom, _, _, _, _, _, second = advance
    with app.app_context():
        _withdraw(classroom, second, IN_PREVIEW)
        state = obligations_service.get_obligation_state(second)

        assert state.is_withdrawn
        assert not state.is_satisfied and not state.is_outstanding and not state.is_payable
        assert state.remaining_amount == Decimal("0.00")
        assert not obligations_service.is_obligation_past_due(state, reference_time_utc=MAR_1)
        # Withdrawal is append-only: the ASSESSMENT is still there.
        assert obligations_service.get_assessment_for_correlation(second) is not None


def test_withdrawal_is_idempotent(app, advance):
    classroom, _, _, _, _, _, second = advance
    with app.app_context():
        first = _withdraw(classroom, second, IN_PREVIEW)
        again = _withdraw(classroom, second, IN_PREVIEW)
        assert first.id == again.id


def test_withdrawal_is_refused_once_the_period_has_begun(app, advance):
    classroom, _, _, _, _, _, second = advance
    with app.app_context():
        with pytest.raises(ObligationNotWithdrawableError, match="began"):
            _withdraw(classroom, second, FEB_1 + timedelta(seconds=1))


def test_withdrawal_at_exactly_the_boundary_prevents_the_period(app, advance):
    """§IX.15: a cancellation effective AT the boundary prevents that period."""
    classroom, _, _, _, _, _, second = advance
    with app.app_context():
        _withdraw(classroom, second, FEB_1)
        assert obligations_service.get_obligation_state(second).is_withdrawn


def test_withdrawal_is_refused_once_any_payment_is_applied(app, advance):
    classroom, student, _, _, _, _, second = advance
    with app.app_context():
        _fund(classroom, student)
        assert _pay(classroom, student, second, Decimal("5.00")).success
        with pytest.raises(ObligationNotWithdrawableError, match="committed"):
            _withdraw(classroom, second, IN_PREVIEW)


def test_nothing_may_satisfy_a_withdrawn_assessment(app, advance):
    classroom, student, _, _, _, _, second = advance
    with app.app_context():
        _withdraw(classroom, second, IN_PREVIEW)
        db.session.commit()
        _fund(classroom, student)

        payment = _pay(classroom, student, second)
        assert not payment.success and payment.error_code == "WITHDRAWN"
        with pytest.raises(ValueError, match="withdrawn"):
            execute_satisfy_obligation_waiver(
                correlation_id=second, class_id=classroom.class_id,
                seat_id=student.seat.id, idempotency_key=f"waive:{second}",
            )
        assert obligations_service.get_satisfaction_events(second) == []


def test_interpretation_feed_drops_withdrawn_assessments(app, advance):
    classroom, _, _, _, _, first, second = advance
    with app.app_context():
        _withdraw(classroom, second, IN_PREVIEW)
        db.session.commit()
        far_future = datetime(2100, 1, 1, tzinfo=timezone.utc)
        events = obligations_service.get_obligation_events_for_window(
            classroom.class_id, datetime(2000, 1, 1, tzinfo=timezone.utc), far_future
        )
        correlations = {row.correlation_id for row in events}
        assert first in correlations
        assert second not in correlations


# --------------------------------------------------------------------------- #
# Termination                                                                  #
# --------------------------------------------------------------------------- #


def test_stop_renewal_withdraws_an_untouched_upcoming_period(app, advance):
    classroom, _, _, cycle1_id, cycle2_id, first, second = advance
    with app.app_context():
        terminal = _terminate(classroom, IN_PREVIEW)

        assert terminal.cycle_boundary_at == FEB_1  # end of the current period
        assert obligations_service.get_obligation_state(second).is_withdrawn
        assert obligations_service.get_obligation_state(first).is_outstanding  # still owed
        cycle2 = db.session.get(BillCycle, cycle2_id)
        assert (cycle2.cycle_boundary_at, cycle2.next_assessment_at) == (FEB_1, MAR_1)  # unaltered
        assert _current(classroom, FEB_1 + timedelta(days=1)) is None  # never effective
        assert _current(classroom, IN_PREVIEW).id == cycle1_id


def test_stop_renewal_keeps_an_upcoming_period_with_any_payment(app, advance):
    classroom, student, _, _, cycle2_id, _, second = advance
    with app.app_context():
        _fund(classroom, student)
        assert _pay(classroom, student, second, Decimal("5.00")).success  # partial commits it
        terminal = _terminate(classroom, IN_PREVIEW)

        assert terminal.cycle_boundary_at == MAR_1  # the committed period runs to its end
        state = obligations_service.get_obligation_state(second)
        assert not state.is_withdrawn and state.remaining_amount == Decimal("45.00")
        assert _current(classroom, FEB_1 + timedelta(days=1)).id == cycle2_id
        assert _current(classroom, MAR_1) is None


def test_deadline_termination_withdraws_later_periods_and_keeps_earlier_debt(app, advance):
    classroom, _, _, _, _, first, second = advance
    with app.app_context():
        deadline = _local_midnight(1, 28)
        terminal = _terminate(classroom, IN_PREVIEW, termination_at=deadline)

        assert terminal.cycle_boundary_at == deadline
        assert obligations_service.get_obligation_state(second).is_withdrawn
        assert obligations_service.get_obligation_state(first).is_outstanding


# --------------------------------------------------------------------------- #
# Required obligations and payment target                                      #
# --------------------------------------------------------------------------- #


def test_required_obligations_ignore_not_yet_due_and_withdrawn(app, advance):
    classroom, student, _, _, _, first, second = advance
    with app.app_context():
        def required(reference=None):
            return obligations_service.are_required_obligations_satisfied(
                classroom.class_id, LINEAGE, reference_time_utc=reference
            )

        # In the preview window cycle 2's bill exists but is not due; cycle 1's is unpaid.
        assert not required(IN_PREVIEW)
        _fund(classroom, student)
        assert _pay(classroom, student, first).success
        # Evaluated now (the payment's real timestamp precedes now): cycle 1 is
        # paid, and cycle 2's bill is due but unpaid.
        assert not required()
        _withdraw(classroom, second, IN_PREVIEW)
        assert required()  # a withdrawn bill is never required


def test_required_obligations_are_prospective(app, advance):
    """Facts recorded after the reference time do not count at it."""
    classroom, student, _, _, _, first, second = advance
    with app.app_context():
        _fund(classroom, student)
        assert _pay(classroom, student, first).success
        assert _pay(classroom, student, second).success
        assert obligations_service.are_required_obligations_satisfied(classroom.class_id, LINEAGE)
        assert not obligations_service.are_required_obligations_satisfied(
            classroom.class_id, LINEAGE, reference_time_utc=_local_midnight(1, 2)
        )


def test_default_payment_target_is_the_oldest_outstanding(app, advance):
    classroom, student, _, _, _, first, second = advance
    with app.app_context():
        ref = f"rent-test:{student.seat.id}"
        assert obligations_service.get_default_payment_target(classroom.class_id, ref).correlation_id == first
        _fund(classroom, student)
        assert _pay(classroom, student, first).success
        assert obligations_service.get_default_payment_target(classroom.class_id, ref).correlation_id == second
