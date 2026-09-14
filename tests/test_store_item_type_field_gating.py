"""Item-type field gating on the two admin store item forms.

A teacher could previously configure a bundle on an immediate-use item, or a
bulk discount on a collective goal. ``_validate_definition`` rejects those on
submit (SPEC-STORE-001 §V.A), so the whole save failed with no indication of
which control was the illegal one.

The forms ship a server-resolved state-contract catalogue. The browser may
select a contract during interaction, but it does not define legality.
"""

import json
import re

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.services import store_service
from app.services.store.form_contract import contract_payload
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]

RULE_NAMES = {"multi_unit", "bulk_discountable", "expiring", "collective", "rent_linkable", "promptable"}


def _contracts_payload(body):
    match = re.search(
        r'<script id="storeFormContracts" type="application/json">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, "form does not ship the resolved Store form contracts"
    return json.loads(match.group(1))


def test_rules_cover_every_canonical_item_type():
    """Every type a teacher can pick has an entry, with every rule answered."""
    rules = store_service.item_type_field_rules()
    assert set(rules) == set(store_service.CANONICAL_ITEM_TYPES)
    for item_type, allowed in rules.items():
        assert set(allowed) == RULE_NAMES, item_type


def test_immediate_use_item_cannot_be_bundled_but_can_use_bulk_pricing():
    """Immediate use cannot bundle, but bulk pricing is a valid price rule."""
    assert store_service.item_type_field_rules()["immediate"]["multi_unit"] is False
    assert store_service.item_type_field_rules()["immediate"]["bulk_discountable"] is True
    assert store_service.item_type_field_rules()["delayed"]["multi_unit"] is True


def test_collective_goal_allows_only_its_own_settings():
    """A shared pot is not a per-seat count, and rent cannot grant one."""
    collective = store_service.item_type_field_rules()["collective"]
    assert collective["collective"] is True
    assert collective["multi_unit"] is False
    assert collective["rent_linkable"] is False


def test_create_form_gates_every_published_rule(client):
    """The Add New Item form tags a group for each rule and ships the payload."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    body = client.get("/admin/store").get_data(as_text=True)

    assert "data-store-item-form" in body
    contracts = _contracts_payload(body)
    assert contracts == contract_payload(rent_prevents_purchase_when_late=False)
    assert 'Purchase Settings' in {section['title'] for section in contracts['immediate|0|1']['sections']}


def test_edit_form_gates_every_published_rule(client):
    """Same guarantee on the edit surface, which carries persisted values."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"store_gating:item:{classroom.class_id}",
    ):
        item = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            user_id=classroom.teacher_user.id,
            name="Homework Pass",
            description="Skip one homework assignment",
            price="25.00",
        )

    body = client.get(
        f"/admin/store/edit/{item.product_lineage_uuid}"
    ).get_data(as_text=True)

    assert "data-store-item-form" in body
    contracts = _contracts_payload(body)
    assert contracts == contract_payload(rent_prevents_purchase_when_late=False)
    assert 'Purchase Settings' in {section['title'] for section in contracts['immediate|0|1']['sections']}
