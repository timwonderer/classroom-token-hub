"""Entitlement service — canonical hall pass balance via EntitlementEvent.

Hall pass balance is derived from the append-only EntitlementEvent log.
No seat-level counter column exists; every read is a live aggregate.
"""

from __future__ import annotations

import secrets

from app.extensions import db
from app.models import EntitlementEvent, Seat, StoreProduct
from app.feats.base import generate_correlation_id
from app.services.entitlement_read_service import (
    ended_entitlement_ids,
    entitlements_with_pending_action,
    get_entitlement_balance,
    get_entitlement_lineage_terminal_event,
    hall_pass_use_log,
)
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


def _current_utc():
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
    ).canonical_now_utc


def get_hall_pass_balance(seat_id: int, class_id: str) -> int:
    """Return the derived hall pass balance for a seat in a class."""
    return get_entitlement_balance(
        seat_id=seat_id,
        class_id=class_id,
        entitlement_type="HALL_PASS",
    )


def lock_hall_pass_holder(seat_id: int, class_id: str) -> Seat:
    """The one serialization point for every write that can end a hall pass.

    A pass ends by use (a hall-pass log, FEAT-PROD-002 §III) or by a REVOKED or
    EXPIRED event, and those live in different tables, so no index can stop an
    approval and a revocation from both ending the same pass. Every such writer
    takes this lock on the holder's seat row first and only then reads whether
    the pass is spent. It is the same row the attendance writers lock.
    """
    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).with_for_update().first()
    if seat is None:
        raise ValueError("Hall-pass holder must be a seat in the class.")
    return seat


def _generate_entitlement_id() -> str:
    return f"hpent_{secrets.token_urlsafe(16)}"


class HoldingLimitExceeded(ValueError):
    """A grant would leave the seat holding more of a product than its limit allows."""

    def __init__(self, *, holding_limit: int, on_hand: int, grant_quantity: int):
        self.holding_limit = holding_limit
        self.on_hand = on_hand
        self.grant_quantity = grant_quantity
        super().__init__(
            f"Granting {grant_quantity} would exceed the holding limit of "
            f"{holding_limit} ({on_hand} already held)"
        )


def get_active_holding_quantity(*, class_id: str, seat_id: int, product_lineage_uuid: str) -> int:
    """Count a seat's active entitlements for a product lineage, from every source.

    Possession is derived from immutable events: a GRANTED lineage with no
    CONSUMED, EXPIRED or REVOKED terminal event is still held.
    """
    return get_active_holding_quantities(
        class_id=class_id, seat_id=seat_id, product_lineage_uuids=[product_lineage_uuid]
    ).get(product_lineage_uuid, 0)


def get_active_holding_quantities(
    *, class_id: str, seat_id: int, product_lineage_uuids
) -> dict[str, int]:
    """``get_active_holding_quantity`` for many lineages in one query.

    Returns ``{product_lineage_uuid: held}``, omitting lineages the seat holds
    none of. One definition serves both, so a page listing many products and
    the purchase command cannot disagree about what a student holds.
    """
    lineages = [uuid for uuid in product_lineage_uuids if uuid]
    if not lineages:
        return {}
    events = EntitlementEvent.query.filter(
        EntitlementEvent.class_id == class_id,
        EntitlementEvent.target_seat_id == seat_id,
        EntitlementEvent.product_id.in_(lineages),
    ).all()
    # A used hall pass is ended by its log, not by an event (FEAT-PROD-002 §III).
    terminal = ended_entitlement_ids(
        class_id, {event.entitlement_id for event in events if event.event_type == "GRANTED"}
    )
    held: dict[str, int] = {}
    for event in events:
        if event.event_type == "GRANTED" and event.entitlement_id not in terminal:
            held[event.product_id] = held.get(event.product_id, 0) + 1
    return held


