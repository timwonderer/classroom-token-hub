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
2. **Superseded or withdrawn version** (§V.A), once succession is due: a
   version superseded by an edit continues under its latest successor on sale
   through a new entitlement starting at the boundary; a version no longer on
   sale with no successor on sale stops renewing, so coverage ends there.
3. **Advance assessment** while succession is due: schedule the next period
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
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.extensions import db
from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.base import requires_feat_context
from app.feats.insurance_premium_payment_feat import premium_is_affordable, settle_insurance_premium
from app.feats.schedule_next_bill_cycle_feat import (
    ScheduleNextBillCycleRequest,
    schedule_next_bill_cycle,
)
from app.feats.terminate_bill_cycle_feat import TerminateBillCycleRequest, terminate_bill_cycle
from app.models import BillCycle, ObligationAssessment, Seat
from app.services import entitlement_service, obligations_service
from app.services import insurance_definition_service as insurance_defs
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
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


NONPAYMENT_CAUSE = "NONPAYMENT"


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
    renewal_stopped_at: datetime | None = None  # §V.A: superseded or withdrawn version
    continued_as: "InsuranceRenewalResult | None" = None  # the continuing entitlement's run
    skipped_reason: str | None = None

    @property
    def wrote_anything(self) -> bool:
        return bool(
            self.cycles_scheduled or self.terminated_for_nonpayment or self.renewal_stopped_at
        )


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
        if due_at is None or canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="later_than",
            candidate=due_at, reference=reference_time_utc,
        ).is_later:
            # Not yet due; later periods are later still.
            return None
        # The due instant moved cancel_after_days class-local calendar days, keeping its local time.
        deadline = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=_ctx(class_id),
            primitive="shift_calendar_days",
            timestamp=due_at,
            days=cancel_after_days,
        ).shifted_timestamp_utc
        state_at_deadline = obligations_service.get_obligation_state(
            assessment.correlation_id, as_of=deadline
        )
        if state_at_deadline is None or not state_at_deadline.is_outstanding:
            continue  # satisfied (or withdrawn) before its deadline
        if not canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="later_than",
            candidate=deadline, reference=reference_time_utc,
        ).is_later:
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
            "deadline": deadline.isoformat(),
        },
        effective_at=deadline,
    )
    # Terminated with the deadline as its instant. Withdrawal is evaluated as of
    # the deadline — not as of the (possibly late) run — so a period that began
    # after the deadline only because the job ran late is still withdrawn, and a
    # period beginning exactly at the deadline is prevented, not begun
    # (withdraw_assessment, DOM-OBL-001 §IX.15).
    terminate_bill_cycle(
        TerminateBillCycleRequest(
            class_id=class_id,
            internal_ref=premium_lineage_ref(entitlement_id),
            termination_at=deadline,
            reference_time_utc=deadline,
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
    # The same affordability rule as a manual payment and the purchase's first
    # premium (DOM-OBL-001 §II.C); a premium that cannot be covered stays owed.
    if not premium_is_affordable(
        class_id=class_id,
        seat_id=seat_id,
        amount=amount,
        description="Automatic insurance premium",
        mechanism="system",
        actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
    ):
        return False
    settle_insurance_premium(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=correlation_id,
        amount=amount,
        ledger_idempotency_key=f"insurance-premium:{entitlement_id}:{cycle_number}:autopay",
        mechanism="system",
        actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
    )
    return True


def continuation_correlation_id(entitlement_id: str) -> str:
    """Correlation of the grant continuing ``entitlement_id`` (one per entitlement)."""
    return f"insurance-continuation:{entitlement_id}"


def _stop_renewal(class_id: str, entitlement_id: str, reference: datetime) -> datetime:
    """End the lineage at the end of its last committed period; return that instant.

    The same Obligations command a student's cancellation uses, so the same
    committed-period and withdrawal rules apply (DOM-STORE-001 §VIII.E.1).
    """
    terminal = terminate_bill_cycle(
        TerminateBillCycleRequest(
            class_id=class_id,
            internal_ref=premium_lineage_ref(entitlement_id),
            reference_time_utc=reference,
        ),
        context=None,
    )
    return terminal.cycle_boundary_at


def _continue_under_successor(
    *,
    class_id: str,
    entitlement_id: str,
    seat: Seat,
    successor,
    boundary: datetime,
    reference: datetime,
) -> str:
    """FEAT-STOR-007 §V.A continuation: a new entitlement under ``successor`` from ``boundary``.

    Its lineage is anchored at the boundary's class-local date, and its first
    premium is an advance premium due at the boundary, attempted at once.
    """
    new_id = entitlement_service.grant_insurance_entitlement(
        seat,
        successor.policy_uuid,
        actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
        correlation_id=continuation_correlation_id(entitlement_id),
        granted_at=boundary,
        continues_entitlement_id=entitlement_id,
    )
    terms = get_insurance_recurring_terms(successor.policy_uuid, class_id=class_id)
    internal_ref = premium_lineage_ref(new_id)
    cycle = schedule_next_bill_cycle(
        ScheduleNextBillCycleRequest(
            class_id=class_id,
            internal_ref=internal_ref,
            cycle_boundary_at=boundary,
            next_assessment_at=coverage_boundary(
                class_id,
                anchor_date=class_local_date(class_id, boundary),
                charge_frequency=terms.charge_frequency,
                index=1,
            ),
            idempotency_key=succession_command_identity(new_id, 1),
            policy_uuid=successor.policy_uuid,
            reference_time_utc=reference,
        ),
        context=None,
    )
    correlation_id = premium_correlation_id(new_id, 1)
    assess_obligation(
        AssessmentRequest(
            seat_id=seat.id,
            class_id=class_id,
            internal_ref=internal_ref,
            correlation_id=correlation_id,
            obligation_type="INSURANCE_PREMIUM",
            policy_uuid=successor.policy_uuid,
            bill_cycle_id=cycle.id,
        ),
        context=None,
    )
    _attempt_autopay(
        class_id=class_id,
        seat_id=seat.id,
        entitlement_id=new_id,
        cycle_number=1,
        correlation_id=correlation_id,
    )
    return new_id


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
    reference = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc

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

        # (2) §V.A: a superseded or withdrawn version does not renew. The
        #     existing entitlement keeps its version to the end (DOM-POL-001 §VII).
        version = insurance_defs.get_insurance_definition(latest.policy_uuid, class_id=class_id)
        successor = insurance_defs.get_latest_successor(latest.policy_uuid, class_id=class_id)
        if successor is not None and successor.availability_state == insurance_defs.IN_USE:
            boundary = _stop_renewal(class_id, entitlement_id, reference)
            result.renewal_stopped_at = boundary
            new_id = _continue_under_successor(
                class_id=class_id,
                entitlement_id=entitlement_id,
                seat=seat,
                successor=successor,
                boundary=boundary,
                reference=reference,
            )
            # A late run catches the continuing lineage up in the same unit.
            result.continued_as = renew_insurance_coverage(
                class_id=class_id, entitlement_id=new_id, reference_time_utc=reference
            )
            return result
        if version is None or version.availability_state != insurance_defs.IN_USE:
            result.renewal_stopped_at = _stop_renewal(class_id, entitlement_id, reference)
            return result

        # (3) Advance assessment of the next period.
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

        # (4) Automatic payment; a failed attempt is an expected outcome.
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
