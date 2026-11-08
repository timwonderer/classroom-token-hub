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


def test_request_feat_refuses_an_item_that_expired_after_the_route_check(client, app, shop):
    """The FEAT rechecks under the holder lock, so a request that passed the
    route just before the boundary cannot be filed after it."""
    from app.feats.entitlement_lifecycle_feat import execute_use_item_request
    from app.models import PendingAction

    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=1)):
            with pytest.raises(ValueError, match="expired"):
                execute_use_item_request(
                    class_id=classroom.class_id, seat_id=student.seat_id,
                    entitlement_id=entitlement_id, action_payload={"action": "REQUEST"},
                    idempotency_key=f"t:late-request:{entitlement_id}",
                )
        db.session.rollback()
        assert PendingAction.query.filter_by(entitlement_id=entitlement_id).count() == 0


def test_expiry_refuses_an_item_whose_request_landed_after_the_sweep_read(client, app, shop):
    """The sweep's pending check runs before its transaction; the write rechecks
    under the lock, so a request that committed in between is left alone."""
    from app.services import entitlement_service

    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
    with temporal.pinned_clock(temporal.shifted(expires_at, hours=-1)):
        response = use_entitlement_item(client, entitlement_id=entitlement_id, passphrase=student.passphrase)
    assert response.get_json()["status"] == "success", response.get_json()

    with app.app_context():
        grant = latest_entitlement_grant(entitlement_id)
        with FEATContext("FEAT-STOR-002", idempotency_key=f"t:expire:{entitlement_id}"):
            with pytest.raises(ValueError, match="request waiting"):
                entitlement_service.expire_entitlement(
                    entitlement_id=entitlement_id, class_id=classroom.class_id,
                    target_seat_id=student.seat_id, actor_seat_id=classroom.teacher_seat_id,
                    product_id=grant.product_id, entitlement_type=grant.entitlement_type,
                    acquisition_type=grant.acquisition_type, correlation_id=f"corr_t:{entitlement_id}",
                    effective_at=expires_at,
                )
        db.session.rollback()
        assert not EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()


def test_expired_hall_pass_is_not_offered_before_the_sweep(client, app, shop):
    from app.services.entitlement_service import get_available_hall_pass_grant

    classroom, student, _ = shop
    with app.app_context():
        pass_product = _publish(classroom, "Expiring hall pass", entitlement_type="HALL_PASS", auto_expiry_days=3)
        db.session.commit()
    entitlement_id = _buy(client, student, pass_product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=-1)):
            assert get_available_hall_pass_grant(student.seat_id, classroom.class_id).entitlement_id == entitlement_id
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=1)):
            assert get_available_hall_pass_grant(student.seat_id, classroom.class_id) is None


def test_expired_hall_pass_leaves_the_balance_before_the_sweep(client, app, shop):
    from app.services.entitlement_read_service import get_hall_pass_balance

    classroom, student, _ = shop
    with app.app_context():
        pass_product = _publish(classroom, "Balance hall pass", entitlement_type="HALL_PASS", auto_expiry_days=3)
        db.session.commit()
    _buy(client, student, pass_product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=-1)):
            before = get_hall_pass_balance(student.seat_id, classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, minutes=1)):
            after = get_hall_pass_balance(student.seat_id, classroom.class_id)
    assert after == before - 1


def test_item_is_exercisable_until_its_boundary(client, app, shop):
    from app.services.entitlement_read_service import is_entitlement_exercisable

    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        assert is_entitlement_exercisable(
            entitlement_id, classroom.class_id, reference_time_utc=temporal.shifted(expires_at, minutes=-1),
        )
        assert not is_entitlement_exercisable(entitlement_id, classroom.class_id, reference_time_utc=expires_at)


def test_sweep_records_expiry_for_a_hall_pass(client, app, shop):
    classroom, student, _ = shop
    with app.app_context():
        pass_product = _publish(classroom, "Swept hall pass", entitlement_type="HALL_PASS", auto_expiry_days=3)
        db.session.commit()
    entitlement_id = _buy(client, student, pass_product)
    with app.app_context():
        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, hours=1)):
            run_store_item_expiry_job()
        expired = EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").all()
        assert len(expired) == 1
        assert expired[0].timestamp == expires_at


def test_sweep_expires_items_whose_version_was_retired_by_an_edit(client, app, shop):
    """The sweep reads only versions with an expiry, retired ones included: an
    edit retires the version a student bought, and its terms still bind."""
    from app.models import StoreProduct
    from app.services import store_service

    classroom, student, product = shop
    entitlement_id = _buy(client, student, product)
    with app.app_context():
        current = StoreProduct.query.filter_by(policy_uuid=product.policy_uuid).one()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"expiry:edit:{product.policy_uuid}"):
            store_service.supersede_product(
                current=current,
                definition={
                    "name": "Expiring pass, no expiry now",
                    "price": "5.00",
                    "item_type": "delayed",
                    "economic_role": "necessity",
                    "direct_purchase_allowed": True,
                },
                actor_seat_id=classroom.teacher_seat_id,
            )
        db.session.commit()
        assert StoreProduct.query.filter_by(policy_uuid=product.policy_uuid).one().availability_state == "RETIRED"

        expires_at = temporal.calendar_days_later(_BOUGHT_AT, 3, class_id=classroom.class_id)
        with temporal.pinned_clock(temporal.shifted(expires_at, hours=1)):
            run_store_item_expiry_job()
        assert EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type="EXPIRED").count() == 1
