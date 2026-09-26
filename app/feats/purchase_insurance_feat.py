"""
FEAT-OBL-004: Insurance Policy Purchase / Enrollment.

A student enters into (purchases) an insurance policy for the current class. The
user action is creating and immediately satisfying the FIRST premium obligation;
the INSURANCE entitlement grant is the consequence of successful satisfaction, not
the defining act — which is why this lives in the Obligations family, not Store.

Atomic success contract (one FEAT transaction; failure anywhere before commit
rolls back ALL of it, including the Ledger effect):

    resolve policy_uuid under class_id
      -> verify IN_USE and lawful recurring terms (DOM-POL-001A §V.E)
      -> reject same-policy concurrent coverage (POLICY_ALREADY_HELD)
      -> grant INSURANCE / PURCHASE entitlement (references policy_uuid; no snapshot)
      -> cycle 1 of the premium lineage ``insurance:{entitlement_id}`` through
         bill-cycle succession: [purchase instant, anchored boundary 1)
      -> assess INSURANCE_PREMIUM for cycle 1
      -> satisfy it through the lawful Ledger path
      -> commit

The premium lineage derives from the entitlement alone, never from this
command's idempotency key (DOM-OBL-001 §II.B), so a repurchase is a new
entitlement and a new lineage. Cycle 1 begins at the purchase instant — never
backdated to midnight — and its end is anchored boundary 1 of the purchase's
class-local date (FEAT-STOR-007 §IV). Later periods are scheduled by the
coverage-renewal FEAT (FEAT-STOR-007).

policy_uuid IS the frozen contract: insurance_policies rows are immutable, so every
fact written here (assessment, entitlement, bill cycle) merely carries policy_uuid
and terms are retrieved later by resolving it. No terms are snapshotted.

Idempotency is COMMAND-owned. correlation_id embeds the idempotency_key, so a
replay of the SAME command is detected and returns the original result, while a
DIFFERENT command that finds active coverage for the same policy is rejected with
POLICY_ALREADY_HELD.

See docs/FEATURE-EXECUTION/FEAT-OBL-004_INSURANCE_POLICY_PURCHASE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.extensions import db
from app.models import Seat, EntitlementEvent
from app.services import insurance_definition_service as insurance_defs
from app.services.insurance_coverage_service import (
    class_local_date,
    coverage_boundary,
    premium_lineage_ref,
)
from app.services.ledger_balance_query_service import get_available_balance
from app.services.policy_reference_service import get_insurance_recurring_terms
from app.services import entitlement_service
from app.services import entitlement_read_service
from app.services.context_resolver import CanonicalContext
from app.feats.base import requires_feat_context, FEATContext
# Obligations DOMAIN commands (plain functions), invoked within THIS FEAT's single
# context. Never the execute_* FEAT wrappers: a FEAT composes domain commands, not
# other FEATs (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2, INV-ARC-006).
from app.feats.schedule_next_bill_cycle_feat import (
    ScheduleNextBillCycleRequest,
    schedule_next_bill_cycle,
)
from app.feats.assess_obligation_feat import assess_obligation, AssessmentRequest
from app.feats.insurance_premium_payment_feat import settle_insurance_premium
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
)


@dataclass
class InsurancePurchaseResult:
    """Outcome of an insurance purchase (identity-blind, replay-safe)."""
    success: bool = False
    correlation_id: str | None = None
    entitlement_id: str | None = None
    transaction_id: int | None = None
    bill_cycle_id: int | None = None
    premium_charged: Decimal = Decimal("0.00")
    already_enrolled: bool = False  # this exact command already succeeded (idempotent replay)
    error_code: str | None = None
    error_message: str | None = None


@requires_feat_context("FEAT-OBL-004")
def execute_purchase_insurance(
    *,
    canonical_context: CanonicalContext,
    policy_uuid: str,
    idempotency_key: str,
    reference_time_utc: datetime | None = None,
) -> InsurancePurchaseResult:
    """Purchase (enroll in) an insurance policy for the acting student seat.

    Student self-purchase only: actor_seat_id == target_seat_id == context.seat_id.
    ``reference_time_utc`` is execution context (the canonically resolved
    purchase instant); omitted, the canonical current time.
    """
    if not policy_uuid:
        raise ValueError("execute_purchase_insurance requires a policy_uuid")
    if not idempotency_key:
        raise ValueError("execute_purchase_insurance requires an idempotency_key")

    class_id = canonical_context.class_id
    seat_id = canonical_context.seat_id
    if not class_id or not seat_id:
        return InsurancePurchaseResult(
            success=False, error_code="INVALID_CONTEXT",
            error_message="Canonical context lacks class_id/seat_id",
        )

    # One correlation ties the whole acquisition (assessment + payment + grant)
    # and embeds the command key so a same-command replay is detectable.
    correlation_id = f"insurance-purchase:{idempotency_key}"

    # ----- Phase 1: read-only validation ----------------------------------- #

    # The seat row serializes this seat's money (INV-LED-015). It is taken first,
    # before even the replay lookup: a same-key retry that waited here must see
    # the grant its predecessor committed, or it would fall through to the
    # coverage check and report POLICY_ALREADY_HELD for its own purchase. Held
    # through the premium debit, it also keeps concurrent purchases, debits and
    # settlement for this seat from passing the same balance check.
    seat = (
        Seat.query.filter_by(id=seat_id, class_id=class_id)
        .with_for_update()
        .first()
    )
    if seat is None:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_SEAT", error_message="Seat not found in class scope",
        )

    # (0) Idempotent replay: this exact command already produced a grant.
    prior_grant = (
        EntitlementEvent.query
        .filter_by(
            class_id=class_id,
            target_seat_id=seat_id,
            entitlement_type="INSURANCE",
            event_type="GRANTED",
            correlation_id=correlation_id,
        )
        .first()
    )
    if prior_grant is not None:
        return InsurancePurchaseResult(
            success=True, already_enrolled=True,
            correlation_id=correlation_id,
            entitlement_id=prior_grant.entitlement_id,
        )

    definition = insurance_defs.get_insurance_definition(policy_uuid, class_id=class_id)
    if definition is None:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="POLICY_NOT_FOUND",
            error_message=f"Insurance policy {policy_uuid} not found in class {class_id}",
        )
    if definition.availability_state != insurance_defs.IN_USE:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INSURANCE_NOT_AVAILABLE_FOR_NEW_COVERAGE",
            error_message=(
                f"Insurance policy {policy_uuid} is not available for new coverage "
                f"(state={definition.availability_state})"
            ),
        )

    premium = Decimal(str(definition.premium))
    if premium <= Decimal("0.00"):
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INVALID_PREMIUM",
            error_message="Insurance premium resolves to a non-positive amount",
        )

    # Hard invariant: no second concurrently effective grant for the same policy.
    if entitlement_read_service.has_active_insurance_coverage(seat_id, class_id, policy_uuid):
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="POLICY_ALREADY_HELD",
            error_message="Seat already holds active coverage for this policy",
        )

    # Tier-group mutual exclusion: at most one active coverage per tier_group
    # (FEAT-CLASS-003 §VIII.3). A student who holds Basic cannot also buy Mid/Premium
    # of the same group without cancelling first. Ungrouped policies are exempt.
    if definition.tier_group and entitlement_read_service.has_active_coverage_in_group(
        seat_id, class_id, definition.tier_group
    ):
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="POLICY_ALREADY_HELD_IN_GROUP",
            error_message=(
                f"Seat already holds active coverage in tier group "
                f"'{definition.tier_group}'"
            ),
        )

    # Affordability: the first premium must be payable now (no overdraft here).
    available = get_available_balance(seat_id, class_id, "checking")
    if available < premium:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INSUFFICIENT_FUNDS",
            error_message=f"Checking balance {available} < premium {premium}",
        )

    # Resolve the recurring terms and cycle 1's boundaries in the read phase: a
    # policy version without lawful recurring terms aborts BEFORE any mutation.
    try:
        terms = get_insurance_recurring_terms(policy_uuid, class_id=class_id)
    except ValueError as exc:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INVALID_RECURRING_TERMS", error_message=str(exc),
        )
    now_utc = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc
    # The purchase's class-local date anchors the cadence (FEAT-STOR-007 §IV).
    anchor_date = class_local_date(class_id, now_utc)
    next_assessment_at = coverage_boundary(
        class_id, anchor_date=anchor_date,
        charge_frequency=terms.charge_frequency, index=1,
    )

    # ----- Phase 2: mutation (single atomic FEAT transaction) --------------- #

    # Every mutation below is a DOMAIN command invoked inside THIS single FEAT
    # context — no nested FEAT executor is called (INV-ARC-000 / -021 / -006).

    # (a) Grant the INSURANCE coverage entitlement first: its id is the premium
    #     lineage (DOM-OBL-001 §II.B). The grant is stamped with the purchase
    #     instant, where the first coverage period begins.
    entitlement_id = entitlement_service.grant_insurance_entitlement(
        seat,
        policy_uuid,
        actor_seat_id=seat_id,
        correlation_id=correlation_id,
        granted_at=now_utc,
    )
    internal_ref = premium_lineage_ref(entitlement_id)

    # (b) Cycle 1 through bill-cycle succession of the empty lineage. Its period
    #     is [purchase instant, anchored boundary 1); it is not backdated.
    cycle = schedule_next_bill_cycle(
        ScheduleNextBillCycleRequest(
            class_id=class_id,
            internal_ref=internal_ref,
            cycle_boundary_at=now_utc,
            next_assessment_at=next_assessment_at,
            idempotency_key=f"insurance-premium:{entitlement_id}:cycle:1",
            policy_uuid=policy_uuid,
            reference_time_utc=now_utc,
        ),
        context=None,
    )

    # (c) Assess premium #1 against cycle 1 (due at the purchase instant).
    assess_obligation(
        AssessmentRequest(
            seat_id=seat_id,
            class_id=class_id,
            internal_ref=internal_ref,
            correlation_id=correlation_id,
            obligation_type="INSURANCE_PREMIUM",
            policy_uuid=policy_uuid,
            bill_cycle_id=cycle.id,
        ),
        context=None,
    )

    # (d) Pay it through the lawful Ledger + satisfaction path.
    transaction = settle_insurance_premium(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=correlation_id,
        amount=premium,
        ledger_idempotency_key=f"insurance-premium:{idempotency_key}:cycle1",
        description=f"Insurance premium (policy {policy_uuid}, cycle 1)",
    )

    return InsurancePurchaseResult(
        success=True,
        correlation_id=correlation_id,
        entitlement_id=entitlement_id,
        transaction_id=transaction.id,
        bill_cycle_id=cycle.id,
        premium_charged=premium,
    )
