"""Overlapping reconcile runs must not double-assess the same obligation (audit F8).

``check_idempotency_assessment`` is a plain read before the insert, with no
row lock. Migration 8a7b6c5d4e3f (2026-07-25) deliberately dropped the
blanket-unique index on ``correlation_id`` alone, because one correlation_id
legitimately carries several ``event_type`` rows (ASSESSMENT, PAYMENT,
WAIVED). That left the read-then-insert check as the only protection for the
narrower promise FEAT-OBLI-001 §IV.3 actually makes — exactly one ASSESSMENT
per (internal_ref, correlation_id) — and two reconcile runs that overlap (the
scheduler losing and regaining its ownership lock without the old run having
finished; see audit O5 and app/scheduler_ownership.py) can both pass that
read before either commits.

These force the race window open directly: the idempotency check is made to
report "not yet assessed" on both calls, as it would for two overlapping
transactions that have not committed yet, and assert the database-level
backstop (migration 6a01dc7a606b) still yields exactly one ASSESSMENT row,
with the loser recovering the winner's row rather than raising or duplicating.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.base import FEATContext
from app.models import ObligationAssessment
from app.services import obligations_service
from tests.helpers.classroom_initializer import initialize


def _count(internal_ref, correlation_id):
    return ObligationAssessment.query.filter_by(
        internal_ref=internal_ref, correlation_id=correlation_id, event_type="ASSESSMENT",
    ).count()


def test_two_overlapping_assessments_for_the_same_lineage_do_not_duplicate(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        class_id = classroom.class_id
        internal_ref = "rent:race"
        correlation_id = "rent-race-cycle-1"

        # Simulate the race: both callers see "not yet assessed" because
        # neither transaction has committed when the other reads.
        monkeypatch.setattr(obligations_service, "check_idempotency_assessment", lambda *a, **k: False)

        kwargs = dict(
            seat_id=seat_id, class_id=class_id, internal_ref=internal_ref,
            correlation_id=correlation_id, obligation_type="RENT",
        )
        first = execute_assess_obligation(**kwargs)
        second = execute_assess_obligation(**kwargs)

        assert second.id == first.id, "the loser of the race must recover the winner's row, not insert a second one"
        assert _count(internal_ref, correlation_id) == 1


def test_a_different_event_type_for_the_same_correlation_id_is_unaffected(app):
    """Control: the narrower constraint must not resurrect the blanket
    correlation_id uniqueness 8a7b6c5d4e3f removed — PAYMENT alongside
    ASSESSMENT for the same correlation_id is still legitimate."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        class_id = classroom.class_id

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="race-control:assessment"):
            db.session.add(ObligationAssessment(
                seat_id=seat_id, class_id=class_id, internal_ref="rent:control",
                correlation_id="rent-control-cycle-1", event_type="ASSESSMENT", obligation_type="RENT",
            ))
            db.session.add(ObligationAssessment(
                seat_id=seat_id, class_id=class_id, internal_ref="rent:control",
                correlation_id="rent-control-cycle-1", event_type="PAYMENT", obligation_type="RENT",
            ))

        assert ObligationAssessment.query.filter_by(correlation_id="rent-control-cycle-1").count() == 2


def test_the_constraint_still_rejects_a_true_duplicate_bypassing_the_feat(app):
    """Control: the constraint itself, not just the FEAT's recovery path."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        seat_id = classroom.students[0].seat.id
        class_id = classroom.class_id
        kwargs = dict(
            seat_id=seat_id, class_id=class_id, internal_ref="rent:raw",
            correlation_id="rent-raw-cycle-1", event_type="ASSESSMENT", obligation_type="RENT",
        )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="race-control:raw-1"):
            db.session.add(ObligationAssessment(**kwargs))

        with pytest.raises(IntegrityError):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="race-control:raw-2"):
                db.session.add(ObligationAssessment(**kwargs))
