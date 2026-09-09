"""
Store Service — product definition publication and visibility (DOM-POL-001).

Product definitions are immutable and versioned. A teacher "editing" a product
does not rewrite its row: it publishes a **new version** carrying a fresh
``policy_uuid`` under the **same** ``product_lineage_uuid``, and retires the
version it replaced. Entitlements already sold freeze the ``policy_uuid`` they
were bought under, so a price change cannot retroactively alter what a student
already owns (DOM-POL-001 §VI.0, DOM-STORE-001 §VII).

Two identifiers, and using the wrong one is the main hazard in this module:

* ``policy_uuid`` — the version. Purchases resolve against it.
* ``product_lineage_uuid`` — the product. Visibility, entitlement history, and
  every derived quantity (units sold, goal progress, stock remaining) key off it
  so they survive an edit.

SCOPE:
- Publish / supersede / hide / retire product versions
- Per-seat visibility (keyed by lineage)
- Derived availability reads (stock remaining, units sold)

OUT OF SCOPE:
- Entitlement grant/consumption (FEAT-STOR-001/002/004)
- Entitlement queries (entitlement_read_service.py, DOM-STORE-001)
- Purchase coordination (FEAT-STOR-001)

These functions perform ORM mutations and MUST run inside an active FEAT
context (enforced by ``app.feats.base``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional
import uuid

from app.extensions import db
from app.models import (
    Seat,
    StoreProduct,
    StoreItemVisibility,
    ClassEconomy,
    EntitlementEvent,
)
from app.services.store_policy_resolver import StorePolicyResolver
from app.utils.canonical_temporal_resolver import utc_now

# The resolver owns the teacher-facing → domain vocabulary map, and every read
# path projects a row through it. An item_type outside that map therefore
# publishes cleanly and then fails every later read for the whole class
# (list_store_policies, build_policy_list_view). Publication is the only seam
# that writes item_type, so the set is enforced here.
CANONICAL_ITEM_TYPES = frozenset(StorePolicyResolver._ITEM_TYPE_TO_ENTITLEMENT_TYPE)


# Canonical availability projection states (DOM-POL-001 §IX).
IN_USE = "IN_USE"
HIDDEN = "HIDDEN"
RETIRED = "RETIRED"
AVAILABILITY_STATES = frozenset({IN_USE, HIDDEN, RETIRED})


# Definition fields a caller may supply when publishing a version. Structural
# allow-list only — semantic validation belongs to the calling FEAT.
_DEFINITION_FIELDS = frozenset({
    "name", "description", "price", "tier", "item_type", "inventory_total",
    "limit_per_student", "auto_delist_date", "auto_expiry_days",
    "is_long_term_goal", "bypass_cwi_warnings", "is_bundle", "bundle_quantity",
    "bulk_discount_enabled", "bulk_discount_quantity", "bulk_discount_percentage",
    "collective_goal_type", "collective_goal_target", "collective_goal_expires_at",
    "collective_goal_instance_code", "redemption_prompt",
})


class StoreServiceError(Exception):
    """Base error for the store product mechanism."""


class UnknownDefinitionField(StoreServiceError):
    """The definition carried a key outside the writable column set."""


class ProductNotFound(StoreServiceError):
    """No product version exists for the given (class_id, locator)."""


class InvalidAvailabilityState(StoreServiceError):
    """Requested availability_state is not a canonical projection state."""


class InvalidDefinition(StoreServiceError):
    """The definition violates SPEC-STORE-001 §V product configuration rules."""


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


def _reject_unknown_fields(fields: dict) -> None:
    extra = set(fields) - _DEFINITION_FIELDS
    if extra:
        raise UnknownDefinitionField(
            f"Unknown store product definition fields: {sorted(extra)}"
        )


# Both sale mechanics that scale a purchase — bundling and the bulk discount —
# presuppose that owning several at once means something. That is only true of a
# type which can hold more than one unexercised unit. An immediate item is
# redeemed on the spot, and a privilege is a standing state rather than a count,
# so neither has a second unit to hold; a collective goal is a shared pot, where
# a single student's quantity is not the thing being counted at all. All three
# are therefore excluded from bundles and bulk discounts alike
# (SPEC-STORE-001 §V.A).
_MULTI_UNIT_ITEM_TYPES = frozenset({'delayed', 'hall_pass'})

# Types with no post-purchase window to expire.
_NON_EXPIRING_ITEM_TYPES = frozenset({'immediate', 'privilege'})


def _validate_definition(definition: dict) -> None:
    """Enforce SPEC-STORE-001 §V at the one seam that writes a product.

    These rules used to live in the JSON payload parser, which the single-table
    consolidation retired — leaving them enforced nowhere, so a form post could
    persist a bundled immediate-use item or a collective goal with no deadline.
    They belong here rather than in a route because publication is the only way
    a definition reaches the database, and a rule enforced at one call site is a
    rule the next call site forgets.
    """
    item_type = definition.get('item_type')
    if item_type not in CANONICAL_ITEM_TYPES:
        raise InvalidDefinition(
            f"item_type {item_type!r} is not a catalog type; expected one of "
            + ", ".join(sorted(CANONICAL_ITEM_TYPES))
        )
    is_collective = item_type == 'collective'

    price = definition.get('price')
    if price is not None and Decimal(str(price)) < 0:
        raise InvalidDefinition("price cannot be negative")

    inventory_total = definition.get('inventory_total')
    if inventory_total is not None and inventory_total < 0:
        raise InvalidDefinition("inventory_total cannot be negative")

    limit_per_student = definition.get('limit_per_student')
    if limit_per_student is not None and limit_per_student <= 0:
        raise InvalidDefinition("limit_per_student must be greater than zero if set")

    auto_expiry_days = definition.get('auto_expiry_days')
    if auto_expiry_days is not None:
        if item_type in _NON_EXPIRING_ITEM_TYPES:
            raise InvalidDefinition(f"{item_type} items cannot have auto_expiry_days")
        if auto_expiry_days <= 0:
            raise InvalidDefinition("auto_expiry_days must be greater than zero if set")

    scales_with_quantity = (
        definition.get('is_bundle') or definition.get('bulk_discount_enabled')
    )
    if scales_with_quantity and item_type not in _MULTI_UNIT_ITEM_TYPES:
        # A goal is refused for a different reason than the rest, so it says so.
        if is_collective:
            raise InvalidDefinition(
                "a collective goal cannot carry bundle or bulk discount settings — "
                "a goal is a shared pot, and these price one student's order"
            )
        raise InvalidDefinition(
            f"{item_type} items cannot be bundled or given a bulk discount — both "
            "sell several at once, and only delayed and hall pass items can hold "
            "more than one unexercised unit"
        )

    if definition.get('is_bundle'):
        bundle_quantity = definition.get('bundle_quantity')
        if not bundle_quantity or bundle_quantity <= 1:
            raise InvalidDefinition("a bundle must grant more than one unit")

    if definition.get('bulk_discount_enabled'):
        quantity = definition.get('bulk_discount_quantity')
        percentage = definition.get('bulk_discount_percentage')
        if not quantity or quantity <= 1:
            raise InvalidDefinition("bulk_discount_quantity must be greater than one")
        if percentage is None or not (0 < Decimal(str(percentage)) <= 100):
            raise InvalidDefinition("bulk_discount_percentage must be within (0, 100]")

    if is_collective:
        goal_type = definition.get('collective_goal_type')
        if not goal_type:
            raise InvalidDefinition("a collective goal must declare collective_goal_type")
        target = definition.get('collective_goal_target')
        # Only the 'fixed' type carries a teacher-supplied target. A whole_class
        # goal derives its target from class size in
        # ``store.collective_goals.resolve_goal_target``, and the teacher leaves
        # the field blank — requiring it here refused every whole-class goal at
        # publication.
        if goal_type == 'fixed':
            if not target or target <= 0:
                raise InvalidDefinition(
                    "a fixed collective goal must have a target above zero"
                )
        elif target is not None and target <= 0:
            raise InvalidDefinition("collective_goal_target must be above zero if set")
        if not definition.get('collective_goal_expires_at'):
            raise InvalidDefinition("a collective goal must have a deadline")
        # Bundle and bulk settings are refused above, with the rest of the types
        # that cannot hold multiple units.
    else:
        for field in ('collective_goal_type', 'collective_goal_target',
                      'collective_goal_expires_at'):
            if definition.get(field) is not None:
                raise InvalidDefinition(
                    f"{field} is only meaningful on a collective goal item"
                )


def publish_product(
    *,
    user_id: int,
    class_id: str,
    definition: dict,
    product_lineage_uuid: Optional[str] = None,
    availability_state: str = IN_USE,
    actor_seat_id: Optional[int] = None,
) -> StoreProduct:
    """Publish a new immutable product version.

    Omit ``product_lineage_uuid`` to start a new product; pass one to publish the
    next version of an existing product. In the latter case the caller is
    responsible for having retired the previous live version — ``supersede_product``
    does both and is what routes should normally call.
    """
    _reject_unknown_fields(definition)
    _validate_definition(definition)
    if availability_state not in AVAILABILITY_STATES:
        raise InvalidAvailabilityState(availability_state)

    product = StoreProduct(
        policy_uuid=str(uuid.uuid4()),
        product_lineage_uuid=product_lineage_uuid or str(uuid.uuid4()),
        user_id=user_id,
        class_id=class_id,
        availability_state=availability_state,
        created_by_seat_id=actor_seat_id,
        **definition,
    )
    db.session.add(product)
    db.session.flush()
    return product


def supersede_product(
    *,
    current: StoreProduct,
    definition: dict,
    actor_seat_id: Optional[int] = None,
) -> StoreProduct:
    """Retire ``current`` and publish its replacement in the same lineage.

    Retiring first matters: the partial unique index permits only one ``IN_USE``
    version per lineage, so publishing before retiring would collide — which is
    the point. Two live versions of one product means two prices, and the index
    refuses to let that exist even briefly.
    """
    retire_product(current)
    return publish_product(
        user_id=current.user_id,
        class_id=current.class_id,
        definition=definition,
        product_lineage_uuid=current.product_lineage_uuid,
        availability_state=IN_USE,
        actor_seat_id=actor_seat_id,
    )


def set_availability(product: StoreProduct, state: str) -> StoreProduct:
    """Move the availability projection — the only lawful in-place mutation."""
    if state not in AVAILABILITY_STATES:
        raise InvalidAvailabilityState(state)
    product.availability_state = state
    product.retired_at = utc_now() if state == RETIRED else None
    db.session.flush()
    return product


def hide_product(product: StoreProduct) -> StoreProduct:
    """Withhold from students without ending the version. Restorable."""
    return set_availability(product, HIDDEN)


def restore_product(product: StoreProduct) -> StoreProduct:
    """Put a hidden version back on sale."""
    return set_availability(product, IN_USE)


def retire_product(product: StoreProduct) -> StoreProduct:
    """End this version permanently. Entitlements sold under it stay resolvable."""
    return set_availability(product, RETIRED)


def retire_lineage(class_id: str, product_lineage_uuid: str) -> int:
    """Retire every non-retired version of a product. Returns the count."""
    versions = (
        StoreProduct.query.filter(
            StoreProduct.class_id == class_id,
            StoreProduct.product_lineage_uuid == product_lineage_uuid,
            StoreProduct.availability_state != RETIRED,
        ).all()
    )
    for version in versions:
        set_availability(version, RETIRED)
    return len(versions)


# ---------------------------------------------------------------------------
# Retrieval — class-scoped, fail closed on class mismatch
# ---------------------------------------------------------------------------


def get_live_product(class_id: str, product_lineage_uuid: str) -> Optional[StoreProduct]:
    """The sellable version of a product, if it has one."""
    return StoreProduct.query.filter_by(
        class_id=class_id,
        product_lineage_uuid=product_lineage_uuid,
        availability_state=IN_USE,
    ).first()


def get_product_version(class_id: str, policy_uuid: str) -> Optional[StoreProduct]:
    """An exact version by its policy_uuid, whatever its availability."""
    return StoreProduct.query.filter_by(
        class_id=class_id, policy_uuid=policy_uuid
    ).first()


def get_current_version(class_id: str, product_lineage_uuid: str) -> Optional[StoreProduct]:
    """The newest non-retired version — what the teacher edits."""
    return (
        StoreProduct.query.filter(
            StoreProduct.class_id == class_id,
            StoreProduct.product_lineage_uuid == product_lineage_uuid,
            StoreProduct.availability_state != RETIRED,
        )
        .order_by(StoreProduct.created_at.desc())
        .first()
    )


def resolve_entitlement_product(event) -> Optional[StoreProduct]:
    """The product version an entitlement event was created under.

    Prefers the exact version frozen in ``payload["policy_uuid"]``, so a
    redemption screen shows the name and terms the student actually bought
    rather than whatever the teacher has since edited them into. Falls back to
    the newest version in the lineage for older events written before the
    payload carried a version, and deliberately includes RETIRED versions —
    an entitlement outlives the shelf life of the thing that produced it.
    """
    if not getattr(event, "product_id", None) or not getattr(event, "class_id", None):
        return None

    frozen_uuid = (getattr(event, "payload", None) or {}).get("policy_uuid")
    if frozen_uuid:
        version = get_product_version(event.class_id, frozen_uuid)
        if version is not None:
            return version

    return (
        StoreProduct.query.filter(
            StoreProduct.class_id == event.class_id,
            StoreProduct.product_lineage_uuid == event.product_id,
        )
        .order_by(StoreProduct.created_at.desc())
        .first()
    )


def list_products(
    class_id: str, *, states: Iterable[str] = (IN_USE, HIDDEN)
) -> list[StoreProduct]:
    """Current versions for a class, newest first."""
    return (
        StoreProduct.query.filter(
            StoreProduct.class_id == class_id,
            StoreProduct.availability_state.in_(tuple(states)),
        )
        .order_by(StoreProduct.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Derived quantities — never stored (DOM-STORE-001 §VII.A)
# ---------------------------------------------------------------------------


def units_sold(class_id: str, product_lineage_uuid: str) -> int:
    """Units granted by purchase for a product, across all its versions.

    Counts ``GRANTED`` events and subtracts those whose lifecycle later reached
    ``REVOKED``, so a voided purchase returns its stock. ``CONSUMED`` and
    ``EXPIRED`` do NOT return stock: the unit was issued and used up or lapsed,
    which is not the same as never having been sold.
    """
    granted = (
        db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == product_lineage_uuid,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .subquery()
    )
    total = db.session.query(granted).count()
    revoked = (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == product_lineage_uuid,
            EntitlementEvent.event_type == "REVOKED",
            # Symmetric with the GRANTED leg. A REVOKED row copies the grant's
            # acquisition_type, so without this an inventory-free teacher GRANT
            # or rent PERK, when revoked, would subtract from a total it never
            # added to and hand the catalog back a unit that was never sold.
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .count()
    )
    return max(total - revoked, 0)


def units_sold_by_lineage(class_id: str, lineages: Iterable[str]) -> dict[str, int]:
    """Bulk form of :func:`units_sold` — one grouped query for a whole page.

    The store-management and shop pages render every product at once; issuing a
    per-item count query there would turn a page load into N round trips.
    """
    lineage_list = [l for l in lineages if l]
    if not lineage_list:
        return {}

    rows = (
        db.session.query(
            EntitlementEvent.product_id,
            EntitlementEvent.event_type,
            db.func.count().label("n"),
        )
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id.in_(lineage_list),
            EntitlementEvent.event_type.in_(("GRANTED", "REVOKED")),
            # Both legs are purchase-only, as in units_sold(); the previous
            # db.or_ exempted REVOKED from the acquisition filter, so a revoked
            # grant or perk decremented a purchase tally.
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .group_by(EntitlementEvent.product_id, EntitlementEvent.event_type)
        .all()
    )

    tallies: dict[str, dict[str, int]] = {}
    for lineage, event_type, count in rows:
        tallies.setdefault(lineage, {})[event_type] = int(count or 0)

    return {
        lineage: max(counts.get("GRANTED", 0) - counts.get("REVOKED", 0), 0)
        for lineage, counts in tallies.items()
    }


def stock_remaining(product: StoreProduct) -> Optional[int]:
    """Units still purchasable, or None when the product is unlimited."""
    if product.inventory_total is None:
        return None
    sold = units_sold(product.class_id, product.product_lineage_uuid)
    return max(product.inventory_total - sold, 0)


def distinct_buyers(class_id: str, product_lineage_uuid: str) -> int:
    """Seats holding at least one purchased unit — collective-goal progress."""
    return (
        db.session.query(EntitlementEvent.target_seat_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == product_lineage_uuid,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .distinct()
        .count()
    )


# ---------------------------------------------------------------------------
# Store Product Visibility — keyed by lineage, so an edit does not drop grants
# ---------------------------------------------------------------------------


def is_product_visible_to_seat(product_lineage_uuid: str, seat_id: int) -> bool:
    """No visibility rows means visible to all; rows restrict to those seats."""
    has_rows = StoreItemVisibility.query.filter_by(
        product_lineage_uuid=product_lineage_uuid
    ).first()
    if has_rows is None:
        return True
    return StoreItemVisibility.query.filter_by(
        product_lineage_uuid=product_lineage_uuid,
        seat_id=seat_id,
    ).first() is not None


def set_product_visibility(product_lineage_uuid: str, seat_ids: list[int]) -> None:
    """Replace visibility grants. Empty list = visible to all."""
    StoreItemVisibility.query.filter_by(
        product_lineage_uuid=product_lineage_uuid
    ).delete()
    for seat_id in set(seat_ids):
        db.session.add(
            StoreItemVisibility(
                product_lineage_uuid=product_lineage_uuid, seat_id=seat_id
            )
        )


def create_product_block(*, product_lineage_uuid: str, class_id: str, block: str) -> None:
    """Grant visibility to all seats in the given block."""
    if not block or not class_id:
        return

    normalized_block = block.strip().upper()
    seat_ids = [
        seat_id
        for (seat_id,) in (
            db.session.query(Seat.id)
            .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
            .filter(
                ClassEconomy.class_id == class_id,
                ClassEconomy.section.isnot(None),
                ClassEconomy.section == normalized_block,
            )
            .distinct()
            .all()
        )
    ]
    existing = {
        seat_id
        for (seat_id,) in db.session.query(StoreItemVisibility.seat_id).filter_by(
            product_lineage_uuid=product_lineage_uuid
        )
    }
    new_rows = [
        StoreItemVisibility(product_lineage_uuid=product_lineage_uuid, seat_id=seat_id)
        for seat_id in seat_ids
        if seat_id not in existing
    ]
    if new_rows:
        db.session.add_all(new_rows)
