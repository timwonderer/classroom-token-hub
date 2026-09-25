"""Disabling rent stops new rent and strands none — DOM-OBL-001 v3.2 §V.8, §IX.15-16.

Holds the ratified rules:

- disabling rent withdraws an untouched advance rent assessment for a period
  that has not begun; any satisfaction commits that period for its seat, and a
  partly paid remainder stays owed;
- a period paid in advance grants its perks when it begins, not at payment,
  and still does so while rent is disabled;
- reconciliation while rent is disabled schedules no successor and assesses
  nothing new, but late fees on surviving debt keep accruing;
- /rent stays reachable while the seat has rent to view or pay, and is absent
  when rent is disabled and nothing survives;
- paying off the surviving rent does not re-enable rent.

The disable FEAT and the /rent route read the real clock, so the rent lineage
here is built relative to it: a weekly cycle that began five days ago, with the
next period already advance-assessed (preview 3 days).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.feats.base import FEATContext
from app.feats.class_configuration import execute_disable_feature
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment, perks_already_granted
from app.models import BillCycle, ObligationAssessment
from app.services import obligations_service
from app.services.class_configuration_query_service import is_feature_enabled
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _configure_rent(classroom, *, late_penalty=Decimal("0.00")):
    """Rent enabled, weekly, cycle 1 begun 5 days ago, cycle 2 advance-assessed."""
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    customize_rent_settings(
        classroom.class_id,
        frequency_type="weekly",
        first_rent_due_date=utc_now() - timedelta(days=5),
        grace_period_days=1,
        rent_amount=Decimal("50.00"),
        bill_preview_enabled=True,
        bill_preview_days=3,
        allow_incremental_payment=True,
        late_penalty_amount=late_penalty,
        late_penalty_type="recurring",
        late_penalty_frequency_days=1,
        satisfaction_benefits=[{"entitlement_type": "HALL_PASS", "quantity": 2}],
    )


def _reconcile(classroom, reference):
    return execute_reconcile_rent(
        classroom.class_id,
        reference_time_utc=reference,
        idempotency_key=f"reconcile:{uuid4().hex}",
    )


def _cycles(classroom):
    return (
        BillCycle.query.filter_by(class_id=classroom.class_id, internal_ref=f"rent:{classroom.class_id}")
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def _rent_assessment_count(classroom):
    return ObligationAssessment.query.filter_by(
        class_id=classroom.class_id, event_type="ASSESSMENT", obligation_type="RENT"
    ).count()


def _rent_correlation(classroom, seat_id, cycle_number):
    return f"rent:{classroom.class_id}:{seat_id}:cycle:{cycle_number}"


def _fund(classroom, seat_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund:{uuid4().hex}", seat_id=seat_id,
            class_id=classroom.class_id, amount=Decimal("500.00"),
            account_type="checking", type="payroll", description="Test funding",
        )


def _pay(classroom, seat_id, correlation_id, amount=None):
    result = execute_rent_payment(
        classroom.class_id, seat_id, correlation_id,
        idempotency_key=f"pay:{uuid4().hex}", payment_amount=amount,
    )
    assert result.success, result
    return result


def _disable_rent(classroom):
    result = execute_disable_feature(
        canonical_context=CanonicalContext(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat.id,
            actor_role="teacher",
        ),
        class_id=classroom.class_id,
        feature="rent",
        idempotency_key=f"disable:{uuid4().hex}",
    )
    assert result.success, result.error_message
    return result


def _state(correlation_id):
    return obligations_service.get_obligation_state(correlation_id)


def _built(app, *, late_penalty=Decimal("0.00")):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _configure_rent(classroom, late_penalty=late_penalty)
        _reconcile(classroom, utc_now())
        cycles = _cycles(classroom)
        assert [c.cycle_number for c in cycles] == [1, 2], "cycle 2 must be advance-assessed"
        assert obligations_service.get_current_bill_cycle(
            classroom.class_id, f"rent:{classroom.class_id}"
        ).cycle_number == 1
    return classroom


def test_disabling_rent_withdraws_untouched_advance_rent_and_keeps_committed_periods(app):
    classroom = _built(app)
    with app.app_context():
        untouched, partial, full = (s.seat.id for s in classroom.students[:3])
        for seat_id in (partial, full):
            _fund(classroom, seat_id)
        _pay(classroom, partial, _rent_correlation(classroom, partial, 2), Decimal("20.00"))
        _pay(classroom, full, _rent_correlation(classroom, full, 2))

        _disable_rent(classroom)

        assert _state(_rent_correlation(classroom, untouched, 2)).is_withdrawn
        partly = _state(_rent_correlation(classroom, partial, 2))
        assert partly.is_outstanding and partly.remaining_amount == Decimal("30.00")
        assert _state(_rent_correlation(classroom, full, 2)).is_satisfied
        # The period in effect is not prevented: its rent stays owed for everyone.
        for seat_id in (untouched, partial, full):
            assert _state(_rent_correlation(classroom, seat_id, 1)).is_outstanding


def test_period_paid_in_advance_grants_perks_when_it_begins_even_while_disabled(app):
    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        correlation_id = _rent_correlation(classroom, seat_id, 2)
        _fund(classroom, seat_id)
        _pay(classroom, seat_id, correlation_id)
        assert not perks_already_granted(classroom.class_id, correlation_id), (
            "payment during the preview window grants nothing early"
        )

        _disable_rent(classroom)
        second = _cycles(classroom)[1]
        _reconcile(classroom, second.cycle_boundary_at + timedelta(hours=1))

        assert perks_already_granted(classroom.class_id, correlation_id)


def test_reconcile_while_rent_is_disabled_schedules_and_assesses_nothing(app):
    classroom = _built(app)
    with app.app_context():
        _disable_rent(classroom)
        before = _rent_assessment_count(classroom)
        second = _cycles(classroom)[1]

        result = _reconcile(classroom, second.next_assessment_at + timedelta(days=8))

        assert result.cycles_created == []
        assert [c.cycle_number for c in _cycles(classroom)] == [1, 2]
        assert _rent_assessment_count(classroom) == before


def test_late_fees_on_surviving_rent_keep_accruing_after_rent_is_disabled(app):
    classroom = _built(app, late_penalty=Decimal("5.00"))
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        late_ref = f"rent:{classroom.class_id}:{seat_id}:late"

        def late_fees():
            return ObligationAssessment.query.filter_by(
                class_id=classroom.class_id, internal_ref=late_ref, event_type="ASSESSMENT"
            ).count()

        accrued_before_disable = late_fees()
        assert accrued_before_disable >= 1, "cycle 1's grace lapsed four days ago"

        _disable_rent(classroom)
        _reconcile(classroom, utc_now() + timedelta(days=3))

        assert late_fees() > accrued_before_disable


def test_paying_off_surviving_rent_does_not_re_enable_rent(app):
    classroom = _built(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        _disable_rent(classroom)
        _fund(classroom, seat_id)
        _pay(classroom, seat_id, _rent_correlation(classroom, seat_id, 1))
        assert _state(_rent_correlation(classroom, seat_id, 1)).is_satisfied

        assert not is_feature_enabled(classroom.class_id, "rent")
        second = _cycles(classroom)[1]
        result = _reconcile(classroom, second.next_assessment_at + timedelta(hours=1))
        assert result.cycles_created == []
        # The last scheduled period has ended and none follows it.
        assert obligations_service.get_current_bill_cycle(
            classroom.class_id, f"rent:{classroom.class_id}",
            reference_time_utc=second.next_assessment_at + timedelta(hours=1),
        ) is None


def test_rent_page_stays_reachable_while_rent_survives_disablement(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _configure_rent(classroom)
        _reconcile(classroom, utc_now())
        _disable_rent(classroom)
        assert _state(_rent_correlation(classroom, student.seat.id, 1)).is_outstanding

    response = client.get("/student/rent")
    assert response.status_code == 200


def test_rent_page_is_absent_when_rent_is_disabled_and_nothing_survives(client, app):
    classroom, _student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _configure_rent(classroom)
        _disable_rent(classroom)

    response = client.get("/student/rent")
    assert response.status_code == 404