def ensure_within_holding_limit(
    *,
    class_id: str,
    seat_id: int,
    product_lineage_uuid: str | None,
    entitlement_type: str,
    holding_limit: int | None,
    grant_quantity: int,
) -> None:
    """Refuse a grant that would exceed the product's holding limit.

    The limit is source-independent (DOM-STORE-001 §VIII.A): purchase, teacher
    grant and rent perk all count toward it and all are bound by it. A grant
    that would exceed it is refused whole, never trimmed to fit (SPEC-STORE-001
    §V.A), and PRIVILEGE is hard-set to one. The caller must hold the target
    seat's row lock so the count cannot race a concurrent grant.
    """
    # PRIVILEGE is hard-set to one; so is COLLECTIVE_GOAL, one buy-in per
    # student (owner ruling 2026-10-07).
    limit = 1 if entitlement_type in {"PRIVILEGE", "COLLECTIVE_GOAL"} else holding_limit
    if limit is None or not product_lineage_uuid:
        return
    on_hand = get_active_holding_quantity(
        class_id=class_id, seat_id=seat_id, product_lineage_uuid=product_lineage_uuid
    )
    if on_hand + grant_quantity > limit:
        raise HoldingLimitExceeded(
            holding_limit=limit, on_hand=on_hand, grant_quantity=grant_quantity
        )


def _ensure_product_holding_limit(
    seat: Seat,
    *,
    entitlement_type: str,
    product_lineage_uuid: str | None,
    policy_uuid: str | None,
    grant_quantity: int,
) -> None:
    """Apply the holding limit of the exact product version being granted."""
    if not product_lineage_uuid or not policy_uuid:
        return
    holding_limit = (
        db.session.query(StoreProduct.holding_limit)
        .filter_by(class_id=seat.class_id, policy_uuid=policy_uuid)
        .scalar()
    )
    ensure_within_holding_limit(
        class_id=seat.class_id,
        seat_id=seat.id,
        product_lineage_uuid=product_lineage_uuid,
        entitlement_type=entitlement_type,
        holding_limit=holding_limit,
        grant_quantity=grant_quantity,
    )


def grant_hall_passes(
    seat: Seat,
    quantity: int,
    *,
    actor_seat_id: int | None = None,
    trigger_id: str | None = None,
    correlation_id: str | None = None,
    acquisition_type: str = "GRANT",
    product_lineage_uuid: str | None = None,
    policy_uuid: str | None = None,
) -> int:
    """Grant hall passes by appending one EntitlementEvent per pass.

    Per DOM-STORE-001 §VII and FEAT-STOR-001 §VII.B: one event per unit,
    same correlation_id across the batch.

    Args:
        seat: Target seat receiving passes.
        quantity: Number of passes to grant (must be positive).
        actor_seat_id: Seat performing the action. Defaults to target seat.
        trigger_id: Optional trigger identifier for payload lineage.
        correlation_id: Cross-domain lineage ID. Generated if not provided.
        acquisition_type: GRANT (teacher direct), PURCHASE, or PERK (rent).
        product_lineage_uuid: Store product the passes came from, when the
            grant originates from a catalog item. DOM-STORE-001 §VII.A wants a
            product on every entitlement; a bare teacher-issued pass has none,
            so this stays optional.
        policy_uuid: The exact product version, frozen into the payload so the
            terms can be recovered after the teacher edits the product.
    """
    _VALID_ACQUISITION_TYPES = ("GRANT", "PURCHASE", "PERK")
    if acquisition_type not in _VALID_ACQUISITION_TYPES:
        raise ValueError(f"acquisition_type must be one of {_VALID_ACQUISITION_TYPES}")

    grant_quantity = int(quantity)
    if grant_quantity <= 0:
        raise ValueError("Hall-pass grant quantity must be positive")
    _ensure_product_holding_limit(
        seat,
        entitlement_type="HALL_PASS",
        product_lineage_uuid=product_lineage_uuid,
        policy_uuid=policy_uuid,
        grant_quantity=grant_quantity,
    )

    now = _current_utc()
    grant_correlation_id = correlation_id or generate_correlation_id()
    resolved_actor = actor_seat_id if actor_seat_id is not None else seat.id
    for index in range(grant_quantity):
        entitlement_id = _generate_entitlement_id()
        event = EntitlementEvent(
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=resolved_actor,
            entitlement_id=entitlement_id,
            product_id=product_lineage_uuid,
            entitlement_type="HALL_PASS",
            acquisition_type=acquisition_type,
            event_type="GRANTED",
            correlation_id=grant_correlation_id,
            payload={
                "source": "grant_hall_passes",
                "trigger_id": f"{trigger_id}:{index + 1}" if trigger_id else entitlement_id,
                **({"policy_uuid": policy_uuid} if policy_uuid else {}),
            },
            timestamp=now,
        )
        db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


