"""
FEAT-OBL-002: Scheduled Rent Cycle — canonical rent reconciliation.

This is the SINGLE mechanism that materializes the recurring rent lifecycle for a
class. It is idempotent and safe to run repeatedly (on a schedule or on demand):

  - While Obligations reports the ``rent:{class_id}`` lineage eligible for
    succession (empty, or its current cycle's ``next_assessment_at`` reached),
    request the next cycle through ``schedule_next_bill_cycle`` (DOM-OBL-001
    §V.7); for every successor after cycle 1, expire the PRIOR cycle's PERK hall
    passes at the rent boundary (DOM-OBL-001 §IX.9 / DOM-STORE-001 §VIII.6).
  - Every run, regardless of the above: assess one RENT ASSESSMENT per claimed,
    non-exempt student seat against whichever cycle is now current. A cycle's
    frozen ``policy_uuid`` fixes its TERMS (amount, cadence, penalty, due
    dates) only — never its roster. A seat claimed after the cycle's first
    assessment pass is picked up here on the very next reconciliation, always
    against the CURRENT cycle, never retroactively against one that already
    advanced past before the seat was claimed. Idempotent per (seat, cycle),
    so a roster with nothing new to assess costs nothing extra.
  - Runs before the boundary with no roster change, or for a disabled class,
    are no-ops.

Layering (INV-ARC-006 / INV-ARC-021): reconciliation is a FEAT orchestrator. It
reads schedule INTENT from RentSettings, resolves concrete instants through the
Rent schedule producer, and drives the Obligations domain (via the assess and
bill-cycle succession commands) and the Store domain (via entitlement expiry). Each domain
still owns its own mutation; the FEAT only coordinates them under one transaction.

Lineage conventions (greenfield):
  - bill cycle:  internal_ref = "rent:{class_id}", cycle_number = 1, 2, 3, …
  - assessment:  internal_ref = "rent:{class_id}:{seat_id}",
                 correlation_id = "rent:{class_id}:{seat_id}:cycle:{cycle_number}"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.models import RentSettings, Seat
from app.services import obligations_service
from app.services import rent_schedule_service
from app.services import entitlement_service
from app.services.identity_service import resolve_teacher_seat_for_class
from app.services.class_configuration_query_service import get_rent_settings, is_feature_enabled
from app.feats.base import requires_feat_context, FEATContext
# Obligations DOMAIN commands (plain functions), invoked within THIS FEAT's single
# context — never the execute_* FEAT wrappers (INV-ARC-000 / -021 / -006).
from app.feats.assess_obligation_feat import assess_obligation, AssessmentRequest
from app.feats.schedule_next_bill_cycle_feat import (
    schedule_next_bill_cycle, ScheduleNextBillCycleRequest,
)
from app.services.obligations_service import SuccessionEligibility
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now


# Safety bound on catch-up: never materialize more than this many cycles in one
# reconciliation run (guards against a mis-configured tiny frequency looping).
_MAX_CATCHUP_CYCLES = 120

# Safety bound on recurring late-fee accrual: never materialize more than this
# many late-fee periods for a single delinquent rent obligation in one run
# (guards against a mis-configured tiny late_penalty_frequency_days looping).
_MAX_LATE_FEE_PERIODS = 60


@dataclass
class ReconcileRentRequest:
    """Input contract for rent reconciliation."""
    class_id: str
    reference_time_utc: datetime | None = None  # 'now'; defaults to system UTC
    idempotency_key: str | None = None  # names this run; defaults to class + reference instant


@dataclass
class ReconcileRentResult:
    """Outcome summary (identity-blind counts + created cycle numbers)."""
    reason: str
    cycles_created: list[int] = field(default_factory=list)
    assessments_created: int = 0
    perks_expired: int = 0
    late_fees_created: int = 0


def _rent_roster(class_id: str) -> list[Seat]:
    """Claimed, non-exempt student seats owing rent in this class."""
    return (
        Seat.query.filter(
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
            Seat.has_received_rent_exemption.isnot(True),
        )
        .order_by(Seat.id.asc())
        .all()
    )


def _assess_cycle(settings: RentSettings, class_id: str, cycle) -> int:
    """Create one RENT ASSESSMENT per roster seat for ``cycle``. Idempotent."""
    created = 0
    for seat in _rent_roster(class_id):
        internal_ref = f"rent:{class_id}:{seat.id}"
        correlation_id = f"rent:{class_id}:{seat.id}:cycle:{cycle.cycle_number}"
        before = obligations_service.check_idempotency_assessment(internal_ref, correlation_id)
        assess_obligation(
            AssessmentRequest(
                seat_id=seat.id,
                class_id=class_id,
                internal_ref=internal_ref,
                correlation_id=correlation_id,
                obligation_type="RENT",
                policy_uuid=settings.policy_uuid,
                bill_cycle_id=cycle.id,
            ),
            context=None,
        )
        if not before:
            created += 1
    return created


def _expire_prior_cycle_perks(class_id: str, prior_cycle, actor_seat_id: int) -> int:
    """Expire every PERK entitlement granted under the prior cycle's assessments."""
    expired = 0
    prior_assessments = obligations_service.get_assessments_for_bill_cycle(
        prior_cycle.id, obligation_type="RENT"
    )
    for assessment in prior_assessments:
        expired += entitlement_service.expire_rent_perks(
            correlation_id=assessment.correlation_id,
            class_id=class_id,
            actor_seat_id=actor_seat_id,
        )
    return expired


