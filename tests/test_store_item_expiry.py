"""A Store item stops being usable at its expiry (FEAT-STOR-002 §VIII).

``auto_expiry_days`` was configured, validated and shown to the teacher, then
read by nothing: a student could request redemption of an item long past its
expiry, and no EXPIRED event was ever written. My Items also rendered every
event in the history, so a used item showed twice and finished items piled up.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent
from app.scheduled_tasks import run_store_item_expiry_job
from app.services.entitlement_read_service import (
    derive_display_status,
    entitlement_expires_at,
    latest_entitlement_grant,
)
from tests.dom.entitlement.helpers import purchase_entitlement_item, use_entitlement_item
from tests.helpers import temporal
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]

_BOUGHT_AT = None


@pytest.fixture(autouse=True)
def _bought_after_setup(app):
    """Purchases happen just after now: a fixed date would fall before the
    store feature's effective_at once the calendar passes it."""
    global _BOUGHT_AT
    with app.app_context():
        _BOUGHT_AT = temporal.shifted(temporal.now(), hours=1)


def _publish(classroom, name, entitlement_type="DELAYED_USE", **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"expiry:publish:{name}"):
        return publish_store_product(
            class_id=classroom.class_id,
            entitlement_type=entitlement_type,
            created_by_seat_id=classroom.teacher_seat_id,
            name=name,
            price="5.00",
            **definition,
        )


@pytest.fixture
def shop(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="store")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"expiry:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"expiry-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                amount=Decimal("100.00"),
                account_type="checking",
                type="payroll",
                description="Store expiry test funding",
            )
        product = _publish(classroom, "Expiring pass", auto_expiry_days=3)
        db.session.commit()
    return classroom, student, product


def _buy(client, student, product):
    with temporal.pinned_clock(_BOUGHT_AT):
        response = purchase_entitlement_item(
            client, policy_uuid=product.policy_uuid, passphrase=student.passphrase,
        )
    assert response.get_json()["status"] == "success", response.get_json()
    grant = EntitlementEvent.query.filter_by(
        correlation_id=response.get_json()["correlation_id"], event_type="GRANTED",
    ).one()
    return grant.entitlement_id


def _my_items(client):
    page = client.get("/student/shop").data.decode()
    return page.split("<!-- My Items Tab -->", 1)[1].split("modal fade", 1)[0]


def test_expiry_is_counted_in_class_days_from_purchase(client, app, shop):
    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)

    with app.app_context():
        expected = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        assert entitlement_expires_at(latest_entitlement_grant(entitlement_id)) == expected
        with temporal.pinned_clock(temporal.shifted(expected, minutes=-1)):
            assert derive_display_status(entitlement_id) == "purchased"
        with temporal.pinned_clock(expected):
            assert derive_display_status(entitlement_id) == "expired"


def test_expired_item_cannot_be_redeemed(client, app, shop):
    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)

    with temporal.pinned_clock(temporal.shifted(expires_at, hours=1)):
        response = use_entitlement_item(
            client, entitlement_id=entitlement_id, passphrase=student.passphrase,
        )
        with app.app_context():
            assert derive_display_status(entitlement_id) == "expired"

    assert response.status_code == 400
    assert "not available" in response.get_json()["message"]


def test_sweep_records_expiry_at_the_boundary_once(client, app, shop):
    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=-1)):
            run_store_item_expiry_job()
        assert not EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()

        with temporal.pinned_clock(temporal.shifted(expires_at, hours=5)):
            run_store_item_expiry_job()
            run_store_item_expiry_job()

        expired = EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()
        assert len(expired) == 1
        assert expired[0].timestamp == expires_at


def test_request_made_before_expiry_is_left_to_the_teacher(client, app, shop):
    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)

    with temporal.pinned_clock(temporal.shifted(expires_at, hours=-1)):
        response = use_entitlement_item(client, entitlement_id=entitlement_id, passphrase=student.passphrase)
    assert response.get_json()["status"] == "success", response.get_json()

    with app.app_context(), temporal.pinned_clock(temporal.shifted(expires_at, hours=2)):
        assert derive_display_status(entitlement_id) == "processing"
        run_store_item_expiry_job()
        assert not EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()


def test_item_without_expiry_never_expires(client, app, shop):
    classroom, student, _ = shop
    with app.app_context():
        perpetual = _publish(classroom, "Perpetual pass")
        db.session.commit()
    entitlement_id = _buy(client, student, perpetual)

    with app.app_context(), temporal.pinned_clock(temporal.calendar_days_later(_BOUGHT_AT, 400)):
        assert derive_display_status(entitlement_id) == "purchased"
        run_store_item_expiry_job()
        assert not EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()


def test_my_items_lists_only_items_still_in_hand_once_each(client, app, shop):
    classroom, student, product = shop
    with app.app_context():
        used_on_sale = _publish(classroom, "Instant treat", entitlement_type="IMMEDIATE_USE")
        keeper = _publish(classroom, "Keeper pass")
        db.session.commit()
    _buy(client, student, product)
    _buy(client, student, used_on_sale)
    _buy(client, student, keeper)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)

    with temporal.pinned_clock(temporal.shifted(expires_at, hours=1)):
        items = _my_items(client)

    assert items.count("Keeper pass") >= 1
    assert "Instant treat" not in items, "an item used at sale is still listed"
    assert "Expiring pass" not in items, "an expired item is still listed"
    assert items.count('card-title">Keeper pass<') == 1