_STORE_GRANT_ENTITLEMENT_TYPES = ("IMMEDIATE_USE", "DELAYED_USE", "PRIVILEGE")


def grant_store_entitlements(
    seat: Seat,
    quantity: int,
    *,
    entitlement_type: str,
    product_lineage_uuid: str,
    policy_uuid: str,
    actor_seat_id: int | None = None,
    trigger_id: str | None = None,
    correlation_id: str | None = None,
    acquisition_type: str = "GRANT",
) -> list[str]:
    """Grant non-hall-pass store entitlements without a purchase.

    Used when a student receives a catalog item for a reason other than buying
    it — today, satisfying rent. Per FEAT-STOR-001 §VII.E each unit is its own
    entitlement lifecycle, so ``quantity`` units produce ``quantity`` rows
    sharing one ``correlation_id``; the count is then derivable and is
    deliberately not stored (DOM-STORE-001 §VII.A).

    Hall passes keep their own function because their balance is derived by a
    dedicated reader.

    Returns the entitlement ids created.
    """
    if entitlement_type not in _STORE_GRANT_ENTITLEMENT_TYPES:
        raise ValueError(
            f"entitlement_type must be one of {_STORE_GRANT_ENTITLEMENT_TYPES}"
        )
    if acquisition_type not in ("GRANT", "PURCHASE", "PERK"):
        raise ValueError("acquisition_type must be one of ('GRANT', 'PURCHASE', 'PERK')")
    if not product_lineage_uuid:
        raise ValueError("product_lineage_uuid is required for store entitlements")

    grant_quantity = int(quantity)
    if grant_quantity <= 0:
        raise ValueError("Entitlement grant quantity must be positive")
    _ensure_product_holding_limit(
        seat,
        entitlement_type=entitlement_type,
        product_lineage_uuid=product_lineage_uuid,
        policy_uuid=policy_uuid,
        grant_quantity=grant_quantity,
    )

    now = _current_utc()
    grant_correlation_id = correlation_id or generate_correlation_id()
    resolved_actor = actor_seat_id if actor_seat_id is not None else seat.id

    entitlement_ids = []
    for index in range(grant_quantity):
        entitlement_id = _generate_entitlement_id()
        entitlement_ids.append(entitlement_id)
        db.session.add(
            EntitlementEvent(
                class_id=seat.class_id,
                target_seat_id=seat.id,
                actor_seat_id=resolved_actor,
                entitlement_id=entitlement_id,
                product_id=product_lineage_uuid,
                entitlement_type=entitlement_type,
                acquisition_type=acquisition_type,
                event_type="GRANTED",
                correlation_id=grant_correlation_id,
                payload={
                    "source": "grant_store_entitlements",
                    "policy_uuid": policy_uuid,
                    "trigger_id": (
                        f"{trigger_id}:{index + 1}" if trigger_id else entitlement_id
                    ),
                },
                timestamp=now,
            )
        )
    db.session.flush()
    return entitlement_ids


