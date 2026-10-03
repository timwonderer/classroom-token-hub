"""Read side of store redemption requests (DOM-STORE-001 §VII.B, §VIII.E.4).

A redemption request lives in two places over its life, and this module is the
one reader that knows both:

* **Waiting** — an unresolved ``pending_actions`` row under ``FEAT-STOR-002``.
  It holds what the student submitted and nothing else.
* **Decided** — the durable entitlement event the decision wrote: ``CONSUMED``
  for an approval, ``REVOKED`` for a denial (DOM-STORE-001 §VIII.E.4). A
  returned request writes nothing and leaves no record.
  §VII.B requires resolution to write that record and delete the pending row,
  so once decided, the event is the only place the request exists. Its payload
  carries the request facts the decision needs to stay readable (the student's
  note, when it was submitted).

Requests resolved before resolution deleted the row are still on file as
pending rows stamped with an ``outcome``. They are read here as decided, so the
history does not silently lose them; nothing new is written that way.

Everything here is a pure read and safe from a GET handler (INV-ARC-007).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import joinedload

from app.models import EntitlementEvent, PendingAction, Seat, Transaction
from app.services import store_service
from app.utils.canonical_temporal_resolver import ensure_utc

REDEMPTION_FEAT = "FEAT-STOR-002"

# Payload ``source`` values the redemption decisions write. The approve value is
# the one approvals have always carried, so earlier CONSUMED rows are found too.
APPROVAL_SOURCE = "api.approve_redemption"
DENIAL_SOURCE = "redemption_denial"
DECISION_SOURCES = (APPROVAL_SOURCE, DENIAL_SOURCE)

# Immediate-use purchases also queue a FEAT-STOR-002 pending action, as a
# reminder rather than a request (DOM-STORE-001 §VIII.E.3). A redemption
# request carries no ``kind``; everything below keeps the two apart.
ACKNOWLEDGEMENT_KIND = "immediate_use_acknowledgement"

APPROVED = "APPROVED"
DENIED = "DENIED"

@dataclass(frozen=True)
class RedemptionRequestView:
    """One redemption request, waiting or decided, as the teacher reads it."""

    request_id: str
    entitlement_id: str
    seat_id: int
    student_name: str
    item_name: str
    item_description: str | None
    redemption_prompt: str | None
    student_note: str | None
    acquisition_type: str
    purchased_at: datetime | None
    price_paid: Decimal | None
    units_in_purchase: int
    bundle_size: int
    submitted_at: datetime | None
    # Decided requests only.
    outcome: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    is_legacy: bool = False
    # An immediate-use purchase's reminder rather than a redemption request.
    is_acknowledgement: bool = False

    @property
    def is_pending(self) -> bool:
        return self.outcome is None


def _covering_purchase(grant: EntitlementEvent) -> Transaction | None:
    """The purchase transaction that paid for this grant.

    Matched on correlation, class, seat and type together, the same join the
    collective-goal refund uses: correlation alone is a shared key, not a
    promise of scope.
    """
    if grant.acquisition_type != "PURCHASE" or not grant.correlation_id:
        return None
    return (
        Transaction.query.filter(
            Transaction.correlation_id == grant.correlation_id,
            Transaction.class_id == grant.class_id,
            Transaction.seat_id == grant.target_seat_id,
            Transaction.type == "purchase",
        )
        .order_by(Transaction.id.asc())
        .first()
    )


def _units_in_purchase(grant: EntitlementEvent) -> int:
    """How many entitlements the purchase behind this grant produced.

    A bundle, or a quantity above one, is several lifecycles under one charge
    (``store_purchase_feat``).
    """
    if grant.acquisition_type != "PURCHASE" or not grant.correlation_id:
        return 1
    return (
        EntitlementEvent.query.filter(
            EntitlementEvent.class_id == grant.class_id,
            EntitlementEvent.target_seat_id == grant.target_seat_id,
            EntitlementEvent.correlation_id == grant.correlation_id,
            EntitlementEvent.event_type == "GRANTED",
        ).count()
        or 1
    )


def _bundle_size(grant: EntitlementEvent) -> int:
    """Uses per purchase of the product version this grant was bought under.

    Read the way the purchase read it (``store_policy_resolver``): a bundle
    size counts only on a product marked as a bundle.
    """
    product = store_service.resolve_entitlement_product(grant)
    if product is None or not product.is_bundle:
        return 1
    return max(1, int(product.bundle_quantity or 1))


def _student_names(seat_ids: set[int]) -> dict[int, str]:
    if not seat_ids:
        return {}
    seats = (
        Seat.query.options(joinedload(Seat.identity_profile))
        .filter(Seat.id.in_(seat_ids))
        .all()
    )
    return {
        seat.id: (seat.identity_profile.full_name if seat.identity_profile else "Unknown student")
        for seat in seats
    }


def _grants_by_entitlement(class_id: str, entitlement_ids: set[str]) -> dict[str, EntitlementEvent]:
    if not entitlement_ids:
        return {}
    grants = EntitlementEvent.query.filter(
        EntitlementEvent.class_id == class_id,
        EntitlementEvent.entitlement_id.in_(entitlement_ids),
        EntitlementEvent.event_type == "GRANTED",
    ).all()
    latest: dict[str, EntitlementEvent] = {}
    for grant in grants:
        held = latest.get(grant.entitlement_id)
        if held is None or grant.timestamp > held.timestamp:
            latest[grant.entitlement_id] = grant
    return latest


def _parse_instant(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    try:
        return ensure_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def _base_fields(grant: EntitlementEvent | None, *, names, seat_id: int) -> dict:
    product = store_service.resolve_entitlement_product(grant) if grant is not None else None
    transaction = _covering_purchase(grant) if grant is not None else None
    return {
        "seat_id": seat_id,
        "student_name": names.get(seat_id, "Unknown student"),
        "item_name": product.name if product else "Store item",
        "item_description": (product.description or None) if product else None,
        "redemption_prompt": (product.redemption_prompt or None) if product else None,
        "acquisition_type": grant.acquisition_type if grant is not None else "PURCHASE",
        "purchased_at": grant.timestamp if grant is not None else None,
        "price_paid": abs(Decimal(transaction.amount or 0)) if transaction is not None else None,
        "units_in_purchase": _units_in_purchase(grant) if grant is not None else 1,
        "bundle_size": _bundle_size(grant) if grant is not None else 1,
    }


def _waiting_requests(class_id: str):
    return PendingAction.query.filter(
        PendingAction.class_id == class_id,
        PendingAction.authoritative_feat == REDEMPTION_FEAT,
        PendingAction.payload["outcome"].as_string().is_(None),
        PendingAction.payload["kind"].as_string().is_(None),
    )


def get_pending_redemption_count(class_id: str) -> int:
    return _waiting_requests(class_id).count()


def list_pending_redemptions(class_id: str) -> list[RedemptionRequestView]:
    """Every request in the class still waiting for a decision, oldest first.

    Oldest first because that is the order a fair queue is worked in.
    """
    rows = (
        _waiting_requests(class_id)
        .order_by(PendingAction.submitted_at.asc(), PendingAction.pending_action_id.asc())
        .all()
    )
    grants = _grants_by_entitlement(class_id, {row.entitlement_id for row in rows})
    names = _student_names({row.seat_id for row in rows})

    views = []
    for row in rows:
        grant = grants.get(row.entitlement_id)
        # A request whose seat is not in this class, or whose entitlement has
        # no grant here, is not this class's to decide.
        if grant is None or grant.target_seat_id != row.seat_id:
            continue
        payload = row.payload or {}
        views.append(RedemptionRequestView(
            request_id=row.pending_action_id,
            entitlement_id=row.entitlement_id,
            student_note=(payload.get("details") or "").strip() or None,
            submitted_at=row.submitted_at,
            **_base_fields(grant, names=names, seat_id=row.seat_id),
        ))
    return views


def list_resolved_redemptions(class_id: str, *, limit: int = 100) -> list[RedemptionRequestView]:
    """The class's decided requests, most recently decided first."""
    events = (
        EntitlementEvent.query.filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type.in_(("CONSUMED", "REVOKED")),
            EntitlementEvent.payload["source"].as_string().in_(DECISION_SOURCES),
        )
        .order_by(EntitlementEvent.timestamp.desc(), EntitlementEvent.event_id.desc())
        .limit(limit)
        .all()
    )
    legacy = (
        PendingAction.query.filter(
            PendingAction.class_id == class_id,
            PendingAction.authoritative_feat == REDEMPTION_FEAT,
            PendingAction.payload["outcome"].as_string().isnot(None),
        )
        .order_by(PendingAction.submitted_at.desc())
        .limit(limit)
        .all()
    )

    grants = _grants_by_entitlement(
        class_id,
        {event.entitlement_id for event in events} | {row.entitlement_id for row in legacy},
    )
    names = _student_names(
        {event.target_seat_id for event in events} | {row.seat_id for row in legacy}
    )

    views = []
    for event in events:
        payload = event.payload or {}
        approved = event.event_type == "CONSUMED"
        views.append(RedemptionRequestView(
            request_id=payload.get("pending_action_id") or event.event_id,
            entitlement_id=event.entitlement_id,
            student_note=(payload.get("details") or "").strip() or None,
            submitted_at=_parse_instant(payload.get("request_submitted_at")),
            outcome=APPROVED if approved else DENIED,
            decided_at=event.timestamp,
            decision_note=(payload.get("decision_note") or "").strip() or None,
            **_base_fields(grants.get(event.entitlement_id), names=names, seat_id=event.target_seat_id),
        ))

    # Approvals already wrote a CONSUMED event that the query above found, so a
    # legacy row adds something only when it is the sole record: a rejection.
    for row in legacy:
        payload = row.payload or {}
        if payload.get("outcome") != "REJECTED":
            continue
        views.append(RedemptionRequestView(
            request_id=row.pending_action_id,
            entitlement_id=row.entitlement_id,
            student_note=(payload.get("details") or "").strip() or None,
            submitted_at=row.submitted_at,
            outcome=DENIED,
            decided_at=_parse_instant(payload.get("resolved_at")) or row.submitted_at,
            is_legacy=True,
            **_base_fields(grants.get(row.entitlement_id), names=names, seat_id=row.seat_id),
        ))

    _earliest = datetime.min.replace(tzinfo=timezone.utc)
    views.sort(key=lambda view: ensure_utc(view.decided_at) if view.decided_at else _earliest, reverse=True)
    return views[:limit]



