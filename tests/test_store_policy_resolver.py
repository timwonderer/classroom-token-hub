"""
Test the store's write/read split.

Two halves, and the split is the point:

* ``store_service.publish_product`` is the one seam that writes a product, so
  it is where SPEC-STORE-001 §V configuration validity is enforced.
* ``StorePolicyResolver`` only reads. Resolution is exact — a ``policy_uuid``
  names one immutable *version*, never a product that must be inferred from an
  identifier plus a timestamp.

The class of defect these guard against is version ambiguity: entitlements
freeze the version they were sold under, so an edit must not retroactively
change the terms of anything already bought.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from app.extensions import db
from app.feats.base import FEATContext
from app.models import StoreProduct
from app.services import store_service
from app.services.store_service import InvalidDefinition, UnknownDefinitionField
from app.services.store_policy_resolver import (
    StorePolicyResolver,
    PolicyNotFound,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.store_products import publish_store_product


@pytest.fixture
def canonical_classroom(app):
    """Create a canonical classroom through production code."""
    with app.app_context():
        return provision_classroom("chemistry_p1")


@pytest.fixture
def test_class(canonical_classroom):
    return {"class_id": canonical_classroom.class_id}


@pytest.fixture
def test_user(canonical_classroom):
    return {"user_id": canonical_classroom.teacher_user_id}


@pytest.fixture
def teacher_seat(canonical_classroom):
    return {"seat_id": canonical_classroom.teacher_seat_id}


class TestPublicationValidation:
    """SPEC-STORE-001 §V, enforced where a product is written.

    These rules previously lived in a payload parser that nothing called any
    more, which meant a teacher could publish a bundled immediate-use item or a
    collective goal with no deadline and nothing would object.
    """

    def _publish(self, class_id, seat_id, **definition):
        return publish_store_product(
            class_id=class_id,
            created_by_seat_id=seat_id,
            **definition,
        )

    def test_rejects_unknown_definition_field(self, app, test_class, teacher_seat):
        """An unrecognized field is a caller bug, not a value to ignore."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:unknown-field"):
                with pytest.raises(UnknownDefinitionField):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        made_up_field="should_fail",
                    )

    def test_rejects_negative_price(self, app, test_class, teacher_seat):
        """SPEC-STORE-001 §V.C: a product cannot pay the student to take it."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:negative-price"):
                with pytest.raises(InvalidDefinition, match="price cannot be negative"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        price="-10.00",
                    )

    def test_rejects_expiry_on_immediate_use(self, app, test_class, teacher_seat):
        """SPEC-STORE-001 §V.A: an immediate item is consumed at purchase, so
        there is no post-purchase window for an expiry to close."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:immediate-expiry"):
                with pytest.raises(InvalidDefinition, match="cannot have auto_expiry_days"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="IMMEDIATE_USE",
                        auto_expiry_days=30,
                    )

    def test_rejects_bundle_on_immediate_use(self, app, test_class, teacher_seat):
        """A bundle grants several unexercised units; an immediate item cannot
        hold even one, because it is spent the moment it is bought."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:immediate-bundle"):
                with pytest.raises(InvalidDefinition, match="cannot be bundled"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="IMMEDIATE_USE",
                        is_bundle=True,
                        bundle_quantity=5,
                    )

    def test_rejects_bundle_of_one(self, app, test_class, teacher_seat):
        """A "bundle" of one is the defect this whole mechanic was built to
        fix: a listing promising several uses that grants a single lifecycle."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:bundle-of-one"):
                with pytest.raises(InvalidDefinition, match="more than one unit"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        is_bundle=True,
                        bundle_quantity=1,
                    )

    def test_accepts_bundle_on_delayed_use(self, app, test_class, teacher_seat):
        """Delayed-use items hold multiple unexercised units, so they bundle."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:delayed-bundle"):
                product = self._publish(
                    test_class["class_id"], teacher_seat["seat_id"],
                    entitlement_type="DELAYED_USE",
                    price="5.00",
                    is_bundle=True,
                    bundle_quantity=3,
                )
            config = StorePolicyResolver.resolve_store_item(product.policy_uuid)
            assert config.bundle_quantity == 3

    def test_rejects_bulk_discount_out_of_range(self, app, test_class, teacher_seat):
        """A discount outside (0, 100] cannot describe a charge."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:bulk-range"):
                with pytest.raises(InvalidDefinition, match="bulk_discount_percentage"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        price="5.00",
                        bulk_discount_enabled=True,
                        bulk_discount_quantity=3,
                        bulk_discount_percentage=150,
                    )

    def test_rejects_bulk_discount_threshold_of_one(self, app, test_class, teacher_seat):
        """A threshold of one is not a bulk discount, it is the price."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:bulk-threshold"):
                with pytest.raises(InvalidDefinition, match="bulk_discount_quantity"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        price="5.00",
                        bulk_discount_enabled=True,
                        bulk_discount_quantity=1,
                        bulk_discount_percentage=10,
                    )

    def test_rejects_collective_goal_without_deadline(self, app, test_class, teacher_seat):
        """Defect #32: a goal with no deadline can never close, so the class
        can neither reach it nor be released from it."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:goal-no-deadline"):
                with pytest.raises(InvalidDefinition, match="deadline"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="COLLECTIVE_GOAL",
                        price="5.00",
                        collective_goal_type="fixed",
                        collective_goal_target=100,
                    )

    def test_rejects_collective_goal_with_per_purchase_mechanics(self, app, test_class, teacher_seat):
        """SPEC-STORE-001 §V.B: a goal is a shared pot, so per-purchase
        mechanics have nothing to attach to.

        Bundling and the bulk discount are refused by one guard, because they
        fail for one reason: both price a single student's order, and a goal is
        not counted that way. The goal says so in its own words rather than
        being lumped in with the types that simply cannot hold a second unit.
        """
        with app.app_context():
            goal = dict(
                entitlement_type="COLLECTIVE_GOAL",
                price="5.00",
                collective_goal_type="fixed",
                collective_goal_target=100,
                collective_goal_expires_at=utc_now() + timedelta(days=30),
            )
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:goal-bundle"):
                with pytest.raises(InvalidDefinition, match="bundle or bulk discount"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        is_bundle=True, bundle_quantity=5, **goal,
                    )
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:goal-bulk"):
                with pytest.raises(InvalidDefinition, match="bundle or bulk discount"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        bulk_discount_enabled=True,
                        bulk_discount_quantity=3,
                        bulk_discount_percentage=10,
                        **goal,
                    )

    def test_rejects_goal_fields_on_non_goal_item(self, app, test_class, teacher_seat):
        """The mutual exclusion runs both ways: goal settings on an ordinary
        item would be stored and silently never read."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:goal-fields-on-delayed"):
                with pytest.raises(InvalidDefinition, match="only meaningful on a collective goal"):
                    self._publish(
                        test_class["class_id"], teacher_seat["seat_id"],
                        entitlement_type="DELAYED_USE",
                        price="5.00",
                        collective_goal_target=100,
                    )

    def test_accepts_complete_collective_goal(self, app, test_class, teacher_seat):
        """The valid shape, so the rules above are shown to be discriminating
        rather than merely restrictive."""
        with app.app_context():
            deadline = utc_now() + timedelta(days=30)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-publish:goal-valid"):
                product = self._publish(
                    test_class["class_id"], teacher_seat["seat_id"],
                    entitlement_type="COLLECTIVE_GOAL",
                    price="5.00",
                    collective_goal_type="fixed",
                    collective_goal_target=100,
                    collective_goal_expires_at=deadline,
                )
            config = StorePolicyResolver.resolve_store_item(product.policy_uuid)
            assert config.entitlement_type == "COLLECTIVE_GOAL"
            assert config.collective_goal_target == 100
            assert config.collective_goal_expires_at is not None


class TestStorePolicyResolver:
    """Exact resolution by version UUID."""

    def test_resolve_store_item_exact_match(self, app, test_class, teacher_seat):
        """Resolution returns the version's own terms.

        ``product_id`` on the resolved config is the *lineage* — the product —
        while ``policy_uuid`` is the version. Entitlement history keys off the
        former and pricing off the latter, which is why both are exposed.
        """
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:exact-match"):
                product = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    price="50.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                )

            config = StorePolicyResolver.resolve_store_item(product.policy_uuid)

            assert config.product_id == product.product_lineage_uuid
            assert config.entitlement_type == "DELAYED_USE"
            assert config.price == Decimal("50.00")
            assert config.policy_uuid == product.policy_uuid
            assert config.class_id == test_class["class_id"]

    def test_resolve_store_item_not_found(self, app):
        """Test PolicyNotFound when UUID doesn't exist."""
        with app.app_context():
            with pytest.raises(PolicyNotFound):
                StorePolicyResolver.resolve_store_item("nonexistent-uuid-12345")

    def test_derived_flags_are_not_declared(self, app, test_class, teacher_seat):
        """``is_purchasable`` and ``supports_direct_grants`` are read off the
        row rather than stored beside it, so they cannot contradict it.

        A hidden product is unbuyable because it is hidden, not because someone
        also remembered to flip a second flag; and hall passes are the only
        catalog type a teacher may hand out without a sale.
        """
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:derived-flags"):
                hall_pass = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="HALL_PASS",
                    created_by_seat_id=teacher_seat["seat_id"],
                )
                hidden = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    price="5.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                    availability_state=store_service.HIDDEN,
                )

            resolved_pass = StorePolicyResolver.resolve_store_item(hall_pass.policy_uuid)
            assert resolved_pass.supports_direct_grants is True
            assert resolved_pass.is_purchasable is True

            resolved_hidden = StorePolicyResolver.resolve_store_item(hidden.policy_uuid)
            assert resolved_hidden.supports_direct_grants is False
            assert resolved_hidden.is_purchasable is False

    def test_list_store_policies_excludes_retired_versions(self, app, test_class, teacher_seat):
        """Discovery is the live catalog; retired versions stay resolvable
        individually for the entitlements that froze them."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:list-live"):
                live = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    name="Live",
                    price="5.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                )
                retired = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    name="Retired",
                    price="6.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                    availability_state=store_service.RETIRED,
                )

            listed = {p.policy_uuid for p in StorePolicyResolver.list_store_policies(test_class["class_id"])}
            assert live.policy_uuid in listed
            assert retired.policy_uuid not in listed

            # Still individually resolvable — an entitlement sold under it must
            # keep reading its own terms.
            assert StorePolicyResolver.resolve_store_item(retired.policy_uuid).price == Decimal("6.00")

    def test_list_store_policies_is_class_scoped(self, app, test_class, teacher_seat):
        """Multi-tenancy: one class's catalog never leaks into another's."""
        with app.app_context():
            other = provision_classroom("biology_block_a")
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:scope-mine"):
                mine = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    price="5.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                )
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:scope-theirs"):
                theirs = publish_store_product(
                    class_id=other.class_id,
                    entitlement_type="DELAYED_USE",
                    price="5.00",
                    created_by_seat_id=other.teacher_seat_id,
                )

            listed = {p.policy_uuid for p in StorePolicyResolver.list_store_policies(test_class["class_id"])}
            assert mine.policy_uuid in listed
            assert theirs.policy_uuid not in listed

    def test_list_store_policies_unknown_class_is_empty(self, app):
        """An unknown class has no catalog rather than an error — discovery is
        a read and callers should not have to distinguish the two."""
        with app.app_context():
            assert StorePolicyResolver.list_store_policies("no-such-class") == []


class TestVersionSupersession:
    """Editing publishes a new version; it does not rewrite the old one.

    This replaces an older suite that asserted two *live* policies could share
    one ``product_id``. Under the single-table model that state is now
    impossible by construction — a partial unique index permits exactly one
    ``IN_USE`` version per lineage — so the property worth proving is that
    supersession preserves the terms already sold.
    """

    def test_supersede_retires_old_version_and_keeps_lineage(self, app, test_class, teacher_seat):
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-supersede:publish-v1"):
                v1 = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    name="Notebook",
                    price="50.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                )

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-supersede:publish-v2"):
                current = db.session.query(StoreProduct).filter_by(
                    policy_uuid=v1.policy_uuid
                ).one()
                v2_row = store_service.supersede_product(
                    current=current,
                    definition={
                        "name": "Notebook",
                        "price": "75.00",
                        "item_type": "delayed",
                    },
                    actor_seat_id=teacher_seat["seat_id"],
                )
                v2_uuid = v2_row.policy_uuid

            # Same product, different versions.
            assert v2_uuid != v1.policy_uuid
            resolved_v1 = StorePolicyResolver.resolve_store_item(v1.policy_uuid)
            resolved_v2 = StorePolicyResolver.resolve_store_item(v2_uuid)
            assert resolved_v1.product_id == resolved_v2.product_id

            # The old terms survive the edit; anything bought at 50.00 still
            # resolves to 50.00.
            assert resolved_v1.price == Decimal("50.00")
            assert resolved_v2.price == Decimal("75.00")

            # Only the new version is on sale, and only it is discoverable.
            assert resolved_v1.is_purchasable is False
            assert resolved_v2.is_purchasable is True
            listed = {p.policy_uuid for p in StorePolicyResolver.list_store_policies(test_class["class_id"])}
            assert listed == {v2_uuid}

    def test_deleting_one_version_leaves_the_other_resolvable(self, app, test_class, teacher_seat):
        """Versions of ONE lineage are independent rows; removing one is not a lineage-wide event.

        The two products must share a lineage for this to mean anything. Two
        bare ``publish_store_product`` calls mint a fresh lineage each, so the
        test would only have shown that deleting one product leaves a different
        product alone. Superseding also respects
        ``uq_store_products_one_live_per_lineage``, which forbids two IN_USE
        rows in one lineage.
        """
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-supersede:delete-publish"):
                v1 = publish_store_product(
                    class_id=test_class["class_id"],
                    entitlement_type="DELAYED_USE",
                    name="Notebook",
                    price="50.00",
                    created_by_seat_id=teacher_seat["seat_id"],
                )

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-supersede:delete-supersede"):
                current = db.session.query(StoreProduct).filter_by(
                    policy_uuid=v1.policy_uuid
                ).one()
                v2_row = store_service.supersede_product(
                    current=current,
                    definition={
                        "name": "Notebook",
                        "price": "60.00",
                        "item_type": "delayed",
                    },
                    actor_seat_id=teacher_seat["seat_id"],
                )
                v2_uuid = v2_row.policy_uuid
                v2_lineage = v2_row.product_lineage_uuid

            assert v2_lineage == v1.product_lineage_uuid

            # Delete the retired version, keeping the live one.
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-supersede:delete-cleanup"):
                row = db.session.query(StoreProduct).filter_by(policy_uuid=v1.policy_uuid).one()
                assert row.availability_state != store_service.IN_USE
                db.session.delete(row)
                db.session.flush()

            with pytest.raises(PolicyNotFound):
                StorePolicyResolver.resolve_store_item(v1.policy_uuid)

            surviving = StorePolicyResolver.resolve_store_item(v2_uuid)
            assert surviving.price == Decimal("60.00")
            assert surviving.product_id == v2_lineage
