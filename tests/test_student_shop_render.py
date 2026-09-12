"""The student shop page must render once the student owns an entitlement.

``build_entitlement_card_view`` read ``item.id`` off the resolved product. The
store_items/store_products consolidation left ``StoreProduct`` with no ``id`` --
it is keyed by ``policy_uuid`` (the version) with ``product_lineage_uuid`` as
the stable product handle -- so the page raised ``AttributeError`` for any
student holding at least one purchase. A student with an empty purchase history
never reached the loop.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.services.context_resolver import CanonicalContext
from tests.helpers.canonical_classroom import login_student, provision_classroom
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


def test_shop_page_renders_with_an_owned_entitlement(client, app):
    """A student holding one entitlement is the exact state that used to 500."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        class_id = classroom.class_id
        enable_class_feature(class_id=class_id, feature="store")

        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"shop-render:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"shop-render-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=class_id,
                user_id=student.user_id,
                amount=Decimal("500.00"),
                account_type="checking",
                type="payroll",
                description="Shop render test funding",
            )
        db.session.commit()

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="shop-render:publish"):
            product = publish_store_product(
                class_id=class_id,
                entitlement_type="DELAYED_USE",
                created_by_seat_id=classroom.teacher_seat_id,
                name="Homework Pass",
                price="10.00",
            )
        db.session.commit()

        result = execute_store_purchase(
            canonical_context=CanonicalContext(
                user_id=student.user_id,
                class_id=class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
            policy_uuid=product.policy_uuid,
            quantity=1,
        )
        assert result.success is True
        db.session.commit()

        login_student(client, student)

    response = client.get("/student/shop")

    assert response.status_code == 200, response.get_data(as_text=True)[:2000]
    assert "Homework Pass" in response.get_data(as_text=True)
