"""Behavioral tests for the three store sale mechanics.

``TestPublicationValidation`` in ``tests/test_store_policy_resolver.py`` proves
these three settings cannot be *misconfigured*. That is a different claim from
proving they *execute*, and all three defects lived precisely in the gap: each
was published, stored, and displayed to the student correctly, and then ignored
at purchase time.

* #30 bundle — the item card promised N units, the purchase granted one.
* #31 bulk discount — the card quoted a discounted price, the ledger charged
  the full one.
* #32 collective goal deadline — the date was displayed and never consulted, so
  students kept paying into a goal that could no longer be reached.

So every test here asserts against the two surfaces the student actually feels:
the number of entitlement lifecycles created, and the amount debited.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, StoreProduct, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_balance_query_service import get_available_balances
from app.services import store_service
from app.services.store.collective_goals import count_goal_participants
from app.feats.transaction_void_feat import execute_void_transaction
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import (
    create_ledger_idempotent_transaction,
    settle_ledger_balances,
)
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


@pytest.fixture
def buyer(app):
    """A funded student seat in a canonical class.

    Funding matters: an unfunded seat resolves every debit through the
    overdraft path, which would let a wrong charge pass unnoticed because the
    balance ends up negative either way.
    """
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"sale-mechanics:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"sale-mechanics-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                user_id=student.user_id,
                amount=Decimal("1000.00"),
                account_type="checking",
                type="payroll",
                description="Sale mechanics test funding",
            )
        db.session.commit()
        yield {
            "class_id": classroom.class_id,
            "teacher_seat_id": classroom.teacher_seat_id,
            "user_id": student.user_id,
            "seat_id": student.seat_id,
            "context": CanonicalContext(
                user_id=student.user_id,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
        }


def _publish(buyer, name, entitlement_type="DELAYED_USE", **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"sale-mechanics:publish:{name}"):
        product = publish_store_product(
            class_id=buyer["class_id"],
            entitlement_type=entitlement_type,
            created_by_seat_id=buyer["teacher_seat_id"],
            name=name,
            **definition,
        )
    db.session.commit()
    return product


def _granted_units(buyer, product):
    return (
        db.session.query(EntitlementEvent)
        .filter_by(
            class_id=buyer["class_id"],
            target_seat_id=buyer["seat_id"],
            product_id=product.product_lineage_uuid,
            event_type="GRANTED",
        )
        .all()
    )


def _checking(buyer):
    """Settled checking balance.

    Settlement is explicit because posted-but-unsettled rows are invisible to
    the balance query, and a purchase that charged the wrong amount would look
    identical to one that charged nothing.
    """
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"sale-mechanics:settle:{uuid.uuid4().hex}",
    ):
        settle_ledger_balances(buyer["seat_id"], buyer["class_id"])
    checking, _savings = get_available_balances(buyer["seat_id"], buyer["class_id"])
    return checking


class TestBundleGrantsEveryUnit:
    """Defect #30: a bundle charges once and must grant every unit it sold.

    DOM-STORE-001 forbids storing a remaining-units counter, so a bundle is not
    one entitlement that decrements — it is N independent entitlement
    lifecycles created by one purchase. Counting rows is therefore the only
    honest way to ask whether the student got what they paid for.
    """

    def test_bundle_of_three_grants_three_units_for_one_charge(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Snack Pack", price="10.00",
                is_bundle=True, bundle_quantity=3,
            )
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )

            assert result.success is True
            assert result.quantity_granted == 3
            events = _granted_units(buyer, product)
            assert len(events) == 3
            # One purchase, so one correlation id across all three lifecycles...
            assert len({e.correlation_id for e in events}) == 1
            # ...but three distinct entitlements, each independently usable.
            assert len({e.entitlement_id for e in events}) == 3
            # Priced per bundle, not per unit: 10.00, not 30.00.
            assert before - _checking(buyer) == Decimal("10.00")

    def test_buying_two_bundles_grants_six_units_and_charges_twice(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Snack Pack Double", price="10.00",
                is_bundle=True, bundle_quantity=3,
            )
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=2,
            )

            assert result.success is True
            assert result.quantity_granted == 6
            assert len(_granted_units(buyer, product)) == 6
            assert before - _checking(buyer) == Decimal("20.00")

    def test_non_bundle_grants_one_unit_per_purchase(self, app, buyer):
        """The control case — the bundle multiplier must not leak into ordinary items."""
        with app.app_context():
            product = _publish(buyer, "Single Snack", price="10.00")
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=2,
            )

            assert result.quantity_granted == 2
            assert before - _checking(buyer) == Decimal("20.00")


class TestSingleUnitPurchaseRules:
    @pytest.mark.parametrize("entitlement_type", ["IMMEDIATE_USE", "PRIVILEGE"])
    def test_single_unit_types_reject_multiple_quantity(self, app, buyer, entitlement_type):
        with app.app_context():
            product = _publish(
                buyer,
                f"Single state {entitlement_type}",
                entitlement_type=entitlement_type,
                price="10.00",
            )
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=2,
            )

            assert result.success is False
            assert result.error_code == "QUANTITY_NOT_ALLOWED"
            assert _granted_units(buyer, product) == []
            assert _checking(buyer) == before


class TestVersionedProductDerivations:
    def test_edit_preserves_stock_and_collective_progress(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer,
                "Editable Goal",
                entitlement_type="COLLECTIVE_GOAL",
                price="10.00",
                inventory_total=4,
                collective_goal_type="fixed",
                collective_goal_target=10,
                collective_goal_expires_at=utc_now() + timedelta(days=30),
            )
            before = _checking(buyer)
            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            assert result.success is True
            assert _checking(buyer) == before - Decimal("10.00")

            current = StoreProduct.query.filter_by(policy_uuid=product.policy_uuid).one()
            with FEATContext(
                "FEAT-TEST-SETUP",
                idempotency_key=f"sale-mechanics:edit:{product.product_lineage_uuid}",
            ):
                successor = store_service.supersede_product(
                    current=current,
                    definition={
                        "name": "Editable Goal Revised",
                        "price": Decimal("12.00"),
                        "item_type": "collective",
                        "inventory_total": 4,
                        "collective_goal_type": "fixed",
                        "collective_goal_target": 10,
                        "collective_goal_expires_at": utc_now() + timedelta(days=30),
                    },
                    actor_seat_id=buyer["teacher_seat_id"],
                )
            db.session.commit()

            assert successor.product_lineage_uuid == product.product_lineage_uuid
            assert store_service.stock_remaining(successor) == 3
            assert count_goal_participants(
                buyer["class_id"], [successor.product_lineage_uuid]
            )[successor.product_lineage_uuid] == 1


class TestPurchaseReversalInventory:
    def test_void_revokes_grant_and_returns_stock(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer,
                "Reversible Stock",
                price="10.00",
                inventory_total=2,
            )
            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            assert result.success is True
            db.session.commit()

            purchase = (
                Transaction.query
                .filter_by(class_id=buyer["class_id"], seat_id=buyer["seat_id"], type="purchase")
                .order_by(Transaction.id.desc())
                .first()
            )
            assert purchase is not None
            # execute_void_transaction opens its own FEAT-LED-002 envelope.
            # Wrapping it in another non-scaffold context is forbidden nesting,
            # and the void writes ledger records under purchase.correlation_id,
            # which the FEAT-LED-002 before_flush check compares against the
            # active correlation.
            execute_void_transaction(
                purchase,
                correlation_id=purchase.correlation_id,
                idempotency_key=f"sale-mechanics:void:{purchase.id}",
            )
            db.session.commit()

            live_product = StoreProduct.query.filter_by(
                class_id=buyer["class_id"],
                product_lineage_uuid=product.product_lineage_uuid,
                availability_state="IN_USE",
            ).one()
            assert store_service.stock_remaining(live_product) == 2
            events = _granted_units(buyer, product)
            assert len(events) == 1
            revoked = EntitlementEvent.query.filter_by(
                class_id=buyer["class_id"],
                entitlement_id=events[0].entitlement_id,
                event_type="REVOKED",
            ).one()
            assert revoked.payload["reason"] == "reversal_propagated"

class TestBulkDiscountChangesTheDebit:
    """Defect #31: the quoted price and the charged price have to agree.

    The discount is a promise made on the item card. Displaying it while
    charging list price is not a rounding disagreement, it is a different
    transaction than the one the student consented to.
    """

    def test_below_threshold_charges_full_price(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Pencil Bulk Low", price="10.00",
                bulk_discount_enabled=True,
                bulk_discount_quantity=5,
                bulk_discount_percentage=20,
            )
            before = _checking(buyer)

            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=4,
            )

            assert before - _checking(buyer) == Decimal("40.00")

    def test_at_threshold_discounts_the_whole_order(self, app, buyer):
        """The card says "buy 5+ for 20% off", so all five units are discounted.

        Discounting only the units past the threshold would be defensible
        arithmetic and indefensible advertising.
        """
        with app.app_context():
            product = _publish(
                buyer, "Pencil Bulk At", price="10.00",
                bulk_discount_enabled=True,
                bulk_discount_quantity=5,
                bulk_discount_percentage=20,
            )
            before = _checking(buyer)

            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=5,
            )

            assert before - _checking(buyer) == Decimal("40.00")

    def test_above_threshold_discounts_every_unit(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Pencil Bulk Above", price="10.00",
                bulk_discount_enabled=True,
                bulk_discount_quantity=5,
                bulk_discount_percentage=20,
            )
            before = _checking(buyer)

            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=8,
            )

            assert before - _checking(buyer) == Decimal("64.00")

    def test_discount_rounds_half_up_to_cents(self, app, buyer):
        """3.33 x 5 = 16.65, less 15% = 14.1525, charged as 14.15.

        Banker's rounding would give the same answer here by luck; the case
        that matters is that the ledger receives a 2-scale amount at all, since
        an unrounded Decimal would either be truncated silently or rejected.
        """
        with app.app_context():
            product = _publish(
                buyer, "Odd Price", price="3.33",
                bulk_discount_enabled=True,
                bulk_discount_quantity=5,
                bulk_discount_percentage=15,
            )
            before = _checking(buyer)

            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=5,
            )

            assert before - _checking(buyer) == Decimal("14.15")


class TestCollectiveGoalDeadline:
    """Defect #32: past its deadline a goal is closed to new purchases.

    A goal that can no longer be reached cannot lawfully take money, because
    the thing being sold is a share in an outcome, not a unit of stock.
    """

    def test_purchase_after_deadline_is_refused_and_charges_nothing(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Lapsed Pizza Party",
                entitlement_type="COLLECTIVE_GOAL",
                price="5.00",
                collective_goal_type="fixed",
                collective_goal_target=100,
                collective_goal_expires_at=utc_now() - timedelta(days=1),
            )
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )

            assert result.success is False
            assert result.error_code == "COLLECTIVE_GOAL_EXPIRED"
            assert result.quantity_granted == 0
            assert _granted_units(buyer, product) == []
            # The refusal has to precede the ledger, not compensate it.
            assert _checking(buyer) == before

    def test_purchase_before_deadline_succeeds(self, app, buyer):
        with app.app_context():
            product = _publish(
                buyer, "Open Pizza Party",
                entitlement_type="COLLECTIVE_GOAL",
                price="5.00",
                collective_goal_type="fixed",
                collective_goal_target=100,
                collective_goal_expires_at=utc_now() + timedelta(days=30),
            )
            before = _checking(buyer)

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=2,
            )

            assert result.success is True
            assert len(_granted_units(buyer, product)) == 2
            assert before - _checking(buyer) == Decimal("10.00")