def grant_insurance_entitlement(
    seat: Seat,
    policy_uuid: str,
    *,
    actor_seat_id: int | None = None,
    correlation_id: str | None = None,
    granted_at=None,
) -> str:
    """Grant one INSURANCE coverage entitlement (acquisition_type=PURCHASE).

    ``granted_at`` is the purchase instant the coordinating FEAT resolved
    canonically (the start of the first coverage period, DOM-STORE-001
    §VIII.E.1); omitted, the canonical current time.

    The immutable insurance definition is referenced by ``policy_uuid`` carried in
    the event payload — ``EntitlementEvent.product_id`` names a *store* product
    lineage and is not used for insurance. Policy terms are retrieved later by resolving that
    ``policy_uuid`` (the row is immutable), never snapshotted into the payload
    (DOM-STORE-001 §VII.A forbids duplicating policy rules).

    Idempotent on ``correlation_id``: a replay of the same purchase returns the
    existing grant's ``entitlement_id`` rather than writing a second grant.

    Returns the entitlement_id of the coverage grant.
    """
    if not policy_uuid:
        raise ValueError("grant_insurance_entitlement requires a policy_uuid")

    grant_correlation_id = correlation_id or generate_correlation_id()
    resolved_actor = actor_seat_id if actor_seat_id is not None else seat.id

    existing = (
        EntitlementEvent.query
        .filter_by(
            class_id=seat.class_id,
            target_seat_id=seat.id,
            entitlement_type="INSURANCE",
            event_type="GRANTED",
            correlation_id=grant_correlation_id,
        )
        .first()
    )
    if existing is not None:
        return existing.entitlement_id

    entitlement_id = _generate_entitlement_id()
    event = EntitlementEvent(
        class_id=seat.class_id,
        target_seat_id=seat.id,
        actor_seat_id=resolved_actor,
        entitlement_id=entitlement_id,
        product_id=None,
        entitlement_type="INSURANCE",
        acquisition_type="PURCHASE",
        event_type="GRANTED",
        correlation_id=grant_correlation_id,
        payload={
            "source": "grant_insurance_entitlement",
            "policy_uuid": policy_uuid,
        },
        timestamp=granted_at or _current_utc(),
    )
    db.session.add(event)
    db.session.flush()
    return entitlement_id


def remove_hall_passes(
    seat: Seat,
    quantity: int,
) -> int:
    """Remove available hall passes by appending REVOKED events.

    Reuses the entitlement_id from the grant being revoked to maintain
    lineage per DOM-STORE-001 §VII.
    """
    quantity_to_remove = int(quantity or 0)
    if quantity_to_remove <= 0:
        raise ValueError("Hall-pass removal quantity must be positive")

    lock_hall_pass_holder(seat.id, seat.class_id)
    current_balance = get_hall_pass_balance(seat.id, seat.class_id)
    if quantity_to_remove > current_balance:
        raise ValueError("Cannot remove more hall passes than the current available balance")

    remaining = quantity_to_remove
    while remaining:
        grant = _available_hall_pass_grant(seat.id, seat.class_id)
        if grant is None:
            break
        event = EntitlementEvent(
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            entitlement_id=grant.entitlement_id,
            product_id=grant.product_id,
            entitlement_type="HALL_PASS",
            acquisition_type=grant.acquisition_type,
            event_type="REVOKED",
            correlation_id=grant.correlation_id,
            payload={
                "source": "remove_hall_passes",
            },
            timestamp=_current_utc(),
        )
        db.session.add(event)
        db.session.flush()
        remaining -= 1

    if remaining:
        # The balance counts a pass with a request waiting, but such a pass
        # cannot be removed until the request is resolved (owner ruling
        # 2026-10-09). The whole removal rolls back.
        raise ValueError(
            "Cannot remove that many hall passes: a pass with a request waiting can't be "
            "removed until the request is approved or rejected"
        )

    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def _available_hall_pass_grant(seat_id: int, class_id: str) -> EntitlementEvent | None:
    """Find the oldest exercisable hall pass grant (FIFO)."""
    grants = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_type == "HALL_PASS",
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.entitlement_id.isnot(None),
        )
        .order_by(EntitlementEvent.timestamp.asc(), EntitlementEvent.event_id.asc())
        .all()
    )
    ids = [grant.entitlement_id for grant in grants]
    # A pass named by a waiting request is reserved for it (owner ruling
    # 2026-10-09): only that request's approval or rejection resolves it.
    unavailable = ended_entitlement_ids(class_id, ids) | entitlements_with_pending_action(class_id, ids)
    for grant in grants:
        if grant.entitlement_id not in unavailable:
            return grant
    return None


def get_available_hall_pass_grant(seat_id: int, class_id: str) -> EntitlementEvent | None:
    """Return the oldest usable hall pass (FIFO), writing nothing.

    Approval uses the pass by naming it in ``hall_pass_logs.hall_pass_id``
    (FEAT-PROD-002 §III); no entitlement event is written for the use.
    """
    return _available_hall_pass_grant(seat_id, class_id)