def _late_fee_periods_elapsed(settings: RentSettings, grace_boundary_at, now) -> int:
    """How many late-fee periods a delinquent obligation has accrued by ``now``.

    - ``once``: exactly one flat penalty the moment grace lapses.
    - ``recurring``: one penalty per elapsed ``late_penalty_frequency_days``
      window since the grace boundary (the first the moment grace lapses, then
      one per full window thereafter), capped by ``_MAX_LATE_FEE_PERIODS``.

    The count is DERIVED from elapsed time, never by counting prior late-fee
    events — so it cannot race and is stable across reconciliation replays.
    """
    penalty_type = (settings.late_penalty_type or 'once').strip().lower()
    if penalty_type != 'recurring':
        return 1
    freq_days = settings.late_penalty_frequency_days
    if not freq_days or freq_days <= 0:
        # Recurring configured without a valid cadence → degrade to a single fee.
        return 1
    elapsed_days = (ensure_utc(now) - ensure_utc(grace_boundary_at)).days
    if elapsed_days < 0:
        return 0
    periods = (elapsed_days // int(freq_days)) + 1
    return min(periods, _MAX_LATE_FEE_PERIODS)


def _assess_late_fees(settings: RentSettings, class_id: str, cycle, now) -> int:
    """Assess LATE_FEE obligations for delinquent rent in ``cycle``. Idempotent.

    A late fee is its OWN immutable obligation with its OWN correlation. It is
    linked to the rent obligation it AROSE FROM through the lawful, persisted
    ``source_correlation_id`` reference — never by parsing a derived string.

    Preconditions for any fee to accrue on a seat's rent obligation:
      - the class configures a positive ``late_penalty_amount`` (the enable
        signal, matching v1 where amount > 0 turned penalties on);
      - the cycle's persisted ``grace_boundary_at`` has lapsed by ``now``;
      - the seat's rent obligation for this cycle is still UNSATISFIED (once the
        rent principal is paid or waived, no further penalties accrue — already
        assessed late fees stand as their own debts).
    """
    penalty_amount = settings.late_penalty_amount
    if penalty_amount is None or Decimal(str(penalty_amount)) <= Decimal('0.00'):
        return 0
    grace_boundary_at = getattr(cycle, 'grace_boundary_at', None)
    if grace_boundary_at is None or ensure_utc(now) <= ensure_utc(grace_boundary_at):
        return 0

    periods = _late_fee_periods_elapsed(settings, grace_boundary_at, now)
    if periods <= 0:
        return 0

    created = 0
    for seat in _rent_roster(class_id):
        rent_correlation_id = f"rent:{class_id}:{seat.id}:cycle:{cycle.cycle_number}"
        rent_assessment = obligations_service.get_assessment_for_correlation(rent_correlation_id)
        if rent_assessment is None:
            continue

        # No new penalties once the rent principal is satisfied (paid or waived).
        # Satisfaction is measured against the paid MAGNITUDE (rent payments post
        # as negative debits) plus any waiver — never the raw signed ledger sum.
        assessed_amount = obligations_service.resolve_assessment_amount(rent_assessment)
        paid_magnitude = obligations_service.get_paid_magnitude(rent_correlation_id)
        waived = obligations_service.check_idempotency_satisfaction(
            rent_correlation_id, "WAIVED"
        )
        if waived or paid_magnitude >= assessed_amount:
            continue

        late_internal_ref = f"rent:{class_id}:{seat.id}:late"
        for n in range(1, periods + 1):
            late_correlation_id = f"{rent_correlation_id}:late:{n}"
            before = obligations_service.check_idempotency_assessment(
                late_internal_ref, late_correlation_id
            )
            assess_obligation(
                AssessmentRequest(
                    seat_id=seat.id,
                    class_id=class_id,
                    internal_ref=late_internal_ref,
                    correlation_id=late_correlation_id,
                    obligation_type="LATE_FEE",
                    policy_uuid=settings.policy_uuid,
                    bill_cycle_id=cycle.id,
                    source_correlation_id=rent_correlation_id,
                ),
                context=None,
            )
            if not before:
                created += 1
    return created


def reconcile_rent(
    request: ReconcileRentRequest,
    *,
    context: FEATContext,
) -> ReconcileRentResult:
    """Materialize the rent lifecycle up to ``reference_time_utc``. Idempotent."""
    class_id = request.class_id
    if not class_id:
        raise ValueError("reconcile_rent requires class_id")

    now = ensure_utc(request.reference_time_utc) if request.reference_time_utc else utc_now()

    # Class-level rent gate.
    if not is_feature_enabled(class_id, "rent"):
        return ReconcileRentResult(reason="RENT_DISABLED")

    # New cycles and new assessments are NEW work, so they take the policy
    # currently in force and freeze its `policy_uuid` onto themselves. This is the
    # mint point for the freeze: `rent_settings` is append-only, so an unordered
    # lookup here could stamp a superseded policy onto a new cycle and pin the
    # wrong amount permanently (DOM-POL-001 §VI.1, §VII).
    settings = get_rent_settings(class_id)
    if settings is None:
        return ReconcileRentResult(reason="NO_SETTINGS")

    # Lightweight resolver context: the temporal resolver only reads .class_id.
    ctx = SimpleNamespace(class_id=class_id)
    internal_ref_cycle = f"rent:{class_id}"

    result = ReconcileRentResult(reason="NOOP")

    # Command identity for each succession this run requests. A caller-supplied
    # key names the run; otherwise the run is identified by its class and the
    # reference instant it reconciles to, so a retry of the same run replays
    # rather than racing itself. Each succession step appends the cycle it was
    # evaluated against, which keeps distinct steps of one run distinct commands.
    run_identity = request.idempotency_key or f"rent-reconcile:{class_id}:{now.isoformat()}"

    # Succession, repeated while Obligations says the lineage is due. Eligibility
    # is the domain's determination (DOM-OBL-001 §V.7); this loop only asks. The
    # first cycle is not a separate command: an EMPTY lineage is succeeded to 1.
    actor_seat_id = None
    iterations = 0
    while True:
        eligibility, latest = obligations_service.get_succession_eligibility(
            class_id, internal_ref_cycle, reference_time_utc=now
        )
        if eligibility not in (SuccessionEligibility.EMPTY, SuccessionEligibility.DUE):
            break
        if latest is not None:
            iterations += 1
            if iterations > _MAX_CATCHUP_CYCLES:
                result.reason = "CATCHUP_BOUND_EXCEEDED"
                break

        if latest is None:
            due_local = rent_schedule_service.first_due_local_date(
                settings, context=ctx, reference_time_utc=now
            )
        else:
            # Successor due date is the class-local date of the resolved next_assessment_at.
            due_local = rent_schedule_service.local_date_of_instant(
                ctx, latest.next_assessment_at
            )
        schedule = rent_schedule_service.resolve_cycle_schedule(
            settings, due_local_date=due_local, context=ctx
        )
        evaluated_against = latest.cycle_number if latest is not None else 0
        new_cycle = schedule_next_bill_cycle(
            ScheduleNextBillCycleRequest(
                class_id=class_id,
                internal_ref=internal_ref_cycle,
                cycle_boundary_at=schedule.cycle_boundary_at,
                next_assessment_at=schedule.next_assessment_at,
                grace_boundary_at=schedule.grace_boundary_at,
                policy_uuid=settings.policy_uuid,
                idempotency_key=f"{run_identity}:after:{evaluated_against}",
                reference_time_utc=now,
            ),
            context=None,
        )
        result.cycles_created.append(new_cycle.cycle_number)

        if latest is None:
            result.reason = "CREATED_INITIAL"
            continue

        # Expire the prior cycle's rent PERK hall passes at the boundary.
        if actor_seat_id is None:
            actor_seat_id = resolve_teacher_seat_for_class(class_id).id
        result.perks_expired += _expire_prior_cycle_perks(class_id, latest, actor_seat_id)

        if result.reason in ("NOOP",):
            result.reason = "ADVANCED"

    # Roster assessment against the now-current cycle, uniform across genesis,
    # advancement, and plain no-op runs (operator report, 2026-09-22): the
    # frozen policy_uuid on a cycle fixes its TERMS (amount, cadence, penalty,
    # due dates) — it must not also freeze its ROSTER. A seat claimed after
    # the cycle's first assessment pass is picked up here on the very next
    # reconciliation, always against the CURRENT open cycle only; a cycle that
    # has already advanced past is never revisited for a late-claiming seat,
    # so nobody is retroactively assessed for a period before they joined.
    # `_assess_cycle` is idempotent per (seat, cycle_number), so re-running it
    # against a cycle already assessed for the rest of the roster is a no-op
    # for every seat it has already seen. If a teacher wants to give a
    # late-joiner time before their first bill, that is what a waiver is for
    # (DOM-OBL-001) -- this reconciliation must not make that call silently.
    backfilled = _assess_cycle(settings, class_id, latest)
    result.assessments_created += backfilled
    if backfilled and result.reason == "NOOP":
        result.reason = "ROSTER_BACKFILLED"

    # Late-fee accrual: assess penalties on any cycle whose grace boundary has
    # lapsed while its rent is still unsatisfied. Runs over every cycle (not just
    # the current one) so arrears from prior cycles continue to accrue penalties,
    # and is fully idempotent (each late fee has a deterministic correlation).
    for cycle in obligations_service.get_bill_cycles_for_internal_ref(internal_ref_cycle):
        result.late_fees_created += _assess_late_fees(settings, class_id, cycle, now)

    if result.late_fees_created and result.reason in ("NOOP",):
        result.reason = "LATE_FEES_ASSESSED"

    return result


@requires_feat_context("FEAT-OBL-002")
def execute_reconcile_rent(
    class_id: str,
    *,
    reference_time_utc: datetime | None = None,
    idempotency_key: str | None = None,
) -> ReconcileRentResult:
    """Public FEAT interface for rent reconciliation.

    Callable from the scheduled reconciliation path and from tests. Idempotent:
    re-running produces no duplicate cycles, assessments, or expiry events.
    """
    request = ReconcileRentRequest(
        class_id=class_id,
        reference_time_utc=reference_time_utc,
        idempotency_key=idempotency_key,
    )
    return reconcile_rent(request, context=None)
