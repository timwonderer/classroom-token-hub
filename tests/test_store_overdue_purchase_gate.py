"""While rent is overdue, only a product marked available despite it may be bought.

SPEC-STORE-001 §IV.D carries overdue purchase permission on one explicit
product flag. The purchase FEAT used to also wave through any product linked
as a rent satisfaction benefit, and the form only offers the flag on
rent-linked items, so the flag could never change an outcome. A rent perk is
granted through FEAT-OBL-003, never through the purchase path, so linkage is
not purchase authorization.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.obligation_view_model import build_student_obligation_view
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]

_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def late_class(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"overdue-gate:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"overdue-gate-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                amount=Decimal("500.00"),
                account_type="checking",
                type="payroll",
                description="Overdue gate test funding",
            )

        products = {}
        for name, essential in (("linked", False), ("linked_essential", True)):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"overdue-gate:publish:{name}"):
                products[name] = publish_store_product(
                    class_id=classroom.class_id,
                    entitlement_type="DELAYED_USE",
                    created_by_seat_id=classroom.teacher_seat_id,
                    name=f"Overdue gate {name}",
                    price="5.00",
                    available_with_overdue_obligations=essential,
                )
        customize_rent_settings(
            classroom.class_id,
            frequency_type="monthly",
            due_day_of_month=1,
            first_rent_due_date=_FIRST_DUE,
            grace_period_days=3,
            rent_amount=Decimal("50.00"),
            late_penalty_amount=Decimal("0.00"),
            prevent_purchase_when_late=True,
            satisfaction_benefits=[
                {
                    "entitlement_type": "DELAYED_USE",
                    "quantity": 1,
                    "product_lineage_uuid": product.product_lineage_uuid,
                }
                for product in products.values()
            ],
        )
        # Cycle 1 falls due on 2026-01-01 and is never paid.
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_FIRST_DUE)
        db.session.commit()

        rent_view = build_student_obligation_view(student.seat_id, classroom.class_id, "RENT")
        period = rent_view.current_period if rent_view else {}
        assert period.get("is_late") or period.get("is_past_due"), "fixture must leave rent overdue"

        yield {
            "classroom": classroom,
            "products": products,
            "context": CanonicalContext(
                user_id=student.user_id,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
        }


def _buy(late_class, name):
    return execute_store_purchase(
        canonical_context=late_class["context"],
        policy_uuid=late_class["products"][name].policy_uuid,
        quantity=1,
        idempotency_key=f"overdue-gate-buy:{uuid.uuid4().hex}",
    )


def test_rent_linked_product_without_the_overdue_flag_is_blocked_while_late(app, late_class):
    with app.app_context():
        result = _buy(late_class, "linked")

        assert result.success is False
        assert result.error_code == "RENT_PAST_DUE_PURCHASE_BLOCKED"
        classroom = late_class["classroom"]
        seat_id = late_class["context"].seat_id
        assert EntitlementEvent.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=seat_id,
            product_id=late_class["products"]["linked"].product_lineage_uuid,
        ).count() == 0
        assert Transaction.query.filter_by(
            class_id=classroom.class_id, seat_id=seat_id, type="purchase",
        ).count() == 0


def test_product_marked_available_when_overdue_can_be_bought_while_late(app, late_class):
    with app.app_context():
        result = _buy(late_class, "linked_essential")

        assert result.success is True, result.error_message
        assert result.quantity_granted == 1
