"""FEAT-STOR-007: Insurance Coverage Renewal.

Coordinates the recurring premium lifecycle of one insurance entitlement: assess
each period's premium in advance, attempt automatic payment, and apply the
purchased policy version's nonpayment behavior
(docs/FEATURE-EXECUTION/FEAT-STOR-007_INSURANCE_COVERAGE_RENEWAL.md).

This FEAT owns no persistence. Every mutation is the owning domain's canonical
command, composed inside this one FEAT context:

- succession and termination, assessment and satisfaction — Obligations
  (``schedule_next_bill_cycle``, ``terminate_bill_cycle``, ``assess_obligation``,
  ``satisfy_obligation`` via ``settle_insurance_premium``);
- money — Ledger, through the lawful premium payment path;
- nonpayment expiry — Store (``expire_entitlement``, FEAT-STOR-002).

One run, per entitlement, as of the canonically resolved reference time:

1. **Nonpayment first** (``CANCEL_AFTER_X_DAYS`` only). The deadline is the
   coverage boundary at which the earliest outstanding required premium lapsed
   plus ``cancel_after_days`` class-local calendar days; later assessments do
   not reset it. Once the deadline is reached with that premium still
   unsatisfied (as of the deadline), the entitlement records ``EXPIRED`` with a
   nonpayment cause effective at the deadline and the lineage is terminated
   with the deadline as its termination instant. ``ACCUMULATE`` never
   terminates for nonpayment.
2. **Advance assessment** while succession is due: schedule the next period
   (boundaries from anchored recurrence, never from the previous boundary),
   assess its frozen per-period premium, and attempt automatic payment. A
   failed attempt leaves the premium outstanding and still commits the
   succession and assessment.

Idempotent: a rerun finds each step already recorded (succession replays on
its command identity, assessment on its correlation, payment on its Ledger
key) and a run that finds nothing due writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.extensions import db
from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.base import requires_feat_context
from app.feats.insurance_premium_payment_feat import settle_insurance_premium
from app.feats.schedule_next_bill_cycle_feat import (
    ScheduleNextBillCycleRequest,
    schedule_next_bill_cycle,
)
from app.feats.terminate_bill_cycle_feat import TerminateBillCycleRequest, terminate_bill_cycle
from app.models import BillCycle, ObligationAssessment, Seat
from app.services import entitlement_service, obligations_service
from app.services.identity_service import resolve_teacher_seat_for_class
from app.services.insurance_coverage_service import (
    class_local_date,
    coverage_boundary,
    get_cadence_anchor,
    get_insurance_grant,
    get_terminal_event,
    premium_lineage_ref,
)
from app.services.ledger_balance_query_service import get_available_balance
from app.services.obligations_service import SuccessionEligibility
from app.services.policy_reference_service import (
    CANCEL_AFTER_X_DAYS,
    get_insurance_recurring_terms,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


NONPAYMENT_CAUSE = "NONPAYMENT"

# Evaluating a withdrawal "as of" the termination instant would treat a period
# that begins exactly at the instant as already begun (half-open periods), yet
# DOM-OBL-001 §V.7 withdraws every untouched advance premium for a period
# beginning AT OR AFTER the instant. Evaluating one microsecond (the storage
# resolution) before the instant makes "not yet begun" coincide exactly with
# "begins at or after the instant".
_INSTANT_RESOLUTION = timedelta(microseconds=1)


@dataclass
class InsuranceRenewalResult:
    """What one renewal run did for one entitlement."""
    entitlement_id: str
    cycles_scheduled: list[int] = field(default_factory=list)  # cycle numbers
    premiums_assessed: list[str] = field(default_factory=list)  # correlation ids
    premiums_autopaid: list[str] = field(default_factory=list)
    premiums_left_outstanding: list[str] = field(default_factory=list)
    terminated_for_nonpayment: bool = False
    nonpayment_deadline: datetime | None = None
    skipped_reason: str | None = None

    @property
    def wrote_anything(self) -> bool:
        return bool(self.cycles_scheduled or self.terminated_for_nonpayment)


def premium_correlation_id(entitlement_id: str, cycle_number: int) -> str:
    """Correlation of one renewal premium: one liability per period (§VII.1)."""
    return f"insurance-premium:{entitlement_id}:{cycle_number}"


def succession_command_identity(entitlement_id: str, cycle_number: int) -> str:
    """Command identity for succeeding the lineage into ``cycle_number``.

    The scheduled occurrence is the identity: every retry of the same period's
    succession is the same command and replays, never a later successor.
    """
    return f"insurance-premium:{entitlement_id}:cycle:{cycle_number}"


def _ctx(class_id: str) -> SimpleNamespace:
    return SimpleNamespace(class_id=class_id)


def _reference_now(class_id: str, reference_time_utc: datetime | None) -> datetime:
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc


def _reached(class_id: str, instant: datetime, reference: datetime) -> bool:
    """Whether ``instant`` is at or before ``reference`` (canonical evaluation)."""
    return not canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="later_than",
        reference_time_utc=reference,
        candidate=instant,
        reference=reference,
    ).is_later


def _add_class_local_days(class_id: str, instant: datetime, days: int) -> datetime:
    """``instant`` moved ``days`` class-local calendar days, keeping its local time.

    Coverage boundaries are class-local midnight, so for them this is the start
    of the class-local day ``days`` after the boundary's date.
    """
    ctx = _ctx(class_id)
    local_day = class_local_date(class_id, instant)
    day_start = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        evaluation_date=local_day,
    ).boundary_start_utc
    offset = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="time_since",
        reference_time_utc=ensure_utc(instant),
        start=day_start,
    ).elapsed_seconds
    target_start = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        evaluation_date=local_day + timedelta(days=days),
    ).boundary_start_utc
    if not offset:
        return target_start
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="shift_timestamp",
        timestamp=target_start,
        elapsed_seconds=offset,
    ).shifted_timestamp_utc


def _lineage_premiums(class_id: str, internal_ref: str) -> list[ObligationAssessment]:
    """The lineage's premium assessments (one per period), oldest period first."""
    return (
        db.session.query(ObligationAssessment)
        .join(BillCycle, BillCycle.id == ObligationAssessment.bill_cycle_id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.internal_ref == internal_ref,
            ObligationAssessment.event_type == "ASSESSMENT",
            ObligationAssessment.obligation_type == "INSURANCE_PREMIUM",
        )
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def find_nonpayment_deadline(
    class_id: str,
    entitlement_id: str,
    *,
    cancel_after_days: int,
    reference_time_utc: datetime,
) -> datetime | None:
    """The reached nonpayment deadline of a ``CANCEL_AFTER_X_DAYS`` lineage, if any.

    For the earliest premium that lapsed unpaid — due at its coverage boundary
    and still unsatisfied, as of ``boundary + cancel_after_days`` class-local
    days, by facts recorded at or before that deadline — returns the deadline
    once the reference time has reached it. Later assessments do not reset it:
    premiums are examined oldest period first, and a premium satisfied before
    its own deadline is no longer the earliest outstanding one. A withdrawn
    premium never became owed and never lapses.
    """
    internal_ref = premium_lineage_ref(entitlement_id)
    for assessment in _lineage_premiums(class_id, internal_ref):
        due_at = obligations_service.resolve_assessment_due_at(assessment)
        if due_at is None or not _reached(class_id, due_at, reference_time_utc):
            # Not yet due; later periods are later still.
            return None
        deadline = _add_class_local_days(class_id, ensure_utc(due_at), cancel_after_days)
        state_at_deadline = obligations_service.get_obligation_state(
            assessment.correlation_id, as_of=deadline
        )
        if state_at_deadline is None or not state_at_deadline.is_outstanding:
            continue  # satisfied (or withdrawn) before its deadline
        if _reached(class_id, deadline, reference_time_utc):
            return deadline
        return None  # the earliest outstanding premium's deadline is still ahead
    return None


def _terminate_for_nonpayment(
    *,
    class_id: str,
    entitlement_id: str,
    grant,
    policy_uuid: str,
    deadline: datetime,
) -> None:
    """FEAT-STOR-007 §VII: EXPIRED effective at the deadline + lineage terminated there."""
    entitlement_service.expire_entitlement(
        entitlement_id=entitlement_id,
        class_id=class_id,
        target_seat_id=grant.target_seat_id,
        actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
        product_id=grant.product_id,
        entitlement_type="INSURANCE",
        acquisition_type=grant.acquisition_type,
        correlation_id=f"insurance-nonpayment:{entitlement_id}",
        payload={
            "source": "FEAT-STOR-007",
            "cause": NONPAYMENT_CAUSE,
            "policy_uuid": policy_uuid,
            "deadline": ensure_utc(deadline).isoformat(),
        },
        effective_at=deadline,
    )
    # Terminated with the deadline as its instant. Withdrawal is evaluated as of
    # the deadline — not as of the (possibly late) run — so a period that began
    # after the deadline only because the job ran late is still withdrawn; see
    # _INSTANT_RESOLUTION for the one-microsecond evaluation point.
    terminate_bill_cycle(
        TerminateBillCycleRequest(
            class_id=class_id,
            internal_ref=premium_lineage_ref(entitlement_id),
            termination_at=deadline,
            reference_time_utc=deadline - _INSTANT_RESOLUTION,
        ),
        context=None,
    )


def _attempt_autopay(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    cycle_number: int,
    correlation_id: str,
) -> bool:
    """Pay a freshly assessed premium in full from available funds, or leave it outstanding."""
    state = obligations_service.get_obligation_state(correlation_id)
    if state is None or not state.is_payable:
        return state is not None and state.is_satisfied
    amount = state.remaining_amount
    if amount <= Decimal("0.00"):
        return True
    if get_available_balance(seat_id, class_id, "checking") < amount:
        return False
    settle_insurance_premium(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=correlation_id,
        amount=amount,
        ledger_idempotency_key=f"insurance-premium:{entitlement_id}:{cycle_number}:autopay",
        description=f"Insurance premium autopay (cycle {cycle_number})",
        mechanism="system",
        actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
    )
    return True


def renew_insurance_coverage(
    *,
    class_id: str,
    entitlement_id: str,
    reference_time_utc: datetime | None = None,
) -> InsuranceRenewalResult:
    """Bring one insurance entitlement's premium lineage up to the reference time.

    Domain orchestration composed inside the caller's FEAT-STOR-007 context.
    """
    result = InsuranceRenewalResult(entitlement_id=entitlement_id)
    reference = _reference_now(class_id, reference_time_utc)

    grant = get_insurance_grant(class_id, entitlement_id)
    if grant is None:
        result.skipped_reason = "NOT_GRANTED"
        return result
    if get_terminal_event(class_id, entitlement_id) is not None:
        result.skipped_reason = "TERMINATED"  # nonpayment expiry is not repeated
        return result

    internal_ref = premium_lineage_ref(entitlement_id)
    anchor = get_cadence_anchor(class_id, entitlement_id)
    if anchor is None:
        result.skipped_reason = "NO_LINEAGE"
        return result

    # The seat row serializes this seat's money (INV-LED-015) for autopay.
    seat = (
        Seat.query.filter_by(id=grant.target_seat_id, class_id=class_id)
        .with_for_update()
        .first()
    )
    if seat is None:
        result.skipped_reason = "NO_SEAT"
        return result

    while True:
        eligibility, latest = obligations_service.get_succession_eligibility(
            class_id, internal_ref, reference_time_utc=reference
        )
        if eligibility is SuccessionEligibility.TERMINAL:
            result.skipped_reason = result.skipped_reason or "TERMINATED"
            return result
        if latest is None:
            result.skipped_reason = "NO_LINEAGE"
            return result

        # Terms resolve from the exact version the lineage's cycles carry, never
        # the family's current row (DOM-POL-001A §V.E).
        terms = get_insurance_recurring_terms(latest.policy_uuid, class_id=class_id)

        # (1) Nonpayment first. §V continues until the deadline, so it is
        #     re-examined before every succession.
        if terms.nonpayment_mode == CANCEL_AFTER_X_DAYS:
            deadline = find_nonpayment_deadline(
                class_id, entitlement_id,
                cancel_after_days=terms.cancel_after_days,
                reference_time_utc=reference,
            )
            if deadline is not None:
                _terminate_for_nonpayment(
                    class_id=class_id,
                    entitlement_id=entitlement_id,
                    grant=grant,
                    policy_uuid=latest.policy_uuid,
                    deadline=deadline,
                )
                result.terminated_for_nonpayment = True
                result.nonpayment_deadline = deadline
                return result

        if eligibility is not SuccessionEligibility.DUE:
            return result  # the next assessment point is still ahead

        # (2) Advance assessment of the next period.
        cycle_number = latest.cycle_number + 1
        start = coverage_boundary(
            class_id, anchor_date=anchor,
            charge_frequency=terms.charge_frequency, index=cycle_number - 1,
        )
        end = coverage_boundary(
            class_id, anchor_date=anchor,
            charge_frequency=terms.charge_frequency, index=cycle_number,
        )
        cycle = schedule_next_bill_cycle(
            ScheduleNextBillCycleRequest(
                class_id=class_id,
                internal_ref=internal_ref,
                cycle_boundary_at=start,
                next_assessment_at=end,
                idempotency_key=succession_command_identity(entitlement_id, cycle_number),
                policy_uuid=latest.policy_uuid,
                reference_time_utc=reference,
            ),
            context=None,
        )
        correlation_id = premium_correlation_id(entitlement_id, cycle.cycle_number)
        assess_obligation(
            AssessmentRequest(
                seat_id=grant.target_seat_id,
                class_id=class_id,
                internal_ref=internal_ref,
                correlation_id=correlation_id,
                obligation_type="INSURANCE_PREMIUM",
                policy_uuid=cycle.policy_uuid,
                bill_cycle_id=cycle.id,
            ),
            context=None,
        )
        result.cycles_scheduled.append(cycle.cycle_number)
        result.premiums_assessed.append(correlation_id)

        # (3) Automatic payment; a failed attempt is an expected outcome.
        if _attempt_autopay(
            class_id=class_id,
            seat_id=grant.target_seat_id,
            entitlement_id=entitlement_id,
            cycle_number=cycle.cycle_number,
            correlation_id=correlation_id,
        ):
            result.premiums_autopaid.append(correlation_id)
        else:
            result.premiums_left_outstanding.append(correlation_id)


@requires_feat_context("FEAT-STOR-007")
def execute_insurance_coverage_renewal(
    *,
    class_id: str,
    entitlement_id: str,
    reference_time_utc: datetime | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
) -> InsuranceRenewalResult:
    """FEAT-STOR-007 executor for one insurance entitlement (one atomic unit)."""
    return renew_insurance_coverage(
        class_id=class_id,
        entitlement_id=entitlement_id,
        reference_time_utc=reference_time_utc,
    )


def list_renewable_insurance_entitlements(class_id: str | None = None) -> list[tuple[str, str]]:
    """``(class_id, entitlement_id)`` of every insurance entitlement with no terminal event.

    The renewal job's work list. Read-only; the FEAT re-checks each one.
    """
    from app.models import EntitlementEvent

    terminal = (
        db.session.query(EntitlementEvent.entitlement_id)
        .filter(EntitlementEvent.event_type.in_(["EXPIRED", "REVOKED"]))
        .subquery()
    )
    query = (
        db.session.query(EntitlementEvent.class_id, EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.entitlement_type == "INSURANCE",
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.entitlement_id.notin_(db.session.query(terminal.c.entitlement_id)),
        )
    )
    if class_id is not None:
        query = query.filter(EntitlementEvent.class_id == class_id)
    return [
        (row.class_id, row.entitlement_id)
        for row in query.order_by(EntitlementEvent.class_id.asc(), EntitlementEvent.entitlement_id.asc())
    ]
