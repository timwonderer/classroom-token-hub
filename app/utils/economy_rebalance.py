"""Economy rebalance: route each selected change to the command that owns it.

A rebalance writes nothing of its own. Every change is delegated to the owning
domain's command, and that domain's own append-only table is the record of the
change (DOM-CLASS-003 §IX, FEAT-ECON-001):

* rent and the rent late penalty → a new ``rent_settings`` row (DOM-POL-001 §VI.1)
* a store price → a superseding ``store_products`` version
* the overdraft fee → a new ``economic_engine`` version (FEAT-CLASS-005)

A change scheduled for the next cycle is an appended row whose effective date is
the owning domain's next boundary. Nothing is queued and nothing activates it
later: the row is in force for the first work its domain issues after that
boundary, and it is visible as pending until then (DOM-CLASS-003 §VII, §X).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models import RentSettings
from app.services.admin_settings_service import supersede_rent_settings
from app.services import store_service
from app.models import StoreProduct
from app.services.class_configuration_query_service import (
    get_rent_settings,
    pending_economic_engines,
)
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now


REBALANCE_ACTIVATION_IMMEDIATE = "immediate"
REBALANCE_ACTIVATION_NEXT_RENEWAL = "next_renewal"

# FEAT-CLASS-005 §XI delegates each rebalance row to its owning command. Every
# selectable change type must name that owner; an unmapped type is refused
# rather than skipped, because a skipped row still reported success.
_CHANGE_TYPE_OWNERS = {
    "rent": "rent",
    "rent_late_penalty": "rent",
    "store_item": "store",
    "overdraft_fee": "banking",
}

# The rent fields a scheduled change may set, by change type.
_RENT_FIELDS = {
    "rent": "rent_amount",
    "rent_late_penalty": "late_penalty_amount",
}

# Store prices change by product-version supersession, which retires the live
# version at once, and overdraft fees by Economic Engine evolution. Neither
# owning domain defines a later activation boundary (FEAT-ECON-001 §VIII), so
# these rows can only be applied immediately; they are never scheduled.
IMMEDIATE_ONLY_CHANGE_TYPES = frozenset({"store_item", "overdraft_fee"})


class UnsupportedRebalanceChange(ValueError):
    """A rebalance change has no owning command, or cannot run in the requested mode."""


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


def _get_rent_effective_at(settings, reference_time: datetime) -> datetime:
    """Start of the first rent period a policy saved now would bind to.

    A policy binds when a period is assessed (DOM-OBL-001 §V.7), so every
    period already issued keeps its terms; the first unissued period begins at
    the latest issued cycle's end. With no cycle yet, the save is in force now.
    """
    from app.services.obligations_service import get_latest_bill_cycle

    latest = get_latest_bill_cycle(f"rent:{settings.class_id}")
    if latest is None or latest.next_assessment_at is None:
        return reference_time
    return ensure_utc(latest.next_assessment_at)


def prepare_scheduled_rebalance_changes(change_plan, *, rent_settings=None, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    scheduled_changes = []

    for change in change_plan:
        enriched_change = dict(change)
        effective_at = None

        # A late penalty is part of the rent contract, so it activates at the
        # same rent boundary as the amount it accompanies.
        if change.get("type") in {"rent", "rent_late_penalty"} and rent_settings is not None:
            effective_at = _get_rent_effective_at(rent_settings, reference_time)

        enriched_change["effective_at"] = _serialize_dt(effective_at)
        scheduled_changes.append(enriched_change)

    return scheduled_changes


def _get_effective_rent_settings(class_id: str | None):
    """Resolve the rent policy currently in force for the class.

    ``rent_settings`` is append-only (DOM-POL-001 §VI.1), so this delegates to the
    canonical reader rather than ordering by ``id`` and hoping: the newest row is
    not necessarily the ``IN_USE`` one once a policy has been hidden or retired.
    """
    if not class_id:
        return None
    return get_rent_settings(class_id)


def _apply_change_list(class_id, changes, activation_mode, *, reference_time=None, canonical_context=None, actor_seat_id=None):
    """Apply policy changes to a class's economic configuration.

    Args:
        class_id: Class to apply changes to (canonical identifier)
        changes: List of change dictionaries from policy payload
        activation_mode: When to activate (REBALANCE_ACTIVATION_*)
        reference_time: Time of rebalance (for audit trail)

    Returns:
        Tuple of (applied_labels, applied_changes)

    Note: FeatureSettings.economy_last_rebalanced_* audit fields removed in Phase 2
    (table dropped; audit trail moves to EconomicEngine version history)
    """
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    applied_labels = []
    applied_changes: list[dict[str, Any]] = []

    for change in changes:
        change_type = change.get("type")
        if change_type == "rent":
            rent_settings = _get_effective_rent_settings(class_id)
            if rent_settings:
                # A rebalance is a policy submission like any other: it mints a new
                # immutable row rather than rewriting the live one, so rent already
                # assessed under the previous terms keeps its assessed amount
                # (DOM-POL-001 §VI.1). Only `rent_amount` changes; the rest of the
                # contract is carried forward by the Policies command.
                supersede_rent_settings(
                    class_id=class_id,
                    updates={"rent_amount": Decimal(str(change.get("new_value")))},
                )
                applied_labels.append("Rent")
                applied_changes.append(dict(change))
        elif change_type == "rent_late_penalty":
            rent_settings = _get_effective_rent_settings(class_id)
            if rent_settings:
                supersede_rent_settings(
                    class_id=class_id,
                    updates={"late_penalty_amount": Decimal(str(change.get("new_value")))},
                )
                applied_labels.append("Rent late penalty")
                applied_changes.append(dict(change))
        elif change_type == "store_item":
            product = StoreProduct.query.filter_by(
                class_id=class_id,
                product_lineage_uuid=change.get("product_lineage_uuid"),
                availability_state=store_service.IN_USE,
            ).first()
            if product is None:
                raise ValueError("Store product is no longer available for this class.")
            definition = {
                field: getattr(product, field)
                for field in store_service._DEFINITION_FIELDS
                if hasattr(product, field)
            }
            definition["price"] = Decimal(str(change.get("new_value")))
            # A replacement version is authored by whoever caused the
            # rebalance. Omitting the seat left every superseded product with a
            # null author, which INV-ARC-019 §VII makes a classroom fact
            # without an owner.
            store_service.supersede_product(
                current=product,
                definition=definition,
                actor_seat_id=actor_seat_id,
            )
            applied_labels.append(f"Store: {product.name}")
            applied_changes.append(dict(change))
        elif change_type == "overdraft_fee":
            # FEAT-CLASS-005 §XI: overdraft/NSF fees change only through the
            # Economic Engine evolution command. The rebalance already executes
            # inside FEAT-CLASS-005 and a nested FEAT context is forbidden, so
            # the command body is composed within the active context.
            if canonical_context is None:
                raise UnsupportedRebalanceChange(
                    "An overdraft fee change requires the acting teacher's canonical context."
                )
            from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
                _execute_evolve_economic_engine_impl,
            )
            from app.models import ClassFeature
            from app.services.class_configuration_query_service import is_feature_enabled

            result = _execute_evolve_economic_engine_impl.__wrapped__(
                canonical_context=canonical_context,
                class_id=class_id,
                updates={"flat_overdraft_fee": Decimal(str(change.get("new_value")))},
                feature_list=[
                    feature for feature in ClassFeature.feature_names()
                    if is_feature_enabled(class_id, feature)
                ],
            )
            if not result.success:
                raise ValueError(f"The overdraft fee could not be updated: {result.error_message}")
            applied_labels.append("Banking: Overdraft / NSF fee")
            applied_changes.append(dict(change))
        else:
            raise UnsupportedRebalanceChange(
                f"Rebalance change type {change_type!r} has no owning command."
            )

    return applied_labels, applied_changes


def _owner_for_change(change: dict[str, Any]) -> str:
    change_type = (change.get("type") or "").strip().lower()
    try:
        return _CHANGE_TYPE_OWNERS[change_type]
    except KeyError:
        raise UnsupportedRebalanceChange(
            f"Rebalance change type {change_type!r} has no owning command."
        ) from None


def apply_rebalance_changes(actor_seat_id, class_id, change_plan, activation_mode, *, reference_time=None, canonical_context=None):
    """Apply rebalance changes now, each through its owning command.

    Returns the applied change labels. The owning domains' rows are the whole
    record of the change; the rebalance keeps no lineage of its own.
    """
    for change in change_plan:
        _owner_for_change(change)
    applied_labels, _applied = _apply_change_list(
        class_id,
        change_plan,
        activation_mode,
        reference_time=ensure_utc(reference_time) if reference_time else utc_now(),
        canonical_context=canonical_context,
        actor_seat_id=actor_seat_id,
    )
    return applied_labels


def schedule_rebalance_changes(
    actor_seat_id: int,
    class_id: str,
    scheduled_changes: list[dict[str, Any]],
    *,
    reference_time: datetime | None = None,
) -> list[RentSettings]:
    """Record changes that take effect at the owning domain's next boundary.

    Only rent terms can wait for a boundary (store prices and the overdraft fee
    have none, FEAT-ECON-001 §VIII). The selected rent terms become one new
    ``rent_settings`` row — one contract, not one row per term — whose
    ``rent_effective_at`` is the start of the first rent period not yet issued.
    Every period already issued keeps the policy it froze, so the open period is
    billed under the old terms and the next period under the new ones
    (DOM-CLASS-003 §VII, DOM-OBL-001 §V.7). Runs inside the caller's FEAT;
    never commits. Returns the rows appended.
    """
    if not class_id:
        return []
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()

    updates: dict[str, Decimal] = {}
    effective_at: datetime | None = None
    for change in scheduled_changes:
        _owner_for_change(change)
        change_type = (change.get("type") or "").strip().lower()
        if change_type in IMMEDIATE_ONLY_CHANGE_TYPES:
            raise UnsupportedRebalanceChange(
                f"Rebalance change type {change_type!r} can only be applied immediately."
            )
        updates[_RENT_FIELDS[change_type]] = Decimal(str(change.get("new_value")))
        change_effective_at = _parse_dt(change.get("effective_at"))
        if change_effective_at is not None:
            effective_at = change_effective_at if effective_at is None else min(effective_at, change_effective_at)

    if not updates:
        return []
    if _get_effective_rent_settings(class_id) is None:
        raise ValueError("Rent is not configured for this class.")
    return [
        supersede_rent_settings(
            class_id=class_id,
            updates=updates,
            effective_at=max(effective_at or reference_time, reference_time),
        )
    ]


def get_pending_rebalance_effective_at(class_id: str | None, *, reference_time: datetime | None = None) -> datetime | None:
    """The soonest date a recorded economy change takes effect, or None.

    Pending changes live in their owning tables: a ``rent_settings`` row still
    selectable for new work whose ``rent_effective_at`` is ahead, and any
    ``economic_engine`` version whose ``effective_at`` is ahead (DOM-CLASS-003
    §X). Pure read (INV-ARC-007).
    """
    if not class_id:
        return None
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    candidates: list[datetime] = []
    rent = get_rent_settings(class_id)
    if rent is not None and rent.rent_effective_at is not None:
        rent_effective_at = ensure_utc(rent.rent_effective_at)
        if rent_effective_at > reference_time:
            candidates.append(rent_effective_at)
    candidates.extend(
        ensure_utc(engine.effective_at)
        for engine in pending_economic_engines(class_id, as_of=reference_time)
    )
    return min(candidates) if candidates else None


def has_pending_economy_change(class_id: str | None, *, reference_time: datetime | None = None) -> bool:
    return get_pending_rebalance_effective_at(class_id, reference_time=reference_time) is not None
