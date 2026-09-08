"""Regression guard for rendering the admin store item edit form.

``edit_store_item`` lost its ``render_template`` template-name positional
argument in bad800fa, so every GET raised TypeError -> 500. The POST path
redirects on success and never renders, which is why the break went unnoticed.

The route is keyed by ``product_lineage_uuid`` — the product — because that is
what a teacher edits. Saving publishes a new version; it does not rewrite the
one students may already have bought under.

The ``TestRentLinkedItemEditing`` class that used to live here is gone. It
described a partially-editable item whose name and price belonged to Rent
Settings, and that ownership has been inverted: rent settings no longer create
store items, and a rent-linked product is an ordinary store product carrying a
toggle. There is no longer a class of field the store may not edit.
"""

import pytest
from types import SimpleNamespace
from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import FEATContext
from app.models import BillCycle
from app.routes.admin import _apply_rent_link_from_form
from app.services.admin_settings_service import get_rent_settings
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


def _make_store_item(classroom, name="Homework Pass"):
    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"admin_store_edit_route:item:{classroom.class_id}:{name}",
    ):
        return publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            user_id=classroom.teacher_user.id,
            name=name,
            description="Skip one homework assignment",
            price="25.00",
        )


def test_admin_store_edit_get_renders_form(client):
    """GET on the store item edit route renders the edit form for its teacher."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    item = _make_store_item(classroom)

    response = client.get(f"/admin/store/edit/{item.product_lineage_uuid}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Homework Pass" in body
    assert f"/admin/store/edit/{item.product_lineage_uuid}" in body


def test_admin_store_edit_get_rejects_foreign_class_item(client):
    """An item belonging to another class is not editable from the active scope."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    other = initialize_as_teacher("ap_csp_p3", client, client.application)
    foreign_item = _make_store_item(other, name="Foreign Item")

    # Re-establish the first teacher's session; the second initialize logged it out.
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get(f"/admin/store/edit/{foreign_item.product_lineage_uuid}")

    assert response.status_code == 404


def test_rent_link_toggle_updates_benefit_without_rewriting_the_existing_policy(
    app, client
):
    """Rent linkage is a next-policy-version change, not an in-place edit."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    product = _make_store_item(classroom, name="Rent Linked Pass")

    with app.app_context():
        before = get_rent_settings(classroom.class_id)
        before_uuid = before.policy_uuid
        open_cycle = BillCycle(
            class_id=classroom.class_id,
            internal_ref=f"rent:{classroom.class_id}",
            cycle_number=1,
            policy_uuid=before_uuid,
            cycle_boundary_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            next_assessment_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        db.session.add(open_cycle)
        db.session.flush()
        form = SimpleNamespace(
            is_rent_linked=SimpleNamespace(data=True),
            item_type=SimpleNamespace(data="delayed"),
            rent_linked_quantity=SimpleNamespace(data=2),
        )

        with FEATContext(
            "FEAT-SETTINGS-001",
            idempotency_key=f"admin_store_edit_route:rent-link:{product.product_lineage_uuid}",
        ):
            _apply_rent_link_from_form(
                form,
                class_id=classroom.class_id,
                product_lineage_uuid=product.product_lineage_uuid,
            )

        after = get_rent_settings(classroom.class_id)
        assert after.policy_uuid != before_uuid
        assert after.get_satisfaction_benefit_grants() == [{
            "entitlement_type": "DELAYED_USE",
            "quantity": 2,
            "product_lineage_uuid": product.product_lineage_uuid,
        }]
        assert before.get_satisfaction_benefit_grants() == []
        db.session.refresh(open_cycle)
        assert open_cycle.policy_uuid == before_uuid
        assert open_cycle.next_assessment_at == datetime(2026, 10, 1, tzinfo=timezone.utc)
