"""Obligation withdrawal — DOM-OBL-001 §V.8.

A withdrawal records that an advance assessment never became owed, because the
future period it was assessed for ceased to be lawful before it became effective
and before any satisfaction occurred. It exists so that advance assessment can
never make a future liability survive an action that, absent advance
assessment, would have prevented it from arising.

This is a domain command, not a FEAT: it is invoked only inside the transaction
of the action that cancels the period (lineage termination, or disablement of
the capability the period depends on), and it carries no FEAT-registry number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from app.extensions import db
from app.models import BillCycle, ObligationAssessment
from app.services import obligations_service
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


class ObligationNotWithdrawableError(Exception):
    """The assessment does not meet DOM-OBL-001 §V.8's conditions for withdrawal."""


@dataclass
class WithdrawAssessmentRequest:
    class_id: str
    correlation_id: str
    reference_time_utc: datetime | None = None
    notes: str | None = None


def withdraw_assessment(request: WithdrawAssessmentRequest) -> ObligationAssessment:
    """Append ``WITHDRAWN`` for an untouched advance assessment. Idempotent.

    Lawful only when the assessment is bound to a bill cycle whose period has
    not begun at the reference time, and no ``PAYMENT`` or ``WAIVED`` has been
    recorded against it. The ``ASSESSMENT`` row itself is never altered.

    Raises ``ObligationNotWithdrawableError`` otherwise.
    """
    assessment = obligations_service.get_assessment_for_correlation(request.correlation_id)
    if assessment is None or assessment.class_id != request.class_id:
        raise ObligationNotWithdrawableError(
            f"no assessment {request.correlation_id!r} in class {request.class_id!r}"
        )

    existing = obligations_service.get_withdrawal_event(request.correlation_id)
    if existing is not None:
        return existing

    cycle = db.session.get(BillCycle, assessment.bill_cycle_id) if assessment.bill_cycle_id else None
    if cycle is None:
        raise ObligationNotWithdrawableError(
            f"{request.correlation_id!r} is not bound to a scheduled period"
        )
    period_not_begun = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=request.class_id),
        primitive="later_than",
        reference_time_utc=request.reference_time_utc,
        candidate=cycle.cycle_boundary_at,
        reference=canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=SimpleNamespace(class_id=request.class_id),
            primitive="current_time",
            reference_time_utc=request.reference_time_utc,
        ).canonical_now_utc,
    ).is_later
    if not period_not_begun:
        raise ObligationNotWithdrawableError(
            f"{request.correlation_id!r}: its period began at {cycle.cycle_boundary_at}"
        )
    if obligations_service.get_satisfaction_events(request.correlation_id):
        raise ObligationNotWithdrawableError(
            f"{request.correlation_id!r} has a recorded satisfaction; its period is committed"
        )

    withdrawal = ObligationAssessment(
        seat_id=assessment.seat_id,
        class_id=assessment.class_id,
        internal_ref=assessment.internal_ref,
        correlation_id=assessment.correlation_id,
        event_type="WITHDRAWN",
        obligation_type=assessment.obligation_type,
        policy_version_id=assessment.policy_version_id,
        bill_cycle_id=assessment.bill_cycle_id,
        notes=(request.notes or "").strip() or None,
    )
    db.session.add(withdrawal)
    db.session.flush()
    return withdrawal