def consume_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    product_id: int | None,
    entitlement_type: str,
    acquisition_type: str,
    correlation_id: str,
    payload: dict | None = None,
) -> EntitlementEvent:
    """Record a CONSUMED terminal event for a generic entitlement.

    Per DOM-STORE-001 §VIII: terminal events reuse the grant's entitlement_id
    to preserve lineage. Caller must verify no terminal event already exists
    (enforced by ix_entitlement_events_one_terminal_per_lineage).

    This is the canonical write path for non-hall-pass consumption
    (store items, privileges, etc.). A hall pass is never consumed here: its
    use is the hall-pass log (FEAT-PROD-002 §III), and this refuses a pass
    that a log already names.
    """
    if entitlement_type == "HALL_PASS":
        lock_hall_pass_holder(target_seat_id, class_id)
        if entitlements_with_pending_action(class_id, [entitlement_id]):
            raise ValueError(f"Hall pass {entitlement_id} has a request waiting and cannot be ended")
    terminal = get_entitlement_lineage_terminal_event(entitlement_id, class_id)
    if terminal is not None:
        raise ValueError(
            f"Entitlement {entitlement_id} already has terminal event: "
            f"{terminal.event_type}"
        )
    if hall_pass_use_log(entitlement_id, class_id) is not None:
        raise ValueError(f"Entitlement {entitlement_id} is a hall pass already used")

    now = _current_utc()
    event = EntitlementEvent(
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        entitlement_id=entitlement_id,
        product_id=product_id,
        entitlement_type=entitlement_type,
        acquisition_type=acquisition_type,
        event_type="CONSUMED",
        correlation_id=correlation_id,
        payload=payload,
        timestamp=now,
    )
    db.session.add(event)
    db.session.flush()
    return event


def expire_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    product_id: int | None,
    entitlement_type: str,
    acquisition_type: str,
    correlation_id: str,
    payload: dict | None = None,
    effective_at=None,
) -> EntitlementEvent:
    """Record an EXPIRED terminal event for an entitlement (FEAT-STOR-002 §VIII/§XV).

    ``effective_at`` is the lawful boundary the expiry takes effect at (an
    insurance termination instant or nonpayment deadline, which a scheduled job
    may reach late); the event is stamped with it so usability "at or before a
    reference time" reads the boundary, not the moment the job ran. Omitted,
    the canonical current time.

    Expiration is the lawful terminal disposition when a coverage/validity boundary
    has been reached. Proving the boundary was reached is the caller's
    responsibility (FEAT-STOR-002 §VIII) — this command performs the write. Reuses
    the grant's ``entitlement_id`` to preserve lineage; exactly one terminal event
    per lineage (DOM-STORE-001 §VIII).

    For insurance this is the ONLY lawful terminal disposition — coverage is never
    revoked or refunded (FEAT-STOR-002 §IX.C); it expires at its boundary.

    Idempotent: an already-EXPIRED lineage returns its existing event. A conflicting
    terminal disposition (e.g. REVOKED) fails closed.
    """
    if entitlement_type == "HALL_PASS":
        lock_hall_pass_holder(target_seat_id, class_id)
        if entitlements_with_pending_action(class_id, [entitlement_id]):
            raise ValueError(f"Hall pass {entitlement_id} has a request waiting and cannot be ended")
    existing = get_entitlement_lineage_terminal_event(entitlement_id, class_id)
    if existing is not None:
        if existing.event_type == "EXPIRED":
            return existing  # idempotent replay
        raise ValueError(
            f"Entitlement {entitlement_id} already has terminal event: "
            f"{existing.event_type}"
        )
    if hall_pass_use_log(entitlement_id, class_id) is not None:
        raise ValueError(f"Entitlement {entitlement_id} is a hall pass already used")

    now = effective_at or _current_utc()
    event = EntitlementEvent(
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        entitlement_id=entitlement_id,
        product_id=product_id,
        entitlement_type=entitlement_type,
        acquisition_type=acquisition_type,
        event_type="EXPIRED",
        correlation_id=correlation_id,
        payload=payload,
        timestamp=now,
    )
    db.session.add(event)
    db.session.flush()
    return event


