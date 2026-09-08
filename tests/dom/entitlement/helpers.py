"""Canonical helper surface for entitlement-domain tests.

The helpers in this module are intentionally narrow:
- one task per helper
- production FEAT-backed route calls or FEAT-wrapped production mutations only
- no ad hoc identity/session construction; use the canonical classroom initializer
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.services.store_service import IN_USE, set_product_visibility
from tests.helpers.store_products import publish_store_product
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import (
    initialize_as_student,
    initialize_as_teacher,
)


def login_entitlement_teacher(classroom_key: str, client, app):
    """Login as the canonical teacher for an entitlement test."""
    return initialize_as_teacher(classroom_key, client, app)


def login_entitlement_student(classroom_key: str, client, app, student_index: int = 0):
    """Login as the canonical student for an entitlement test."""
    return initialize_as_student(classroom_key, client, app, student_index=student_index)


def enable_store_feature_for_class(class_id: str) -> None:
    """Enable the store feature for a canonical class."""
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"entitlement:enable-store:{class_id}"):
        enable_class_feature(class_id=class_id, feature_name="store")
        db.session.info["feat_orchestrator_commit"] = True
        try:
            db.session.commit()
        finally:
            db.session.info.pop("feat_orchestrator_commit", None)


def set_entitlement_item_visibility(product_lineage_uuid: str, seat_ids: list[int]) -> None:
    """Replace visibility grants for one product.

    Visibility is keyed by lineage, not by version: hiding a product from a seat
    is a statement about the product, and it would be absurd for an edit to
    silently re-expose it.
    """
    with FEATContext("FEAT-STOR-001", idempotency_key=f"entitlement:set-visibility:{product_lineage_uuid}"):
        set_product_visibility(product_lineage_uuid, seat_ids)


def create_entitlement_store_item(
    *,
    teacher_id: int,
    class_id: str,
    name: str,
    price: Decimal,
    entitlement_type: str = "DELAYED_USE",
    availability_state: str = IN_USE,
    **definition,
):
    """Publish one live product version under the FEAT mutation boundary.

    Returns the detached snapshot ``publish_store_product`` produces, which
    carries both identifiers: ``policy_uuid`` (the version a purchase resolves
    against) and ``product_lineage_uuid`` (the product entitlement history and
    visibility key off).
    """
    with FEATContext("FEAT-STOR-001", idempotency_key=f"entitlement:create-item:{class_id}:{name}"):
        product = publish_store_product(
            class_id=class_id,
            entitlement_type=entitlement_type,
            user_id=teacher_id,
            name=name,
            price=str(price),
            availability_state=availability_state,
            **definition,
        )
        db.session.info["feat_orchestrator_commit"] = True
        try:
            db.session.commit()
        finally:
            db.session.info.pop("feat_orchestrator_commit", None)
        return product


def purchase_entitlement_item(client, *, policy_uuid: str, passphrase: str, quantity: int = 1, client_purchase_id: str | None = None):
    """Invoke the production purchase-item route."""
    payload = {
        "policy_uuid": policy_uuid,
        "passphrase": passphrase,
        "quantity": quantity,
    }
    if client_purchase_id is not None:
        payload["client_purchase_id"] = client_purchase_id
    return client.post("/api/purchase-item", json=payload)


def use_entitlement_item(client, *, entitlement_id: str, passphrase: str, details: str = ""):
    """Invoke the production use-item route."""
    return client.post(
        "/api/use-item",
        json={
            "entitlement_id": entitlement_id,
            "passphrase": passphrase,
            "details": details,
        },
    )


def approve_entitlement_redemption(client, *, entitlement_id: str):
    """Invoke the production approve-redemption route."""
    return client.post("/api/approve-redemption", json={"entitlement_id": entitlement_id})


def reject_entitlement_redemption(client, *, entitlement_id: str):
    """Invoke the production reject-redemption route."""
    return client.post("/api/reject-redemption", json={"entitlement_id": entitlement_id})