def list_pending_acknowledgements(class_id: str) -> list[RedemptionRequestView]:
    """Immediate-use purchases waiting for the teacher to mark them complete.

    Oldest first. The entitlement is already ``CONSUMED``; the row only reminds
    the teacher to deliver the item (DOM-STORE-001 §VIII.E.3).
    """
    rows = (
        PendingAction.query.filter(
            PendingAction.class_id == class_id,
            PendingAction.authoritative_feat == REDEMPTION_FEAT,
            PendingAction.payload["kind"].as_string() == ACKNOWLEDGEMENT_KIND,
        )
        .order_by(PendingAction.submitted_at.asc(), PendingAction.pending_action_id.asc())
        .all()
    )
    grants = _grants_by_entitlement(class_id, {row.entitlement_id for row in rows})
    names = _student_names({row.seat_id for row in rows})
    views = []
    for row in rows:
        grant = grants.get(row.entitlement_id)
        if grant is None or grant.target_seat_id != row.seat_id:
            continue
        views.append(RedemptionRequestView(
            request_id=row.pending_action_id,
            entitlement_id=row.entitlement_id,
            student_note=None,
            submitted_at=row.submitted_at,
            is_acknowledgement=True,
            **_base_fields(grant, names=names, seat_id=row.seat_id),
        ))
    return views
