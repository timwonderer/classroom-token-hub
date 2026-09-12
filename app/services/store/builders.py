"""
Store Domain View Model Builders — Phase 1 Remediation

Converts raw store item and entitlement data into immutable, presentation-ready
view models per SPEC-UI-001 and INV-ARC-022.

All business logic for rent entitlements, pricing, and collective goal progress
is pre-computed here. Templates receive only formatted display values.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import StoreProduct, EntitlementEvent, RentSettings, ClassEconomy


@dataclass(frozen=True)
class CollectiveProgressView:
    """Pre-computed progress state for collective goal items."""
    item_id: str
    purchase_count: int
    target_count: int
    remaining_count: int
    progress_percent: int
    is_complete: bool
    goal_type: str  # 'fixed' or 'whole_class'
    display_expires_at: str | None  # Pre-formatted expiry date, or None


@dataclass(frozen=True)
class StoreItemCardView:
    """
    Pre-computed view model for a store item card in the browse tab.

    Eliminates all template-level rent entitlement logic (lines 30-39 of student_shop.html).
    All boolean flags and pricing state are pre-calculated.
    """
    # The product lineage — stable across edits. Use this for anything that
    # aggregates over the product (visibility, goal progress, stock).
    item_id: str
    name: str
    description: str | None
    display_price: str  # Pre-formatted as "$X.XX"
    display_regular_price: str  # Pre-formatted as "$X.XX" (used in rent perk badges)
    price_amount: str  # Unformatted decimal string for data attributes
    regular_price_amount: str  # Unformatted decimal string for data attributes
    # The exact version on sale. This is what a purchase must quote back, so
    # the terms the student saw are the terms they are charged.
    policy_uuid: str | None
    item_type: str  # 'immediate', 'delayed', 'collective', 'hall_pass'
    inventory_available: int | None  # None means unlimited
    limit_per_student: int | None
    is_bundle: bool
    bundle_quantity: int | None
    bulk_discount_enabled: bool
    bulk_discount_quantity: int | None
    bulk_discount_percentage: float | None

    # Rent entitlement flags (pre-computed per audit violations lines 30-39)
    is_privilege_rent_item: bool
    is_per_use_rent_item: bool
    is_hall_pass_item: bool
    is_rent_perk_item: bool
    is_rent_covered: bool  # Rendered with reduced opacity if True
    has_rent_free_purchase: bool
    has_any_rent_free_purchase: bool
    rent_free_units_available: int | None  # None, -1 (unlimited), or count

    # Collective goal (pre-computed per audit violations lines 100-135)
    collective_progress: CollectiveProgressView | None

    # Derived presentation state
    is_out_of_stock: bool  # inventory is not None and <= 0
    button_disabled: bool  # True if out of stock or rent covered
    button_text: str  # "Out of Stock", "Already Included", or "Purchase"

    @property
    def display_rent_perk_message(self) -> str | None:
        """Return the rent perk badge message, or None if not applicable.

        The message describes units the student already **holds**, so it says
        where to find them. Wording it as a price ("free purchase") invited the
        reading that buying again costs nothing, which was never true.
        """
        if not self.has_any_rent_free_purchase:
            return None
        if self.rent_free_units_available == -1:
            return "Unlimited free uses in My Items"
        if self.rent_free_units_available and self.rent_free_units_available > 0:
            plural = "use" if self.rent_free_units_available == 1 else "uses"
            return f"{self.rent_free_units_available} free {plural} in My Items"
        return None


@dataclass(frozen=True)
class EntitlementCardView:
    """
    Pre-computed view model for a purchased item in the My Items tab.

    Flattens ORM traversals (entitlement.store_item.*) and pre-formats all dates.
    Eliminates template-level ORM access (lines 198-234 of student_shop.html).
    """
    entitlement_id: str
    item_id: str
    item_name: str  # Flattened from ORM: entitlement.store_item.name
    item_type: str  # 'immediate', 'delayed', 'collective', 'hall_pass'
    item_description: str | None  # Flattened from ORM
    status: str  # 'purchased', 'pending', 'processing', etc.
    display_status: str  # Display label: "Ready to Use", "Pending Approval", etc.
    # Timestamps stay as datetimes. Rendering them is the temporal resolver's
    # job (fmt_timestamp / fmt_date), which localizes to the class timezone;
    # pre-formatting here would hard-code UTC.
    purchased_at: datetime | None
    expires_at: datetime | None
    has_expiry_date: bool
    redemption_prompt: str | None

    # Derived presentation state
    can_redeem_immediately: bool  # immediate items in purchased status
    can_request_redemption: bool  # delayed items in purchased status
    can_use_hall_pass: bool  # hall pass items in purchased status
    is_pending_approval: bool
    is_processing: bool
    is_hall_pass: bool
    status_badge_class: str  # Bootstrap badge class based on status (bg-success, bg-warning, etc.)


def build_store_item_card_view(
    item: StoreProduct,
    class_id: str,
    has_paid_rent: bool,
    rent_item_types_by_lineage: dict[str, Collection[str]],
    rent_free_entitlement_counts: dict[str, int | None],
    collective_progress_by_item: dict[str, CollectiveProgressView] | None = None,
    stock_remaining: int | None = None,
) -> StoreItemCardView:
    """
    Build a pre-computed view model for a store item card.

    Eliminates all {% set %} logic from template (lines 30-39, 100-135).

    Every caller-supplied map is keyed by ``product_lineage_uuid``, not by the
    version's ``policy_uuid``. Rent linkage, goal progress and remaining stock
    are all properties of the *product*; keying them by version would make a
    teacher's edit look like a brand-new product with a fresh goal and full
    shelves.

    Args:
        item: The StoreProduct version currently on sale
        class_id: Class scope for multi-tenancy
        has_paid_rent: Whether current student has paid rent
        rent_item_types_by_lineage: lineage uuid -> rent perk types
        rent_free_entitlement_counts: lineage uuid -> free use count (-1 unlimited)
        collective_progress_by_item: lineage uuid -> pre-computed progress
        stock_remaining: Derived units left, or None when inventory is unlimited

    Returns:
        Frozen StoreItemCardView ready for template consumption
    """
    lineage = item.product_lineage_uuid

    # Pre-compute all rent entitlement flags (audit violations lines 30-39)
    rent_item_types = rent_item_types_by_lineage.get(lineage, [])
    is_privilege_rent_item = 'privilege' in rent_item_types
    is_per_use_rent_item = 'per_use' in rent_item_types
    is_hall_pass_item = item.item_type == 'hall_pass'
    is_rent_perk_item = (not is_hall_pass_item) and len(rent_item_types) > 0
    is_rent_covered = (
        has_paid_rent and is_privilege_rent_item and not is_per_use_rent_item
    )

    rent_free_units_available = rent_free_entitlement_counts.get(lineage)
    has_rent_free_purchase = (
        rent_free_units_available is not None
        and (rent_free_units_available == -1 or rent_free_units_available > 0)
    )
    has_any_rent_free_purchase = has_rent_free_purchase

    # Pre-compute pricing display (pre-formatted, no Jinja filters)
    #
    # Holding rent-perk units does NOT discount a purchase. A PERK grant
    # (DOM-STORE-001 §A) is an entitlement the student already possesses — it
    # is redeemed from My Items, not re-bought at $0. This branch used to quote
    # $0.00 for anyone holding one, which nothing on the server ever honoured;
    # it was invisible only for as long as purchases failed to debit at all.
    if is_rent_covered:
        # Distinct case: the button is disabled ("Already Included"), so no
        # purchase can be attempted and the zero is a statement, not a quote.
        display_price = "$0.00"
        price_amount = "0.00"
    else:
        display_price = f"${item.price:.2f}"
        price_amount = f"{item.price:.2f}"

    display_regular_price = f"${item.price:.2f}"
    regular_price_amount = f"{item.price:.2f}"

    # Pre-compute inventory state. ``inventory_total`` is the ceiling the
    # teacher configured; what is left is derived from granted entitlements and
    # supplied by the caller, so it is never stored and never drifts.
    is_out_of_stock = stock_remaining is not None and stock_remaining <= 0
    button_disabled = is_rent_covered or is_out_of_stock
    if is_out_of_stock:
        button_text = "Out of Stock"
    elif is_rent_covered:
        button_text = "Already Included"
    else:
        button_text = "Purchase"

    # Pre-compute collective goal progress (audit violations lines 100-135)
    collective_progress = None
    if item.item_type == 'collective' and collective_progress_by_item:
        collective_progress = collective_progress_by_item.get(lineage)

    return StoreItemCardView(
        item_id=lineage,
        name=item.name,
        description=item.description,
        display_price=display_price,
        display_regular_price=display_regular_price,
        price_amount=price_amount,
        regular_price_amount=regular_price_amount,
        policy_uuid=item.policy_uuid,
        item_type=item.item_type,
        inventory_available=stock_remaining,
        limit_per_student=item.limit_per_student,
        is_bundle=item.is_bundle,
        bundle_quantity=item.bundle_quantity,
        bulk_discount_enabled=item.bulk_discount_enabled,
        bulk_discount_quantity=item.bulk_discount_quantity,
        bulk_discount_percentage=item.bulk_discount_percentage,
        is_privilege_rent_item=is_privilege_rent_item,
        is_per_use_rent_item=is_per_use_rent_item,
        is_hall_pass_item=is_hall_pass_item,
        is_rent_perk_item=is_rent_perk_item,
        is_rent_covered=is_rent_covered,
        has_rent_free_purchase=has_rent_free_purchase,
        has_any_rent_free_purchase=has_any_rent_free_purchase,
        rent_free_units_available=rent_free_units_available,
        collective_progress=collective_progress,
        is_out_of_stock=is_out_of_stock,
        button_disabled=button_disabled,
        button_text=button_text,
    )


def build_entitlement_card_view(
    entitlement: Any,
    class_id: str,
) -> EntitlementCardView:
    """
    Build a pre-computed view model for a purchased item card.

    Flattens ORM traversals and pre-formats all dates (audit violations lines 198-234).
    Accepts both EntitlementEvent models and SimpleNamespace objects from legacy routes.

    Args:
        entitlement: EntitlementEvent or SimpleNamespace with entitlement data
        class_id: Class scope for multi-tenancy

    Returns:
        Frozen EntitlementCardView ready for template consumption
    """
    # Handle SimpleNamespace objects from legacy routes
    if hasattr(entitlement, 'store_item'):
        # Legacy route object: SimpleNamespace with store_item attribute
        item = entitlement.store_item
        item_name = item.name if item else "Unknown Item"
        item_description = item.description if item else None
        item_type = item.item_type if item else "immediate"
        status = getattr(entitlement, 'status', 'purchased')
        entitlement_id = getattr(entitlement, 'id', 'unknown')
        purchase_date = getattr(entitlement, 'purchase_date', None)
        expiry_date = getattr(entitlement, 'expiry_date', None)
        item_id = item.product_lineage_uuid if item else 0
        redemption_prompt = getattr(item, 'redemption_prompt', None) if item else None
    else:
        # EntitlementEvent model
        payload = getattr(entitlement, 'payload', None) or {}
        item_name = f"Product {getattr(entitlement, 'product_id', 0)}"
        item_description = None
        item_type = getattr(entitlement, 'entitlement_type', 'immediate') or getattr(entitlement, 'acquisition_type', 'immediate')
        status = "purchased"  # Default for GRANTED events
        event_type = getattr(entitlement, 'event_type', 'GRANTED')
        if event_type == "CONSUMED":
            status = "consumed"
        elif event_type == "EXPIRED":
            status = "expired"
        elif event_type == "REVOKED":
            status = "revoked"
        entitlement_id = getattr(entitlement, 'entitlement_id', 'unknown')
        purchase_date = getattr(entitlement, 'timestamp', None)
        expiry_date = payload.get("expiry_date")
        item_id = getattr(entitlement, 'product_id', 0) or 0
        redemption_prompt = payload.get("redemption_prompt")

    # Map status to display label
    status_labels = {
        "purchased": "Ready to Use",
        "pending": "Pending Approval",
        "processing": "Processing",
        "consumed": "Used",
        "expired": "Expired",
        "revoked": "Revoked",
    }
    display_status = status_labels.get(status, status.title())

    # The expiry date arrives from the event payload, so it may be an ISO string.
    expires_at = None
    if expiry_date:
        try:
            if isinstance(expiry_date, str):
                expires_at = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
            else:
                expires_at = expiry_date
        except (ValueError, TypeError):
            pass
    has_expiry_date = expires_at is not None

    # Derive presentation state
    is_hall_pass = item_type == "hall_pass"
    can_redeem_immediately = (
        item_type == "immediate" and status == "purchased"
    )
    can_request_redemption = (
        item_type == "delayed" and status == "purchased"
    )
    can_use_hall_pass = is_hall_pass and status == "purchased"
    is_pending_approval = status == "pending"
    is_processing = status == "processing"

    # Map status to badge class
    status_badge_classes = {
        "purchased": "bg-success",
        "pending": "bg-warning",
        "processing": "bg-info",
        "consumed": "bg-secondary",
        "expired": "bg-secondary",
        "revoked": "bg-danger",
    }
    status_badge_class = status_badge_classes.get(status, "bg-secondary")

    return EntitlementCardView(
        entitlement_id=str(entitlement_id),
        item_id=str(item_id),
        item_name=item_name,
        item_type=item_type,
        item_description=item_description,
        status=status,
        display_status=display_status,
        purchased_at=purchase_date,
        expires_at=expires_at,
        has_expiry_date=has_expiry_date,
        redemption_prompt=redemption_prompt,
        can_redeem_immediately=can_redeem_immediately,
        can_request_redemption=can_request_redemption,
        can_use_hall_pass=can_use_hall_pass,
        is_pending_approval=is_pending_approval,
        is_processing=is_processing,
        is_hall_pass=is_hall_pass,
        status_badge_class=status_badge_class,
    )


def build_collective_progress_view(
    item: StoreProduct,
    purchase_count: int,
    class_size: int | None = None,
) -> CollectiveProgressView:
    """
    Build a pre-computed view model for collective goal progress.

    Pre-computes all calculations (audit violations lines 100-135).

    Args:
        item: The StoreProduct with collective_goal_type and collective_goal_target
        purchase_count: Current number of purchases for this item
        class_size: Total students in class (for 'whole_class' goals)

    Returns:
        Frozen CollectiveProgressView ready for template consumption
    """
    if item.collective_goal_type == "whole_class":
        target = class_size or 1
    elif item.collective_goal_type == "fixed":
        target = item.collective_goal_target or 1
    else:
        target = 1

    remaining = max(0, target - purchase_count)
    progress_percent = min(100, (purchase_count * 100) // target if target > 0 else 0)
    is_complete = purchase_count >= target

    # Pre-format expiry date (no strftime in template)
    display_expires_at = None
    if item.collective_goal_expires_at:
        display_expires_at = item.collective_goal_expires_at.strftime("%b %d, %Y")

    return CollectiveProgressView(
        item_id=item.product_lineage_uuid,
        purchase_count=purchase_count,
        target_count=target,
        remaining_count=remaining,
        progress_percent=progress_percent,
        is_complete=is_complete,
        goal_type=item.collective_goal_type or "fixed",
        display_expires_at=display_expires_at,
    )
