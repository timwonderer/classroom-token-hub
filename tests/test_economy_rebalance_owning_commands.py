"""Every rebalance row is carried out by the command that owns it.

FEAT-CLASS-005 §XI delegates rent to rent supersession, Store prices to product
version supersession, and the overdraft fee to Economic Engine evolution. Two
rows the preview offered had no path to their owner: a scheduled Store price was
skipped when transitions were queued, and an overdraft fee was skipped on both
paths, while the page still flashed success.

Neither Store prices nor the overdraft fee has a later activation boundary
(FEAT-ECON-001 §VIII), so both are immediate-only and a scheduled submission
that includes them is refused.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.models import ClassFeature, PolicyTransition, PolicyVersion
from app.services.class_configuration_query_service import (
    get_current_economic_engine,
    is_feature_enabled,
)
from app.services.context_resolver import CanonicalContext
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


def test_scheduled_store_price_is_refused_rather_than_silently_dropped(client, app):
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
        assert get_current_version(classroom.class_id, product.product_lineage_uuid).price == Decimal("9999.00")
        assert PolicyTransition.query.filter_by(class_id=classroom.class_id).count() == 0


def test_immediate_store_price_supersedes_the_product_and_records_a_transition(client, app):
    classroom = _teacher_class(client, app)
    product = _overpriced_store_item(classroom)
    key = f"store:{product.product_lineage_uuid}"
    assert key in _offered(client)

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"activation_mode": "immediate", "confirm_immediate": "yes", "selected_changes": [key]},
    )

    assert response.status_code == 302
    with app.app_context():
        current = get_current_version(classroom.class_id, product.product_lineage_uuid)
        assert current.policy_uuid != product.policy_uuid
        assert current.price < Decimal("9999.00")
        applied = PolicyTransition.query.filter_by(
            class_id=classroom.class_id, domain="store", status="applied",
        ).all()
        assert len(applied) == 1


def test_immediate_overdraft_fee_evolves_the_economic_engine(client, app):
    classroom = _teacher_class(client, app)
    with app.app_context():
        context = CanonicalContext(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat.id,
            actor_role="teacher",
        )
        result = execute_evolve_economic_engine(
            canonical_context=context,
            class_id=classroom.class_id,
            updates={"flat_overdraft_fee": 999.0},
            feature_list=[
                feature for feature in ClassFeature.feature_names()
                if is_feature_enabled(classroom.class_id, feature)
            ],
            idempotency_key=f"rebalance-owner:overdraft-seed:{classroom.class_id}",
        )
        assert result.success, result.error_message
    assert "overdraft_fee" in _offered(client)

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"activation_mode": "immediate", "confirm_immediate": "yes", "selected_changes": ["overdraft_fee"]},
    )

    assert response.status_code == 302
    with app.app_context():
        engine = get_current_economic_engine(classroom.class_id)
        assert Decimal(str(engine.flat_overdraft_fee)) < Decimal("999.00")
        assert PolicyTransition.query.filter_by(
            class_id=classroom.class_id, domain="banking", status="applied",
        ).count() == 1


def test_scheduled_rent_and_late_penalty_queue_independent_dated_transitions(client, app):
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

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"activation_mode": "next_renewal", "selected_changes": sorted(rent_keys)},
    )

    assert response.status_code == 302
    with app.app_context():
        pending = PolicyTransition.query.filter_by(
            class_id=classroom.class_id, domain="rent", status="pending",
        ).all()
        assert len(pending) == 2
        for transition in pending:
            version = db.session.get(PolicyVersion, transition.target_policy_version_id)
            assert '"effective_at": "' in version.policy_payload_json


def test_a_selection_past_an_advisory_insurance_row_is_applied(client, app):
    """Advisory insurance rows carry no change.

    The route indexed ``item['change']`` while matching the selection, so any
    selected row listed after an out-of-band insurance policy raised KeyError.
    Rendering the page with an insurance policy also runs the budget survival
    check, which read ``premium`` off PolicyVersion rows that carry their terms
    in the payload.
    """
    from app.services.insurance_policy_service import create_policy_version

    classroom = _teacher_class(client, app)
    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"rebalance-owner:insurance:{classroom.class_id}"):
            create_policy_version(
                class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat.id,
                payload={
                    "name": "Overpriced Cover",
                    "premium": "9999.00",
                    "charge_frequency": "weekly",
                    "insurance_type": "TRANSACTION",
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
        data={"activation_mode": "immediate", "confirm_immediate": "yes", "selected_changes": [key]},
    )

    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    with app.app_context():
        assert get_current_version(classroom.class_id, product.product_lineage_uuid).price < Decimal("9999.00")


def test_insurance_advisory_row_is_judged_in_the_class_policy_mode(app, monkeypatch):
    """The checker exposes ``policy_mode``; reading ``mode`` always fell back to default."""
    import json
    from types import SimpleNamespace

    from app.routes.admin import _build_rebalance_preview
    from app.services import economic_engine

    seen = []

    def fake_resolve_insurance(*, product, cwi, mode):
        seen.append(mode)
        return SimpleNamespace(cwi=None)

    monkeypatch.setattr(economic_engine, "resolve_insurance", fake_resolve_insurance)
    version = PolicyVersion(
        policy_payload_json=json.dumps({"premium": "5.00", "insurance_type": "TRANSACTION"}),
        is_active=True,
    )
    checker = SimpleNamespace(policy_mode="tight", store_role_bands=lambda cwi: {})

    with app.app_context():
        _build_rebalance_preview(
            None, "class-id", checker, Decimal("100.00"), None, [version],
            store_items=[], economic_engine=None,
        )

    assert seen == ["tight"]
