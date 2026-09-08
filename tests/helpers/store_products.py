"""
Store product test helper.

Tests used to build catalog rows by handing a JSON payload to
``StorePolicyResolver.create_store_product``. That path is gone: a product is
now one typed, versioned row published through
``app.services.store_service.publish_product``.

This helper exists so tests keep speaking the domain vocabulary they assert in
(``entitlement_type``) while writing the column the catalog actually stores
(``item_type``). It is a thin adapter over the production publisher — it does
not construct a StoreProduct itself.

Two identifiers come back on the returned row and mixing them up is the usual
mistake:

* ``policy_uuid`` — the version. Purchases and grants resolve against it.
* ``product_lineage_uuid`` — the product. This is what ``StorePolicyConfig``
  exposes as ``product_id``, and what entitlement history keys off.

Must be called inside an active FEAT context, like the production publisher.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.models import Seat
from app.services import store_service
from app.services.store_policy_resolver import StorePolicyResolver


@dataclass(frozen=True)
class PublishedProduct:
    """A detached snapshot of a published version.

    Fixtures routinely hand their result across an ``app_context`` boundary,
    and a live ORM row raises ``DetachedInstanceError`` the moment a test
    touches an attribute on the far side. Returning plain values instead makes
    that whole class of fixture breakage impossible; a test that genuinely
    needs the row queries it by ``policy_uuid``.
    """

    policy_uuid: str
    product_lineage_uuid: str
    class_id: str
    name: str
    price: Decimal
    item_type: str


# Domain vocabulary (what SPEC-STORE-001 validates) → catalog vocabulary (what
# the teacher-facing column stores). Inverted from the resolver's own map so the
# two cannot drift apart.
ENTITLEMENT_TYPE_TO_ITEM_TYPE = {
    entitlement_type: item_type
    for item_type, entitlement_type in
    StorePolicyResolver._ITEM_TYPE_TO_ENTITLEMENT_TYPE.items()
}


def publish_store_product(
    *,
    class_id: str,
    entitlement_type: str,
    created_by_seat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    name: Optional[str] = None,
    price: str = "0.00",
    availability_state: str = store_service.IN_USE,
    product_lineage_uuid: Optional[str] = None,
    **definition,
) -> PublishedProduct:
    """Publish one live product version and return a snapshot of it.

    ``user_id`` is derived from ``created_by_seat_id`` when omitted, because
    every caller already has the acting seat and the owning user is a property
    of that seat rather than an independent fact a test should restate.
    """
    try:
        item_type = ENTITLEMENT_TYPE_TO_ITEM_TYPE[entitlement_type]
    except KeyError:
        raise ValueError(
            f"Unknown entitlement_type {entitlement_type!r}; "
            f"expected one of {sorted(ENTITLEMENT_TYPE_TO_ITEM_TYPE)}"
        ) from None

    if user_id is None:
        if created_by_seat_id is None:
            raise ValueError("publish_store_product needs user_id or created_by_seat_id")
        seat = db_seat(created_by_seat_id)
        user_id = seat.user_id

    product = store_service.publish_product(
        user_id=user_id,
        class_id=class_id,
        definition={
            "name": name or f"Test {item_type} item",
            "price": price,
            "item_type": item_type,
            **definition,
        },
        product_lineage_uuid=product_lineage_uuid,
        availability_state=availability_state,
        actor_seat_id=created_by_seat_id,
    )
    return PublishedProduct(
        policy_uuid=product.policy_uuid,
        product_lineage_uuid=product.product_lineage_uuid,
        class_id=product.class_id,
        name=product.name,
        price=Decimal(str(product.price)),
        item_type=product.item_type,
    )


def db_seat(seat_id: int) -> Seat:
    seat = Seat.query.get(seat_id)
    if seat is None:
        raise LookupError(f"Seat {seat_id} does not exist")
    return seat
