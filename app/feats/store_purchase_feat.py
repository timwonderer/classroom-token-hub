"""
FEAT-STOR-001: Store Purchase and Entitlement Grant (v4.0)

Orchestrates the complete purchase lifecycle:
- Accepts exact policy_uuid (no discovery/inference)
- Resolves policy and validates per SPEC-STORE-001
- Validates purchase eligibility (is_purchasable, per-student limits, financial)
- Coordinates Ledger purchase resolution
- Creates immutable EntitlementEvent rows (one per unit)
- Handles instant-use coordination if applicable

All mutations (Ledger + EntitlementEvent) succeed or fail together (atomic).

Scope: actual Store products only. Insurance is NOT a store product — it is
acquired through FEAT-OBL-004 (Insurance Policy Purchase / Enrollment) over the
immutable insurance_policies definition. This FEAT rejects any INSURANCE-typed
policy that reaches it.

Contract: Caller is responsible for discovery via the resolver's policy list
primitive. This FEAT accepts exact policy_uuid and executes without inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import requires_feat_context, FEATContext, get_correlation_id
from app.feats.ledger_resolution_feat import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
    apply_resolved_ledger_plan,
)
from app.models import Seat, EntitlementEvent, ClassEconomy
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import get_current_economic_engine
from app.services.class_configuration_query_service import get_rent_settings
from app.services.obligation_view_model import build_student_obligation_view
from app.services.store_policy_resolver import StorePolicyResolver, PolicyNotFound, PolicyParseError, PolicyValidationError
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    ensure_utc,
)


class StorePurchaseError(Exception):
    """Raised when purchase validation or execution fails."""
    pass


@dataclass
class StorePurchaseResult:
    """Result of a successful store purchase."""
    success: bool
    correlation_id: str
    quantity_granted: int
    entitlement_ids: list[str] = field(default_factory=list)
    product_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def _calculate_debit(policy_config, quantity: int) -> tuple[Decimal, bool]:
    """Return (amount to charge, whether the bulk discount applied).

    The discount triggers on the number of units the student buys, at or above
    the configured threshold, and applies to the whole order rather than only
    the units past the threshold — that is what the item card promises the
    student ("Buy 5+ for 15% off"), and the quoted price and the charged price
    have to agree.

    Rounded to cents, half-up: the ledger stores 2-scale amounts, and banker's
    rounding on a price would surprise a student reading the arithmetic.
    """
    gross = policy_config.price * quantity

    threshold = policy_config.bulk_discount_quantity
    percentage = policy_config.bulk_discount_percentage
    if threshold is None or percentage is None or quantity < threshold:
        return gross, False

    multiplier = (Decimal('100') - Decimal(str(percentage))) / Decimal('100')
    discounted = (gross * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return discounted, True


def execute_store_purchase(
    *,
    canonical_context: CanonicalContext,
    policy_uuid: str,
    quantity: int,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    instant_use: bool = False,
) -> StorePurchaseResult:
    """
    Execute a lawful store purchase and create entitlement grants.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role
        policy_uuid: Exact policy UUID to resolve and execute against (no inference)
        quantity: Positive integer number of units
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard
        instant_use: If True, immediately consume granted entitlements

    Returns:
        StorePurchaseResult with success status and granted entitlements

    Contract: Caller is responsible for discovering which policy applies.
    This FEAT accepts the exact policy_uuid and resolves it without inference.
    """
    # Use decorator's idempotency generation if not provided
    return _execute_store_purchase_impl(
        canonical_context=canonical_context,
        policy_uuid=policy_uuid,
        quantity=quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        instant_use=instant_use,
    )


@requires_feat_context("FEAT-STOR-001")
def _execute_store_purchase_impl(
    *,
    canonical_context: CanonicalContext,
    policy_uuid: str,
    quantity: int,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    instant_use: bool = False,
) -> StorePurchaseResult:
    """
    Internal implementation wrapped in @requires_feat_context for context management.

    Exact resolution: accept policy_uuid and resolve without inference.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.class_id or not canonical_context.seat_id:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate target seat exists and belongs to class
    target_seat = (
        db.session.query(Seat)
        .filter(
            Seat.id == canonical_context.seat_id,
            Seat.class_id == canonical_context.class_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if not target_seat or target_seat.class_id != canonical_context.class_id:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="INVALID_CONTEXT",
            error_message="Target seat not found or not in class scope",
        )

    # Validate quantity
    if not isinstance(quantity, int) or quantity <= 0:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="QUANTITY_NOT_ALLOWED",
            error_message="Quantity must be a positive integer",
        )

    # =========================================================================
    # Resolve and validate product policy per SPEC-STORE-001
    # =========================================================================

    # Exact resolution: resolve supplied policy_uuid without inference.
    # Caller is responsible for discovering which policy applies.
    try:
        policy_config = StorePolicyResolver.resolve_store_item(policy_uuid)
    except PolicyNotFound:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_NOT_FOUND",
            error_message=f"Policy UUID {policy_uuid} not found (may have been deleted)",
        )
    except (PolicyParseError, PolicyValidationError) as e:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_INVALID",
            error_message=f"Policy validation failed: {str(e)}",
        )

    # Verify policy belongs to the canonical class scope
    if policy_config.class_id != canonical_context.class_id:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_SCOPE_MISMATCH",
            error_message=f"Policy UUID {policy_uuid} belongs to different class ({policy_config.class_id} vs {canonical_context.class_id})",
        )

    # Rent policy owns the late-purchase consequence. Resolve lateness from the
    # canonical obligation projection, and allow only products explicitly linked
    # as rent satisfaction benefits when the policy says non-covered purchases
    # are blocked. The check is server-side so a hidden/disabled UI control
    # cannot bypass the class policy.
    rent_settings = get_rent_settings(canonical_context.class_id)
    if rent_settings and rent_settings.prevent_purchase_when_late:
        rent_view = build_student_obligation_view(
            canonical_context.seat_id,
            canonical_context.class_id,
            "RENT",
        )
        current_period = rent_view.current_period if rent_view else {}
        is_late = bool(current_period.get("is_late") or current_period.get("is_past_due"))
        linked_lineages = {
            benefit.get("product_lineage_uuid")
            for benefit in rent_settings.get_satisfaction_benefit_grants()
            if benefit.get("product_lineage_uuid")
        }
        if is_late and policy_config.product_lineage_uuid not in linked_lineages:
            return StorePurchaseResult(
                success=False,
                correlation_id="",
                quantity_granted=0,
                error_code="RENT_PAST_DUE_PURCHASE_BLOCKED",
                error_message="Store purchases are blocked while rent is past due",
            )

    # Validate is_purchasable (FEAT-STOR-001 specific constraint)
    if not policy_config.is_purchasable:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="PRODUCT_NOT_PURCHASABLE",
            error_message=f"Product {policy_config.product_id} is not purchasable",
        )

    # Insurance is NOT a store product. It is acquired through FEAT-OBL-004
    # (Insurance Policy Purchase / Enrollment) over the immutable insurance_policies
    # definition — an Obligations action, not a store purchase. This FEAT is the
    # lawful writer of PURCHASE grants for actual Store products only, so reject any
    # INSURANCE-typed policy that reaches here (none should exist: publication of
    # insurance StoreProducts was removed).
    if policy_config.entitlement_type == 'INSURANCE':
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="INSURANCE_NOT_PURCHASABLE_VIA_STORE",
            error_message="Insurance is purchased via FEAT-OBL-004, not the store path",
        )

    # Immediate-use and privilege products cannot hold multiple unexercised
    # units.  Quantity greater than one is therefore not a larger purchase of
    # the same product; it would manufacture inventory the product type cannot
    # represent.  Bundles remain lawful only for types that hold independent
    # unredeemed units (DELAYED_USE and HALL_PASS).
    if policy_config.entitlement_type in {'IMMEDIATE_USE', 'PRIVILEGE'} and quantity != 1:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="QUANTITY_NOT_ALLOWED",
            error_message="Immediate-use and privilege products may only be purchased one at a time",
        )

    # A collective goal closes at its deadline. Past it the goal can no longer
    # be reached, so selling into it would take money for an outcome that cannot
    # occur. The deadline was configured, published, and displayed but never
    # consulted; this is where it binds.
    if policy_config.collective_goal_expires_at is not None:
        temporal_now = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=canonical_context,
            primitive="current_time",
        ).canonical_now_utc
        if ensure_utc(policy_config.collective_goal_expires_at) <= ensure_utc(temporal_now):
            return StorePurchaseResult(
                success=False,
                correlation_id="",
                quantity_granted=0,
                error_code="COLLECTIVE_GOAL_EXPIRED",
                error_message="This collective goal has passed its deadline and is closed to new purchases",
            )

    # A bundle grants several units for one purchase. DOM-STORE-001 forbids
    # persisting `bundle_remaining` or any other mutable balance (§lines 70,
    # 137, 430), so a bundle is not one entitlement with a counter — it is N
    # independent entitlement lifecycles, which is exactly what FEAT-STOR-001
    # §VII.E already requires ("each purchased unit creates one entitlement
    # lifecycle"). Buying is priced per bundle; granting is per unit.
    units_per_purchase = policy_config.bundle_quantity or 1
    units_to_grant = quantity * units_per_purchase

    # Validate per-student limit (if configured)
    if policy_config.limit_per_student is not None:
        # Count existing GRANTED entitlements for this seat and product
        existing_count = db.session.query(EntitlementEvent).filter_by(
            class_id=canonical_context.class_id,
            target_seat_id=canonical_context.seat_id,
            product_id=policy_config.product_id,
            event_type='GRANTED',
        ).count()

        # The teacher configures a *purchase* limit, but grants are counted in
        # units, so convert the limit into the same unit before comparing —
        # otherwise a bundle of five would exhaust a limit of five in one buy.
        granted_units_allowed = policy_config.limit_per_student * units_per_purchase
        if existing_count + units_to_grant > granted_units_allowed:
            return StorePurchaseResult(
                success=False,
                correlation_id="",
                quantity_granted=0,
                error_code="LIMIT_EXCEEDED",
                error_message=f"Purchasing {quantity} would exceed per-student limit of {policy_config.limit_per_student}",
            )

    # Generate or use provided correlation ID
    corr_id = correlation_id or get_correlation_id() or f"store_purchase_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Ledger Execution
    # =========================================================================

    # FEAT-STOR-001 §VI.E: the charge is calculated from authoritative Policy
    # configuration. The bulk discount was published to the student on the item
    # card and then never applied to the debit — the student was quoted one
    # price and charged another. Recompute it here, on the authoritative side,
    # rather than trusting anything the client sent.
    debit_amount, _discount_applied = _calculate_debit(policy_config, quantity)

    intended_plan = build_intended_ledger_plan(
        seat_id=canonical_context.seat_id,
        class_id=canonical_context.class_id,
        user_id=canonical_context.user_id,
        debit_amount=debit_amount,
        # "Purchase: <name> (xN)" is not cosmetic — it is the format
        # ``transaction_void_feat._void_purchase`` parses to find the item and
        # the quantity it must return. A differently worded description makes a
        # purchase unvoidable.
        description=f"Purchase: {policy_config.name or policy_config.product_id} (x{quantity})",
        transaction_type="purchase",
        source_account="checking",
        target_account="store_purchase",
    )
    economic_engine = get_current_economic_engine(canonical_context.class_id)
    ledger_idempotency_key = idempotency_key or f"store-purchase:{corr_id}:ledger-plan"
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        economic_engine=economic_engine,
        idempotency_key=ledger_idempotency_key,
        allow_recovery_transfer=True,
    )
    if resolved_plan.outcome == "DENY":
        return StorePurchaseResult(
            success=False,
            correlation_id=corr_id,
            quantity_granted=0,
            error_code="INSUFFICIENT_FUNDS",
            error_message="Purchase denied by Ledger",
        )
    ledger_result = apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        economic_engine=economic_engine,
        idempotency_key=ledger_idempotency_key,
    )
    if not ledger_result.get("accepted", False):
        return StorePurchaseResult(
            success=False,
            correlation_id=corr_id,
            quantity_granted=0,
            error_code="INSUFFICIENT_FUNDS",
            error_message=f"Purchase denied by Ledger: {ledger_result.get('reason', 'unknown')}",
        )

    # Cross-domain orchestration: if Ledger charged an NSF fee while resolving this
    # purchase, record it as a fine obligation (Ledger stays domain-blind —
    # DOM-LED-001 §II; the fine is Obligations-owned — SPEC-ECON-003, DOM-OBL-001 §II.C).
    nsf_fee_txn_id = ledger_result.get("ledger_transaction_id")
    if nsf_fee_txn_id:
        from app.feats.nsf_fee_feat import record_nsf_fee_obligation
        record_nsf_fee_obligation(
            class_id=canonical_context.class_id,
            seat_id=canonical_context.seat_id,
            fee_transaction_id=nsf_fee_txn_id,
        )

    # =========================================================================
    # PHASE 3: Entitlement Grants (Atomic)
    # =========================================================================

    # Get current timestamp via canonical temporal resolver
    temporal_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="current_time",
    )
    timestamp_utc = temporal_eval.canonical_now_utc

    entitlement_ids = []

    for _unit_idx in range(units_to_grant):
        entitlement_id = str(uuid.uuid4())

        # Build event payload per DOM-STORE-001 §VII.A.
        #
        # That section is restrictive about what may live here: the payload
        # "SHALL contain only the type-specific authoritative facts necessary to
        # interpret the event" and "SHALL NOT duplicate monetary truth, policy
        # rules, or derived balances" — and entitlement_events "SHALL NOT contain
        # quantity, remaining balance, mutable redemption status, or display
        # metadata."
        #
        # So a bundle records nothing about its size here. Each unit is its own
        # entitlement lifecycle (FEAT-STOR-001 §VII.E), and the count of units is
        # recovered by counting rows sharing this correlation_id — a derived
        # quantity, which is exactly why it must not be stored. Likewise the
        # amount charged is the Ledger's truth, not the entitlement's; it is
        # reachable through the same correlation_id.
        #
        # ``policy_uuid`` is the one thing that must be frozen: it is what lets a
        # holder resolve the exact terms they bought under after the teacher
        # supersedes the product.
        event_payload = {
            "instant_use": instant_use,
            "policy_uuid": policy_config.policy_uuid,
        }

        event = EntitlementEvent(
            event_id=str(uuid.uuid4()),
            entitlement_id=entitlement_id,
            class_id=canonical_context.class_id,
            target_seat_id=canonical_context.seat_id,
            actor_seat_id=canonical_context.seat_id,
            product_id=policy_config.product_id,  # Product identifier from resolved policy (per SPEC-STORE-001)
            entitlement_type=policy_config.entitlement_type,  # From resolved policy
            acquisition_type="PURCHASE",
            event_type="GRANTED",
            correlation_id=corr_id,
            payload=event_payload,
            timestamp=timestamp_utc,
        )
        db.session.add(event)
        entitlement_ids.append(entitlement_id)

    db.session.flush()  # Ensure all rows are written before instant-use coordination

    # =========================================================================
    # PHASE 4: Instant-Use Coordination (if applicable)
    # =========================================================================

    if instant_use:
        # Create CONSUMED event for each granted entitlement in the same transaction
        for entitlement_id in entitlement_ids:
            consumed_event = EntitlementEvent(
                event_id=str(uuid.uuid4()),
                entitlement_id=entitlement_id,
                class_id=canonical_context.class_id,
                target_seat_id=canonical_context.seat_id,
                actor_seat_id=canonical_context.seat_id,
                product_id=policy_config.product_id,  # From resolved policy
                entitlement_type=policy_config.entitlement_type,  # From resolved policy
                acquisition_type="PURCHASE",
                event_type="CONSUMED",
                correlation_id=corr_id,
                payload={
                    "consumed_at_purchase": True,
                    "purchase_instant_use": True,
                    "policy_uuid": policy_config.policy_uuid,
                },
                timestamp=timestamp_utc,
            )
            db.session.add(consumed_event)

        db.session.flush()

    return StorePurchaseResult(
        success=True,
        correlation_id=corr_id,
        quantity_granted=units_to_grant,
        entitlement_ids=entitlement_ids,
        product_id=policy_config.product_id,  # From resolved policy
        error_code=None,
        error_message=None,
    )
