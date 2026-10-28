"""A resubmitted store purchase is the same purchase (FEAT-STOR-001 §IX).

The shop's Confirm button posts to ``/api/purchase-item``. A double-click, or a
retry after a lost response, sends the same command twice. The route used to
call FEAT-STOR-001 without an idempotency key, so each POST minted a fresh
ledger key and the second one charged and granted again.
"""

import uuid
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, Transaction
from app.services.ledger_balance_query_service import get_available_balance
from tests.dom.entitlement.helpers import purchase_entitlement_item
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


@pytest.fixture
def shop(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="store")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"purchase-idem:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"purchase-idem-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                amount=Decimal("100.00"),
                account_type="checking",
                type="payroll",
                description="Purchase idempotency test funding",
            )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="purchase-idem:publish"):
            product = publish_store_product(
                class_id=classroom.class_id,
                entitlement_type="DELAYED_USE",
                created_by_seat_id=classroom.teacher_seat_id,
                name="Homework pass",
                price="10.00",
            )
        db.session.commit()
    return classroom, student, product


def _purchase_rows(class_id, seat_id):
    charges = Transaction.query.filter_by(class_id=class_id, seat_id=seat_id, type="purchase").all()
    grants = EntitlementEvent.query.filter_by(
        class_id=class_id, target_seat_id=seat_id, event_type="GRANTED", acquisition_type="PURCHASE",
    ).all()
    return charges, grants


def test_resubmitted_purchase_charges_and_grants_once(client, app, shop):
    classroom, student, product = shop
    request_id = str(uuid.uuid4())

    for _ in range(2):
        response = purchase_entitlement_item(
            client, policy_uuid=product.policy_uuid, passphrase=student.passphrase,
            quantity=2, client_purchase_id=request_id,
        )
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["status"] == "success"

    with app.app_context():
        charges, grants = _purchase_rows(classroom.class_id, student.seat_id)
        assert len(charges) == 1
        assert len(grants) == 2
        assert get_available_balance(student.seat_id, classroom.class_id, "checking") == Decimal("80.00")


def test_distinct_purchase_requests_are_distinct_purchases(client, app, shop):
    classroom, student, product = shop

    for _ in range(2):
        response = purchase_entitlement_item(
            client, policy_uuid=product.policy_uuid, passphrase=student.passphrase,
            client_purchase_id=str(uuid.uuid4()),
        )
        assert response.get_json()["status"] == "success"

    with app.app_context():
        charges, grants = _purchase_rows(classroom.class_id, student.seat_id)
        assert len(charges) == 2
        assert len(grants) == 2
        assert get_available_balance(student.seat_id, classroom.class_id, "checking") == Decimal("80.00")


def test_overlong_purchase_request_id_is_refused(client, app, shop):
    classroom, student, product = shop

    response = purchase_entitlement_item(
        client, policy_uuid=product.policy_uuid, passphrase=student.passphrase,
        client_purchase_id="x" * 200,
    )

    assert response.status_code == 400
    with app.app_context():
        charges, _ = _purchase_rows(classroom.class_id, student.seat_id)
        assert charges == []
