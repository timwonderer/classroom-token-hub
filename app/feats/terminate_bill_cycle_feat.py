"""
Bill-cycle termination — the Obligations command that STOPS a recurring lineage.

Succession and termination are the two bill-cycle operations (DOM-OBL-001 §V.7):

    succession:   nothing -> cycle 1, cycle N -> cycle N+1  (schedule_next_bill_cycle)
    termination:  cycle N -> cycle N+1*   (this module)  *terminal, no recurrence

Termination is cessation, not succession, so it does not route through
``schedule_next_bill_cycle``. (Insurance purchase still creates its cycle 1 through
the interim ``establish_bill_cycle`` until the insurance lineage migrates.)

A terminal cycle row carries ``next_assessment_at = NULL``: the lineage produces
no further recurring assessment. Its ``cycle_boundary_at`` is the termination
instant (DOM-OBL-001 §V.7): the end of the last committed period on stop-renewal,
or an owning domain's lawful deadline. It does NOT rewrite prior obligation
events (§IX.5, §IX.7); it withdraws only untouched advance assessments of periods
that would begin at or after the instant (§V.8). Ending the entitlement at that
instant is a separate, Store-owned disposition (FEAT-STOR-002 EXPIRED), never
performed here.

Insurance cancellation (FEAT-OBL-005) terminates the recurring
``INSURANCE_PREMIUM`` lineage through this command — stopping future premiums
without revoking, refunding, or early-expiring the paid coverage
(FEAT-STOR-002 §IX.C: insurance is non-revocable).

This is a domain command, not a user-facing FEAT: it carries no FEAT-registry
number of its own and executes under the shared bill-cycle mutation-authority tag
``FEAT-OBL-002`` (the same coarse authority as succession). The
termination distinction lives in the command contract, not the authority tag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.extensions import db
from app.models import BillCycle, ObligationAssessment
from app.feats.withdraw_obligation_feat import WithdrawAssessmentRequest, withdraw_assessment
from app.services import obligations_service
from app.services.obligations_service import BillCycleLifecycleError
from app.feats.base import requires_feat_context, FEATContext


@dataclass
class TerminateBillCycleRequest:
    """Input contract for bill-cycle termination.

    ``termination_at`` is supplied only by an owning domain terminating at its own
    lawful deadline (e.g. an insurance nonpayment deadline). Omitted, this is a
    stop-renewal and the domain derives the termination instant itself: the end
    of the last committed period (DOM-OBL-001 §V.7). The policy identity is
    carried forward; termination never reinterprets it (INV-ARC-009).
    """
    class_id: str  # Multi-tenancy scope (INV-CORE-000)
    internal_ref: str  # Stable lineage key for the continuing relationship
    termination_at: datetime | None = None
    reference_time_utc: datetime | None = None


def _cycle_assessments(cycle: BillCycle) -> list[ObligationAssessment]:
    return (
        db.session.query(ObligationAssessment)
        .filter_by(bill_cycle_id=cycle.id, event_type="ASSESSMENT")
        .all()
    )


def _is_committed(cycle: BillCycle) -> bool:
    """A not-yet-begun period is committed once any satisfaction is applied (§V.8)."""
    return any(
        obligations_service.get_satisfaction_events(a.correlation_id)
        for a in _cycle_assessments(cycle)
    )


def _stop_renewal_instant(request: TerminateBillCycleRequest, latest: BillCycle) -> datetime:
    """End of the last committed period (DOM-OBL-001 §V.7).

    The current period is committed. A scheduled, not-yet-begun period (created
    by advance assessment) is committed only if any satisfaction has been applied
    to its assessment; then the lineage runs to that period's end.
    """
    current = obligations_service.get_current_bill_cycle(
        request.class_id, request.internal_ref, reference_time_utc=request.reference_time_utc
    )
    if current is None or latest.id == current.id:
        return latest.next_assessment_at
    # ``latest`` is a scheduled upcoming cycle whose period has not begun.
    if _is_committed(latest):
        return latest.next_assessment_at
    return current.next_assessment_at


def terminate_bill_cycle(
    request: TerminateBillCycleRequest,
    *,
    context: FEATContext | None = None,
) -> BillCycle:
    """Terminate a recurring obligation lineage by appending a terminal cycle.

    The terminal row's ``cycle_boundary_at`` is the termination instant
    (DOM-OBL-001 §V.7). In the same transaction, every unsatisfied advance
    assessment for a period beginning at or after that instant is withdrawn
    (§V.8); a period that began before it keeps its assessment, which stays due.
    Scheduled cycles beginning at or after the instant are left unaltered and
    never become effective. Prior cycles and events are never rewritten.

    Idempotent: an already-terminal lineage returns its terminal row unchanged.

    Raises BillCycleLifecycleError if no cycle exists for the lineage, or it is
    out of the requested class scope.
    """
    latest = obligations_service.get_latest_bill_cycle(request.internal_ref)
    if latest is None:
        raise BillCycleLifecycleError(
            f"terminate_bill_cycle requires an existing cycle for lineage "
            f"'{request.internal_ref}'; nothing to terminate."
        )
    if latest.class_id != request.class_id:
        raise BillCycleLifecycleError(
            f"class scope mismatch for lineage '{request.internal_ref}': "
            f"cycle belongs to class {latest.class_id}, not {request.class_id}."
        )
    if latest.next_assessment_at is None:
        return latest

    instant = request.termination_at or _stop_renewal_instant(request, latest)

    # Withdraw every untouched assessment of a period that begins at or after the
    # instant; periods with any satisfaction are committed and keep theirs.
    scheduled_after = (
        db.session.query(BillCycle)
        .filter(
            BillCycle.class_id == request.class_id,
            BillCycle.internal_ref == request.internal_ref,
            BillCycle.next_assessment_at.isnot(None),
            BillCycle.cycle_boundary_at >= instant,
        )
        .all()
    )
    for cycle in scheduled_after:
        for assessment in _cycle_assessments(cycle):
            if obligations_service.get_satisfaction_events(assessment.correlation_id):
                continue
            withdraw_assessment(
                WithdrawAssessmentRequest(
                    class_id=request.class_id,
                    correlation_id=assessment.correlation_id,
                    reference_time_utc=request.reference_time_utc,
                    notes="Renewal ended before this period began",
                )
            )

    terminal = BillCycle(
        class_id=latest.class_id,
        internal_ref=latest.internal_ref,
        cycle_number=latest.cycle_number + 1,
        source_version_id=latest.source_version_id,
        policy_uuid=latest.policy_uuid,
        cycle_boundary_at=instant,  # the termination instant
        next_assessment_at=None,  # TERMINAL — stops future recurrence
        grace_boundary_at=None,
    )
    db.session.add(terminal)
    db.session.flush()
    return terminal


@requires_feat_context("FEAT-OBL-002")
def execute_terminate_bill_cycle(
    class_id: str,
    internal_ref: str,
) -> BillCycle:
    """Public entry for bill-cycle termination under the shared FEAT-OBL-002 authority.

    Termination carries no FEAT-registry number of its own; it runs under the
    bill-cycle mutation-authority tag. Composing callers (e.g. FEAT-OBL-005) invoke
    the plain ``terminate_bill_cycle`` command inside their own context instead.
    """
    return terminate_bill_cycle(
        TerminateBillCycleRequest(class_id=class_id, internal_ref=internal_ref),
        context=None,
    )
