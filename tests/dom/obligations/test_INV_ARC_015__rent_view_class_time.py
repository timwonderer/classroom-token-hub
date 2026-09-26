"""The student rent view speaks class time — INV-ARC-015 §VII, §X.2; SPEC-TIME-001.

The view must agree with when rent consequences actually happen. A late fee is
charged by ``reconcile_rent_feat`` once the cycle's persisted
``grace_boundary_at`` has passed, so the view reads that same instant and never
re-derives one. The old fallback re-derived it as ``due + grace × 24h``: after
the November fall-back that is 23:00 the previous class day, and for a cycle
with no grace boundary at all it reported a bill late — with a late fee — that
reconciliation never charges.

Displayed dates are class-local: a class-midnight boundary's UTC date is the
previous day in any class east of Greenwich.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.extensions import db
from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.schedule_next_bill_cycle_feat import execute_schedule_next_bill_cycle
from app.models import BillCycle, ObligationAssessment
from app.services.obligation_view_model import (
    add_display_formatting_to_student_obligation_view,
    build_student_obligation_view,
)
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _class_midnight(class_id, day):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="evaluation_day_boundaries",
        evaluation_date=day,
    ).boundary_start_utc


def _view(classroom, seat_id, reference):
    return build_student_obligation_view(
        seat_id, classroom.class_id, "RENT", reference_time_utc=reference
    ).current_period


def _late_fees(classroom, seat_id):
    return ObligationAssessment.query.filter_by(
        class_id=classroom.class_id, seat_id=seat_id,
        obligation_type="LATE_FEE", event_type="ASSESSMENT",
    ).count()


def _reconcile(classroom, reference):
    execute_reconcile_rent(
        classroom.class_id, reference_time_utc=reference,
        idempotency_key=f"reconcile:{uuid4().hex}",
    )


# US fall-back 2025-11-02. A Pacific bill due Fri Oct 31 with three grace days
# is late from 00:00 PST Mon Nov 3 (08:00 UTC). Three 24-hour days from 00:00 PDT
# Oct 31 (07:00 UTC) end at 07:00 UTC — 23:00 PST on Sunday Nov 2.
DUE_LOCAL = date(2025, 10, 31)
GRACE_BOUNDARY = _utc(2025, 11, 3, 8, 0)
SUNDAY_2330_PST = _utc(2025, 11, 3, 7, 30)
MONDAY_JUST_AFTER_MIDNIGHT_PST = _utc(2025, 11, 3, 8, 0, 1)


def _pacific_rent_due_before_the_fall_back(app):
    classroom = initialize("tz_pacific_p1", app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        customize_rent_settings(
            classroom.class_id,
            frequency_type="weekly",
            first_rent_due_date=_class_midnight(classroom.class_id, DUE_LOCAL),
            grace_period_days=3,
            rent_amount=Decimal("50.00"),
            bill_preview_enabled=False,
            late_penalty_amount=Decimal("5.00"),
            late_penalty_type="once",
        )
        _reconcile(classroom, _utc(2025, 10, 31, 12, 0))
        db.session.commit()
    return classroom


def test_INV_ARC_015__late_status_matches_reconcile_across_the_fall_back(app):
    classroom = _pacific_rent_due_before_the_fall_back(app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        cycle = BillCycle.query.filter_by(class_id=classroom.class_id).one()
        assert cycle.grace_boundary_at == GRACE_BOUNDARY

        _reconcile(classroom, SUNDAY_2330_PST)
        assert _late_fees(classroom, seat_id) == 0, "reconcile charges nothing on Sunday night"
        card = _view(classroom, seat_id, SUNDAY_2330_PST)
        assert not card["is_late"], "so the page must not call the bill late yet"
        assert card["late_fee"] == Decimal("0.00")
        assert card["grace_end"] == GRACE_BOUNDARY

        _reconcile(classroom, MONDAY_JUST_AFTER_MIDNIGHT_PST)
        assert _late_fees(classroom, seat_id) == 1
        card = _view(classroom, seat_id, MONDAY_JUST_AFTER_MIDNIGHT_PST)
        assert card["is_late"]


def test_INV_ARC_015__pay_by_is_the_last_grace_day_not_the_first_late_day(app):
    """Reconcile charges once 00:00 Monday has passed, so "pay by" is Sunday."""
    classroom = _pacific_rent_due_before_the_fall_back(app)
    with app.app_context():
        card = _view(classroom, classroom.students[0].seat.id, SUNDAY_2330_PST)
        assert card["grace_last_day"] == date(2025, 11, 2)


def test_INV_ARC_015__a_cycle_without_a_grace_boundary_is_never_late(app):
    """Reconcile never charges a late fee without a grace boundary; the page
    used to invent one from grace_period_days and show the bill late."""
    classroom = initialize("tz_pacific_p1", app)
    student = classroom.students[0]
    with app.app_context():
        policy = customize_rent_settings(
            classroom.class_id, rent_amount=Decimal("50.00"), grace_period_days=3,
            late_penalty_amount=Decimal("5.00"),
        )
        due = _class_midnight(classroom.class_id, DUE_LOCAL)
        cycle = execute_schedule_next_bill_cycle(
            classroom.class_id, f"rent:{classroom.class_id}",
            cycle_boundary_at=due,
            next_assessment_at=_class_midnight(classroom.class_id, date(2025, 11, 7)),
            policy_uuid=policy.policy_uuid, grace_boundary_at=None,
            idempotency_key=f"cycle:{uuid4().hex}", reference_time_utc=due,
        )
        correlation_id = f"rent:{classroom.class_id}:{student.seat.id}:cycle:{cycle.cycle_number}"
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"assess:{correlation_id}"):
            assess_obligation(
                AssessmentRequest(
                    seat_id=student.seat.id, class_id=classroom.class_id,
                    internal_ref=f"rent:{classroom.class_id}:{student.seat.id}",
                    correlation_id=correlation_id, obligation_type="RENT",
                    policy_uuid=policy.policy_uuid, bill_cycle_id=cycle.id,
                ),
                context=None,
            )
        db.session.commit()

        card = _view(classroom, student.seat.id, MONDAY_JUST_AFTER_MIDNIGHT_PST)
        assert card["grace_end"] is None
        assert card["grace_last_day"] is None
        assert not card["is_late"]
        assert card["late_fee"] == Decimal("0.00")


def test_INV_ARC_015__due_date_display_is_the_class_date_in_tokyo(app):
    """Oct 1 00:00 JST is Sep 30 15:00 UTC; the UTC date showed "September 30"."""
    classroom = initialize("tz_tokyo_p1", app)
    student = classroom.students[0]
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        customize_rent_settings(
            classroom.class_id, frequency_type="monthly",
            first_rent_due_date=_class_midnight(classroom.class_id, date(2025, 10, 1)),
            rent_amount=Decimal("50.00"), bill_preview_enabled=False,
        )
        reference = _utc(2025, 10, 1, 3, 0)
        _reconcile(classroom, reference)
        db.session.commit()

        view = build_student_obligation_view(
            student.seat.id, classroom.class_id, "RENT", reference_time_utc=reference
        )
        assert view.current_period["due_date"] == _utc(2025, 9, 30, 15, 0)
        display = add_display_formatting_to_student_obligation_view(view)
        assert display.display_current_due_date == "October 01, 2025"
