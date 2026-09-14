"""Economy analysis over the live store catalog.

``check_store_items_balance`` re-filtered the products it was handed on a v1
``is_active`` column. ``StoreProduct`` carries ``availability_state`` instead, so
every analysis run against a class with any store product raised
``AttributeError`` and ``POST /admin/api/economy/analyze`` returned 500.

Availability belongs to the caller: each call site resolves the sellable set
through ``store_service.list_products(..., states=(IN_USE,))``. The checker
prices whatever it is given.
"""

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.services import store_service
from app.utils.economy_balance import EconomyBalanceChecker
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


def _publish(classroom, name, price, **kwargs):
    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"economy_analysis:{classroom.class_id}:{name}",
    ):
        return publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            user_id=classroom.teacher_user.id,
            name=name,
            description="Analysis fixture",
            price=price,
            **kwargs,
        )


def test_economy_analyze_succeeds_with_a_store_product_in_the_catalog(client):
    """The reported 500: one sellable product was enough to break analysis."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    _publish(classroom, "Homework Pass", "25.00")

    # expected_weekly_hours must be set for CWI to be defined; without it the
    # analysis returns early and never reaches store pricing at all.
    response = client.post(
        "/admin/api/economy/analyze", json={"expected_weekly_hours": 5}
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["status"] == "success"
    assert any(
        "Homework Pass" in warning["feature"]
        for warning in payload["warning_items"]
    )


def test_store_balance_check_prices_every_product_it_is_given(client):
    """No availability re-derivation: the caller's list is the priced set.

    The rows here come from ``list_products``, the same call the route makes —
    ``publish_store_product`` returns a detached snapshot, which would not
    reproduce the attribute error at all.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    _publish(classroom, "Cheap Pass", "1.00")
    _publish(classroom, "Dear Pass", "40.00")

    products = store_service.list_products(
        classroom.class_id, states=(store_service.IN_USE,)
    )
    checker = EconomyBalanceChecker(
        classroom.teacher_user.id, class_id=classroom.class_id
    )
    warnings = checker.check_store_items_balance(products, cwi=20.0)

    assert {w.feature for w in warnings} == {
        "Store Item: Cheap Pass",
        "Store Item: Dear Pass",
    }


def test_long_term_goal_products_stay_out_of_the_cwi_bands(client):
    """The one exclusion the checker still owns, since it is a pricing intent."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()

    _publish(classroom, "Class Party", "500.00", is_long_term_goal=True)

    products = store_service.list_products(
        classroom.class_id, states=(store_service.IN_USE,)
    )
    assert [p.is_long_term_goal for p in products] == [True]

    checker = EconomyBalanceChecker(
        classroom.teacher_user.id, class_id=classroom.class_id
    )

    assert checker.check_store_items_balance(products, cwi=20.0) == []
