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

import re

import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import BillCycle
from app.routes.admin import _apply_rent_link_from_form
from app.services.admin_settings_service import get_rent_settings
from app.services.store_service import get_current_version
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


def test_admin_store_edit_post_changes_the_price(app, client):
    """Editing the price publishes a successor carrying the new price.

    The payload includes ``submit``, which is what a browser sends and what no
    prior test sent. The field-legality guard policed every field on the form,
    so the submit button itself was reported as inapplicable and the save was
    refused — silently, because neither store template rendered form errors.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    item = _make_store_item(classroom, name="Repriced Pass")

    response = client.post(
        f"/admin/store/edit/{item.product_lineage_uuid}",
        data={
            "name": "Repriced Pass",
            "description": "Skip one homework assignment",
            "item_type": "immediate",
            "economic_role": "necessity",
            "price": "31.00",
            "submit": "Save Item",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        current = get_current_version(classroom.class_id, item.product_lineage_uuid)
        assert current.price == Decimal("31.00")


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
        # Fixture setup is still a mutation, so it needs an envelope of its own:
        # the flush guard refuses any DML outside a FEAT context.
        with FEATContext(
            "FEAT-TEST-SETUP",
            idempotency_key=f"admin_store_edit_route:open-cycle:{classroom.class_id}",
        ):
            db.session.add(open_cycle)
            db.session.flush()
        # No activation date: the benefit takes effect now, which is the case
        # this test pins. The supersede call reads the field unconditionally, so
        # the stub must carry it even when the answer is "unset".
        form = SimpleNamespace(
            is_rent_linked=SimpleNamespace(data=True),
            item_type=SimpleNamespace(data="delayed"),
            rent_linked_quantity=SimpleNamespace(data=2),
            activation_date=SimpleNamespace(data=None),
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


def _store_teacher(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()
    return classroom


def test_store_forms_bind_live_price_feedback_and_render_long_term_goal_as_a_choice(app, client):
    """Copilot C9/C20/C21: both forms share one renderer.

    The copied renderers lost the price input's data-economy-validate marker
    and the #economy-warnings container, so live CWI feedback bound nothing.
    They also rendered is_long_term_goal as a hidden input whose value was
    always "y", so every browser save marked the item a long-term goal.
    """
    classroom = _store_teacher(app, client)
    item = _make_store_item(classroom, name="Rendered Pass")

    for path in ("/admin/store", f"/admin/store/edit/{item.product_lineage_uuid}"):
        body = client.get(path).get_data(as_text=True)
        assert 'data-economy-validate="store_item"' in body, path
        assert 'id="economy-warnings"' in body, path
        assert 'data-economy-trigger="[data-economy-validate]"' in body, path
        assert re.search(r'<input[^>]*type="checkbox"[^>]*name="is_long_term_goal"|<input[^>]*name="is_long_term_goal"[^>]*type="checkbox"', body), path
        assert not re.search(r'<input[^>]*type="hidden"[^>]*name="is_long_term_goal"', body), path


def test_edit_to_grant_only_accepts_the_browser_payload(app, client):
    """Copilot C15: a field the browser did not send reads as absent.

    Building the POST form from the stored item filled the undisclosed price
    back in, and the save was refused as carrying an inapplicable field.
    """
    classroom = _store_teacher(app, client)
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"grant-only-edit:{classroom.class_id}"):
        item = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            name="Soon Grant Only",
            price="25.00",
        )

    response = client.post(
        f"/admin/store/edit/{item.product_lineage_uuid}",
        data={
            "name": "Soon Grant Only",
            "item_type": "delayed",
            "economic_role": "necessity",
            "is_rent_linked": "y",
            "rent_linked_quantity": "1",
            "submit": "Save Item",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        current = get_current_version(classroom.class_id, item.product_lineage_uuid)
        assert current.policy_uuid != item.policy_uuid
        assert current.price is None
        assert current.direct_purchase_allowed is False


def test_edit_keeps_the_delist_date(app, client):
    """Copilot C10: editing a scheduled product no longer erases its delist date."""
    from datetime import date
    from app.routes.admin import _end_of_day_utc

    classroom = _store_teacher(app, client)
    # Seeded exactly as the form writes it: the exclusive end of the chosen
    # local day. Its UTC date is the next day, so a prefill that takes
    # ``.date()`` of the stored datetime shows the wrong day on a UTC server.
    with app.app_context():
        # The class is passed explicitly: this runs outside a request, and the
        # day boundary is a property of the class's timezone, not of `g`.
        delist = _end_of_day_utc(date(2030, 6, 30), class_id=classroom.class_id)
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"delist-edit:{classroom.class_id}"):
        item = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            name="Seasonal Pass",
            price="25.00",
            auto_delist_date=delist,
        )

    body = client.get(f"/admin/store/edit/{item.product_lineage_uuid}").get_data(as_text=True)
    assert 'value="2030-06-30"' in body

    response = client.post(
        f"/admin/store/edit/{item.product_lineage_uuid}",
        data={
            "name": "Seasonal Pass",
            "item_type": "immediate",
            "economic_role": "necessity",
            "price": "27.00",
            "auto_delist_date": "2030-06-30",
            "submit": "Save Item",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        current = get_current_version(classroom.class_id, item.product_lineage_uuid)
        assert current.price == Decimal("27.00")
        # Stored as the end of the chosen local day. Compare instants: the date
        # of that instant differs between a UTC and a local database session.
        from datetime import date
        from app.routes.admin import _end_of_day_utc
        assert current.auto_delist_date == _end_of_day_utc(
            date(2030, 6, 30), class_id=classroom.class_id
        )


def test_future_start_date_publishes_in_use_and_gates_at_read_time(app, client):
    """Copilot C11: a start date no longer hides the product for ever.

    Nothing promotes a HIDDEN version, so a future-dated product never went on
    sale. activation_at is a read-time gate on an IN_USE version
    (SPEC-STORE-001 §IV.C).
    """
    from app.models import StoreProduct
    from app.services.store_policy_resolver import StorePolicyResolver

    classroom = _store_teacher(app, client)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()

    response = client.post(
        "/admin/store",
        data={
            "name": "Next Week Pass",
            "item_type": "immediate",
            "economic_role": "necessity",
            "price": "12.00",
            "activation_date": tomorrow,
            "submit": "Save Item",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        product = StoreProduct.query.filter_by(class_id=classroom.class_id, name="Next Week Pass").one()
        assert product.availability_state == "IN_USE"
        assert product.activation_at is not None
        assert StorePolicyResolver.resolve_store_item(product.policy_uuid).is_purchasable is False


def test_admin_store_renders_a_grant_only_product(app, client):
    """Copilot C1: a grant-only product has no price and must not 500 the catalog."""
    classroom = _store_teacher(app, client)
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"grant-only-render:{classroom.class_id}"):
        publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            name="Rent Only Perk",
            price=None,
            direct_purchase_allowed=False,
        )

    response = client.get("/admin/store")

    assert response.status_code == 200
    assert "Grant only" in response.get_data(as_text=True)