def revoke_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    product_id: int | None,
    entitlement_type: str,
    acquisition_type: str,
    correlation_id: str,
    payload: dict | None = None,
) -> EntitlementEvent:
    """Record a REVOKED terminal event for an entitlement.

    This command performs the write only; the caller establishes that the
    revocation is lawful. One terminal event per lineage (DOM-STORE-001
    §VIII), so a lineage that already terminated fails closed.
    """
    if entitlement_type == "HALL_PASS":
        lock_hall_pass_holder(target_seat_id, class_id)
        if entitlements_with_pending_action(class_id, [entitlement_id]):
            raise ValueError(f"Hall pass {entitlement_id} has a request waiting and cannot be ended")
    terminal = get_entitlement_lineage_terminal_event(entitlement_id, class_id)
    if terminal is not None:
        raise ValueError(
            f"Entitlement {entitlement_id} already has terminal event: "
            f"{terminal.event_type}"
        )
    if hall_pass_use_log(entitlement_id, class_id) is not None:
        raise ValueError(f"Entitlement {entitlement_id} is a hall pass already used")

    event = EntitlementEvent(
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        entitlement_id=entitlement_id,
        product_id=product_id,
        entitlement_type=entitlement_type,
        acquisition_type=acquisition_type,
        event_type="REVOKED",
        correlation_id=correlation_id,
        payload=payload,
        timestamp=_current_utc(),
    )
    db.session.add(event)
    db.session.flush()
    return event


def expire_rent_perks(
    *,
    correlation_id: str,
    class_id: str,
    actor_seat_id: int,
) -> int:
    """Expire every perk granted for a rent obligation at its cycle boundary.

    DOM-OBL-001 §IX.9: at a rent boundary, previously granted rent perks expire
    regardless of whether the policy UUID stays the same. DOM-STORE-001 states
    the same for every rent-granted entitlement, and SPEC-STORE-001 §V.A derives
    a rent-linked entitlement's expiration from the rent cycle for every
    rent-linkable type, not only hall passes.

    Finds all active PERK grants sharing the correlation_id from the rent
    obligation and writes EXPIRED events for each.

    Returns the count of entitlements expired.
    """
    # Hall passes among the perks: lock their holders first, in seat order, so
    # an approval that would use one of them waits or is waited on.
    holder_ids = sorted({
        row[0]
        for row in db.session.query(EntitlementEvent.target_seat_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.correlation_id == correlation_id,
            EntitlementEvent.acquisition_type == "PERK",
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.entitlement_type == "HALL_PASS",
        )
        .distinct()
        .all()
    })
    for holder_id in holder_ids:
        lock_hall_pass_holder(holder_id, class_id)

    # Lock grant rows to serialize concurrent expiration attempts (FOR UPDATE).
    grants = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.correlation_id == correlation_id,
            EntitlementEvent.acquisition_type == "PERK",
            EntitlementEvent.event_type == "GRANTED",
        )
        .with_for_update()
        .all()
    )

    now = _current_utc()
    expired_count = 0
    ids = [grant.entitlement_id for grant in grants]
    # A used pass is already spent, and a pass with a request waiting cannot be
    # removed while it waits (owner ruling 2026-10-09); expiry skips both.
    ended = ended_entitlement_ids(class_id, ids) | entitlements_with_pending_action(class_id, ids)
    for grant in grants:
        # A used pass is already spent; expiring it would end it twice.
        if grant.entitlement_id in ended:
            continue
        event = EntitlementEvent(
            class_id=class_id,
            target_seat_id=grant.target_seat_id,
            actor_seat_id=actor_seat_id,
            entitlement_id=grant.entitlement_id,
            product_id=grant.product_id,
            entitlement_type=grant.entitlement_type,
            acquisition_type="PERK",
            event_type="EXPIRED",
            correlation_id=correlation_id,
            payload={
                "source": "expire_rent_perks",
            },
            timestamp=now,
        )
        db.session.add(event)
        expired_count += 1

    if expired_count:
        db.session.flush()
    return expired_count
