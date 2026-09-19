"""The Store holding limit binds every acquisition source.

DOM-STORE-001 §VIII.A makes the limit source-independent: a student's active
quantity for a product lineage must not exceed it after *any* lawful grant, and
SPEC-STORE-001 §V.A refuses an over-limit grant whole rather than trimming it.
Before this was centralized only the purchase FEAT consulted the limit, so a
teacher grant or a rent perk could push a student past it.

Possession is counted, not stored: a GRANTED lineage without a CONSUMED,
EXPIRED or REVOKED terminal event is held.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.direct_entitlement_grant_feat import execute_direct_grant
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent
from app.services import entitlement_service
from app.services.context_resolver import CanonicalContext
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]

_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def classroom(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        for student in classroom.students[:2]:
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"holding:fund:{student.seat_id}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"holding-fund:{student.seat_id}",
                    seat_id=student.seat_id,
                    class_id=classroom.class_id,
                    amount=Decimal("500.00"),
                    account_type="checking",
                    type="payroll",
                    description="Holding limit test funding",
                )
        db.session.commit()
        yield classroom


def _publish(classroom, name, entitlement_type, **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"holding:publish:{name}"):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type=entitlement_type,
            created_by_seat_id=classroom.teacher_seat_id,
            name=name,
            **definition,
        )
    db.session.commit()
    return product


def _student_context(classroom, index=0):
    student = classroom.students[index]
    return CanonicalContext(
        user_id=student.user_id,
        class_id=classroom.class_id,
        seat_id=student.seat_id,
        actor_role="student",
    )


def _teacher_context(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user_id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id,
        actor_role="teacher",
    )


def _buy(classroom, product, index=0):
    return execute_store_purchase(
        canonical_context=_student_context(classroom, index),
        policy_uuid=product.policy_uuid,
        quantity=1,
        idempotency_key=f"holding-buy:{uuid.uuid4().hex}",
    )


def _held(classroom, product, index=0):
    return entitlement_service.get_active_holding_quantity(
        class_id=classroom.class_id,
        seat_id=classroom.students[index].seat_id,
        product_lineage_uuid=product.product_lineage_uuid,
    )


def test_teacher_grant_cannot_exceed_the_holding_limit(app, classroom):
    with app.app_context():
        product = _publish(
            classroom, "Hall Pass Card", "HALL_PASS", price="1.00", holding_limit=2,
        )
        assert _buy(classroom, product).success is True

        refused = execute_direct_grant(
            canonical_context=_teacher_context(classroom),
            target_seat_id=classroom.students[0].seat_id,
            policy_uuid=product.policy_uuid,
            quantity=2,
        )
        assert refused.success is False
        assert refused.error_code == "HOLDING_LIMIT_EXCEEDED"
        assert _held(classroom, product) == 1

        granted = execute_direct_grant(
            canonical_context=_teacher_context(classroom),
            target_seat_id=classroom.students[0].seat_id,
            policy_uuid=product.policy_uuid,
            quantity=1,
        )
        assert granted.success is True
        assert _held(classroom, product) == 2

        # The grant counts against the purchase path too.
        blocked = _buy(classroom, product)
        assert blocked.success is False
        assert blocked.error_code == "HOLDING_LIMIT_EXCEEDED"


def test_holding_limit_counts_active_holdings_not_lifetime_acquisitions(app, classroom):
    with app.app_context():
        product = _publish(
            classroom, "Homework Pass", "DELAYED_USE", price="5.00", holding_limit=1,
        )
        assert _buy(classroom, product).success is True
        assert _buy(classroom, product).error_code == "HOLDING_LIMIT_EXCEEDED"

        grant = EntitlementEvent.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=classroom.students[0].seat_id,
            product_id=product.product_lineage_uuid,
            event_type="GRANTED",
        ).one()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="holding:consume"):
            entitlement_service.consume_entitlement(
                entitlement_id=grant.entitlement_id,
                class_id=grant.class_id,
                target_seat_id=grant.target_seat_id,
                actor_seat_id=grant.target_seat_id,
                product_id=grant.product_id,
                entitlement_type=grant.entitlement_type,
                acquisition_type=grant.acquisition_type,
                correlation_id=grant.correlation_id,
            )
        db.session.commit()

        assert _held(classroom, product) == 0
        assert _buy(classroom, product).success is True


def test_another_seats_holdings_do_not_count(app, classroom):
    with app.app_context():
        product = _publish(
            classroom, "Late Pass", "DELAYED_USE", price="5.00", holding_limit=1,
        )
        assert _buy(classroom, product, index=1).success is True
        assert _buy(classroom, product, index=0).success is True


def test_rent_perk_at_the_holding_limit_is_refused_and_rent_stays_satisfied(app, classroom):
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        product = _publish(
            classroom, "Rent Perk Pass", "DELAYED_USE", price="5.00", holding_limit=1,
        )
        customize_rent_settings(
            classroom.class_id,
            frequency_type="monthly",
            due_day_of_month=1,
            first_rent_due_date=_FIRST_DUE,
            grace_period_days=3,
            rent_amount=Decimal("50.00"),
            late_penalty_amount=Decimal("0.00"),
            satisfaction_benefits=[{
                "entitlement_type": "DELAYED_USE",
                "quantity": 1,
                "product_lineage_uuid": product.product_lineage_uuid,
            }],
        )
        assert _buy(classroom, product).success is True

        seat_id = classroom.students[0].seat_id
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_FIRST_DUE)
        correlation_id = f"rent:{classroom.class_id}:{seat_id}:cycle:1"
        result = execute_rent_payment(
            classroom.class_id, seat_id, correlation_id,
            idempotency_key=f"rent-pay:{correlation_id}:cmd",
        )

        assert result.success is True, result.error_message
        assert result.fully_paid is True
        assert result.passes_awarded == 0
        assert EntitlementEvent.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=seat_id,
            product_id=product.product_lineage_uuid,
            acquisition_type="PERK",
        ).count() == 0
        assert _held(classroom, product) == 1
