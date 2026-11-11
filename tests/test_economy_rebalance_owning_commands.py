"""Every rebalance row is carried out by the command that owns it.

FEAT-CLASS-005 §XI delegates rent to rent supersession and Store prices to
product version supersession. A scheduled Store price row had no path to its
owner when transitions were queued, while the page still flashed success.

Store prices have no later activation boundary (FEAT-ECON-001 §VIII), so they
take effect at once; rent terms always take effect from the next unbilled
period. There is no activation choice (owner ruling 2026-09-30), and a
submitted ``activation_mode`` changes nothing.

The owning table's new row is the whole record of a change: the rebalance keeps
no lineage of its own (operator ruling 2026-09-30, DOM-CLASS-003 §IX).
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import RentSettings, StoreProduct
from app.services.class_configuration_query_service import get_rent_settings
from app.services.store_service import get_current_version
from tests.helpers.class_domain import customize_rent_settings, update_expected_weekly_hours
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product


def _offered(client):
    body = client.get("/admin/economic-engine?review_rebalance=1").get_data(as_text=True)
    return set(re.findall(r'name="selected_changes"[^>]*value="([^"]+)"', body))


def _teacher_class(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    update_expected_weekly_hours(client, "40")
    return classroom


def _overpriced_store_item(classroom):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"rebalance-owner:store:{classroom.class_id}"):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            name="Overpriced Pass",
            price="9999.00",
            economic_role="necessity",
        )
    db.session.commit()
    return product


def test_a_store_price_takes_effect_at_once_whatever_mode_a_stale_form_posts(client, app):
    classroom = _teacher_class(client, app)
    product = _overpriced_store_item(classroom)
    key = f"store:{product.product_lineage_uuid}"
    assert key in _offered(client)

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"activation_mode": "next_renewal", "selected_changes": [key]},
    )

    assert response.status_code == 302
    with app.app_context():
        assert get_current_version(classroom.class_id, product.product_lineage_uuid).price < Decimal("9999.00")


def test_immediate_store_price_supersedes_the_product(client, app):
    classroom = _teacher_class(client, app)
    product = _overpriced_store_item(classroom)
    key = f"store:{product.product_lineage_uuid}"
    assert key in _offered(client)

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": [key]},
    )

    assert response.status_code == 302
    with app.app_context():
        current = get_current_version(classroom.class_id, product.product_lineage_uuid)
        assert current.policy_uuid != product.policy_uuid
        assert current.price < Decimal("9999.00")
        # The superseded version stays as history; the new one is the record.
        assert StoreProduct.query.filter_by(
            class_id=classroom.class_id, product_lineage_uuid=product.product_lineage_uuid,
        ).count() == 2


def test_scheduled_rent_and_late_penalty_become_one_dated_rent_row(client, app):
    """Both terms belong to one rent contract, so they land in one new row."""
    classroom = _teacher_class(client, app)
    with app.app_context():
        customize_rent_settings(
            classroom.class_id,
            rent_amount=Decimal("1.00"),
            late_penalty_amount=Decimal("0.01"),
        )
        db.session.commit()
    offered = _offered(client)
    rent_keys = {key for key in offered if key.startswith("rent")}
    assert "rent-late-penalty" in rent_keys and len(rent_keys) == 2, offered
    with app.app_context():
        rows_before = RentSettings.query.filter_by(class_id=classroom.class_id).count()

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": sorted(rent_keys)},
    )

    assert response.status_code == 302
    with app.app_context():
        assert RentSettings.query.filter_by(class_id=classroom.class_id).count() == rows_before + 1
        new = get_rent_settings(classroom.class_id)
        assert new.rent_amount > Decimal("1.00")
        assert new.late_penalty_amount > Decimal("0.01")
        assert new.rent_effective_at is not None


def test_a_selection_past_an_advisory_insurance_row_is_applied(client, app):
    """Advisory insurance rows carry no change.

    The route indexed ``item['change']`` while matching the selection, so any
    selected row listed after an out-of-band insurance policy raised KeyError.
    Rendering the page with an insurance policy also runs the budget survival
    check, which reads the premium off the offered ``insurance_policies`` rows.
    """
    from app.services.insurance_definition_service import create_insurance_definition

    classroom = _teacher_class(client, app)
    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"rebalance-owner:insurance:{classroom.class_id}"):
            create_insurance_definition(
                class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat.id,
                definition={
                    "title": "Overpriced Cover",
                    "insurance_type": "TRANSACTION",
                    "premium": Decimal("9999.00"),
                    "charge_frequency": "WEEKLY",
                    "reimbursement_percentage": Decimal("80"),
                    "payout_multiple": Decimal("3"),
                    "claims_per_week_equivalent": Decimal("1"),
                    "claim_window_days": 7,
                    "bill_preview_days": 3,
                    "nonpayment_mode": "ACCUMULATE",
                },
            )
        db.session.commit()
    product = _overpriced_store_item(classroom)

    page = client.get("/admin/economic-engine?review_rebalance=1")
    assert page.status_code == 200, page.get_data(as_text=True)[:2000]
    assert "Insurance: Overpriced Cover" in page.get_data(as_text=True)
    key = f"store:{product.product_lineage_uuid}"

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": [key]},
    )

    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    with app.app_context():
        assert get_current_version(classroom.class_id, product.product_lineage_uuid).price < Decimal("9999.00")


def test_insurance_advisory_row_is_judged_in_the_class_policy_mode(app, monkeypatch):
    """The checker exposes ``policy_mode``; reading ``mode`` always fell back to default."""
    from types import SimpleNamespace

    from app.routes.admin import _build_rebalance_preview
    from app.services import economic_engine

    seen = []

    def fake_resolve_insurance(*, product, cwi, mode):
        seen.append(mode)
        return SimpleNamespace(cwi=None)

    monkeypatch.setattr(economic_engine, "resolve_insurance", fake_resolve_insurance)
    policy = SimpleNamespace(
        policy_uuid="policy-uuid", premium=Decimal("5.00"), insurance_type="TRANSACTION",
        title="Cover", tier_name=None,
    )
    checker = SimpleNamespace(policy_mode="tight", store_role_bands=lambda cwi: {})

    with app.app_context():
        _build_rebalance_preview(
            None, "class-id", checker, Decimal("100.00"), None, [policy],
            store_items=[],
        )

    assert seen == ["tight"]
