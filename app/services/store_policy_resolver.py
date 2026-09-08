"""
Store Policy Resolver — STORE-owned policy consumption service.

Implements DOM-STORE-001 and SPEC-STORE-001:
- Resolves store product policies by UUID (exact immutable retrieval)
- Supports discovery of canonical policy definitions for a class

This module reads. Publication and its SPEC-STORE-001 §V validation live in
``app.services.store_service``.

Key principle: UUID resolution is exact, not inferential.
- resolve_store_item(policy_uuid) returns that exact immutable policy
- list_store_policies(class_id) returns canonical policy definitions for the class
- No cross-domain FK; no version inference from product_id + time
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.extensions import db
from app.models import StoreProduct, ClassEconomy


class StorePolicyError(Exception):
    """Base exception for store policy resolution errors."""
    pass


class PolicyNotFound(StorePolicyError):
    """Raised when policy UUID does not resolve."""
    pass


class PolicyParseError(StorePolicyError):
    """Raised when a stored product row cannot be projected into a config."""
    pass


class PolicyValidationError(StorePolicyError):
    """Raised when a stored product row violates SPEC-STORE-001 constraints."""
    pass


@dataclass(frozen=True)
class StorePolicyConfig:
    """Immutable resolved store product policy.

    Represents a resolved, validated policy per SPEC-STORE-001.
    All fields present and type-checked; no unknown fields.
    Snapshottable into entitlement_events.payload for historical reference.
    """

    # Required fields per SPEC-STORE-001 §IV.A
    #
    # ``product_id`` is the product LINEAGE uuid, not a row id. It identifies the
    # product across every version of it, which is what entitlement history and
    # all derived quantities aggregate over. The specific version resolved is
    # ``policy_uuid`` below.
    product_id: str
    is_purchasable: bool
    supports_direct_grants: bool
    price: Decimal
    entitlement_type: str  # IMMEDIATE_USE | DELAYED_USE | HALL_PASS | PRIVILEGE | INSURANCE | COLLECTIVE_GOAL

    # Optional fields per SPEC-STORE-001 §IV.C
    limit_per_student: Optional[int] = None
    auto_expiry_days: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    bypass_cwi_warnings: bool = False
    is_long_term_goal: bool = False
    bundle_quantity: Optional[int] = None
    bulk_discount_quantity: Optional[int] = None
    bulk_discount_percentage: Optional[float] = None
    collective_goal_type: Optional[str] = None
    collective_goal_target: Optional[int] = None
    collective_goal_expires_at: Optional[datetime] = None

    # Insurance publication locator (DOM-STORE-001): required iff
    # entitlement_type == INSURANCE, forbidden otherwise. Points to the
    # POL-owned insurance definition (InsurancePolicy.policy_uuid) this
    # StoreProduct publishes. Immutable with the rest of the definition.
    insurance_policy_uuid: Optional[str] = None

    # Metadata for historical reference
    policy_uuid: str = field(default="")
    class_id: str = field(default="")
    created_at: Optional[datetime] = None


# ``StorePolicyConfigParser`` has been removed. It decoded and validated a JSON
# policy payload, and nothing produces one any more: a product is published as a
# typed row and read back by ``StorePolicyResolver._config_from_row``. The
# SPEC-STORE-001 §V configuration rules it enforced now live at the single write
# seam, ``app.services.store_service._validate_definition`` — keeping a second,
# unreachable copy of those rules is precisely how the two drift apart.

class StorePolicyResolver:
    """Resolves store product policies by UUID.

    Implements:
    - Exact resolution: resolve_store_item(policy_uuid) → StorePolicyConfig
    - Discovery: list_store_policies(class_id) → List[StorePolicyConfig]

    Key principles:
    - UUID resolution is exact, not inferential
    - If policy is deleted, UUID no longer resolves (expected behavior)
    - Historical entitlements remain valid from their own snapshots
    """

    # StoreProduct.item_type is the teacher-facing vocabulary; entitlement_type is
    # the domain vocabulary SPEC-STORE-001 validates against.
    _ITEM_TYPE_TO_ENTITLEMENT_TYPE = {
        'immediate': 'IMMEDIATE_USE',
        'delayed': 'DELAYED_USE',
        'collective': 'COLLECTIVE_GOAL',
        'hall_pass': 'HALL_PASS',
        'privilege': 'PRIVILEGE',
    }

    @classmethod
    def _config_from_row(cls, product: StoreProduct) -> StorePolicyConfig:
        """Project a typed product row into a resolved policy config.

        There is no parsing step any more. The definition lives in typed columns
        with DB-level constraints, so schema validation happened at publication
        rather than on every read — the JSON payload this used to decode could
        drift from the catalog row it described, which is the class of defect the
        single-table model removes.
        """
        entitlement_type = cls._ITEM_TYPE_TO_ENTITLEMENT_TYPE.get(product.item_type)
        if entitlement_type is None:
            raise PolicyValidationError(
                f"Item type {product.item_type!r} has no entitlement type mapping"
            )

        return StorePolicyConfig(
            product_id=product.product_lineage_uuid,
            is_purchasable=(product.availability_state == 'IN_USE'),
            # HALL_PASS is the only catalog type a teacher may grant directly.
            supports_direct_grants=(entitlement_type == 'HALL_PASS'),
            price=product.price,
            entitlement_type=entitlement_type,
            limit_per_student=product.limit_per_student,
            auto_expiry_days=product.auto_expiry_days,
            name=product.name,
            description=product.description,
            tier=product.tier,
            bypass_cwi_warnings=bool(product.bypass_cwi_warnings),
            is_long_term_goal=bool(product.is_long_term_goal),
            bundle_quantity=(
                product.bundle_quantity
                if product.is_bundle and (product.bundle_quantity or 0) > 1
                else None
            ),
            bulk_discount_quantity=(
                product.bulk_discount_quantity if product.bulk_discount_enabled else None
            ),
            bulk_discount_percentage=(
                product.bulk_discount_percentage if product.bulk_discount_enabled else None
            ),
            collective_goal_type=product.collective_goal_type,
            collective_goal_target=product.collective_goal_target,
            collective_goal_expires_at=product.collective_goal_expires_at,
            policy_uuid=product.policy_uuid,
            class_id=product.class_id,
            created_at=product.created_at,
        )

    @classmethod
    def resolve_store_item(cls, policy_uuid: str) -> StorePolicyConfig:
        """Resolve an exact product version by UUID per SPEC-STORE-001 §VII.

        Resolution is exact and never inferential: a retired version still
        resolves, because entitlements sold under it must keep resolving their
        own terms. Whether it may be *sold* is carried by ``is_purchasable``,
        which the caller enforces — not by refusing to resolve.

        Raises:
            PolicyNotFound: If the UUID does not resolve.
        """
        product = db.session.query(StoreProduct).filter_by(policy_uuid=policy_uuid).first()

        if not product:
            raise PolicyNotFound(f"Policy UUID {policy_uuid} not found (may have been deleted)")

        return cls._config_from_row(product)

    @staticmethod
    def list_store_policies(class_id: str) -> List[StorePolicyConfig]:
        """List canonical store policy definitions for a class.

        This is a pure configuration discovery primitive. It does not evaluate
        student eligibility, affordability, entitlement ownership, class feature
        state, ordering, or presentation. Those concerns belong in Phase 5
        view models.
        Args:
            class_id: Class scope for policies

        Returns:
            List[StorePolicyConfig]: Canonical policy definitions for the class

        Raises:
            StorePolicyError: If any policy fails validation (stop on first error)
        """
        # Verify class exists
        class_economy = db.session.query(ClassEconomy).filter_by(class_id=class_id).first()
        if not class_economy:
            return []

        # Current (non-retired) versions only. Retired versions stay resolvable
        # individually for entitlements that froze them, but they are not part
        # of the catalog a class discovers.
        store_products = db.session.query(StoreProduct).filter(
            StoreProduct.class_id == class_id,
            StoreProduct.availability_state != 'RETIRED',
        ).all()

        policies = []
        for store_product in store_products:
            try:
                policies.append(StorePolicyResolver._config_from_row(store_product))
            except (PolicyParseError, PolicyValidationError) as e:
                # Fail-fast: stop on first validation error
                raise StorePolicyError(f"Policy {store_product.policy_uuid} in class {class_id} validation failed: {str(e)}")

        return policies

    # ``create_store_product(class_id, payload)`` has been removed. It wrote a
    # JSON-payload policy row that no catalog row pointed at, which is how the
    # two-table split produced products students could see but never buy.
    # Publication now goes through ``app.services.store_service.publish_product``
    # (or ``supersede_product`` for an edit), which writes the one typed row.
