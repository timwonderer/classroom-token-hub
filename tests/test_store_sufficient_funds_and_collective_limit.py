"""A store purchase needs the money, and a collective goal is one buy-in per student.

Owner rulings 2026-10-07 (FEAT-STOR-001 3.2, SPEC-ECON-003 2.3, DOM-STORE-001 5.5,
SPEC-STORE-001 1.6). On 2026-10-07 a student in production moved all of checking
($116.72) to savings, leaving $0.01, then bought 32 units of a $750 whole-class
collective goal. The purchase posted $24,000 into a negative balance, a $25 NSF fee
posted with it, and 32 collective-goal entitlements went to that one seat.
Protection was on, but savings ($426.97) could not cover the whole shortfall.

The rules now:

* a purchase may proceed only when checking, alone or with a full
  overdraft-protection transfer from savings, covers it; otherwise it is refused
  before anything posts, with no fee and no NSF obligation;
* a collective goal is bought one unit at a time, and a student who holds a
  buy-in cannot buy another.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, ObligationAssessment, Seat, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_balance_query_service import get_available_balances
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import record_ledger_fixture
from tests.helpers.store_products import publish_store_product


@pytest.fixture
def shop(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        teacher = db.session.get(Seat, classroom.teacher_seat_id)
        db.session.commit()
        yield {
            "class_id": classroom.class_id,
            "seat_id": student.seat_id,
            "student": CanonicalContext(
                user_id=student.user_id, class_id=classroom.class_id,
                seat_id=student.seat_id, actor_role="student",
            ),
            "teacher": CanonicalContext(
                user_id=teacher.user_id, class_id=classroom.class_id,
                seat_id=teacher.id, actor_role="teacher",
            ),
            "teacher_seat_id": teacher.id,
        }


def _banking(shop, *, protection, fee="25.00", key):
    changed = execute_evolve_economic_engine(
        canonical_context=shop["teacher"], class_id=shop["class_id"],
        updates={"overdraft_protection_enabled": protection, "flat_overdraft_fee": Decimal(fee)},
        feature_list=["banking"], idempotency_key=f"funds:{key}",
    )
    assert changed.success


def _fund(shop, *, checking="0.00", savings="0.00", key):
    with FEATContext("FEAT-LED-001", idempotency_key=f"funds:seed:{key}"):
        if Decimal(checking):
            record_ledger_fixture(seat_id=shop["seat_id"], class_id=shop["class_id"],
                                  amount=Decimal(checking))
        if Decimal(savings):
            record_ledger_fixture(seat_id=shop["seat_id"], class_id=shop["class_id"],
                                  account_type="savings", amount=Decimal(savings))
    db.session.commit()


def _product(shop, *, price, entitlement_type="DELAYED_USE", name="Funds Test", **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"funds:product:{name}"):
        product = publish_store_product(
            class_id=shop["class_id"], entitlement_type=entitlement_type, name=name,
            price=price, created_by_seat_id=shop["teacher_seat_id"], **definition,
        )
    db.session.commit()
    return product


def _collective(shop, *, price="750.00", name="Whole Class Pizza Party"):
    return _product(
        shop, price=price, entitlement_type="COLLECTIVE_GOAL", name=name,
        collective_goal_type="whole_class",
        collective_goal_expires_at=utc_now() + timedelta(days=60),
    )


def _rows(shop):
    return Transaction.query.filter_by(class_id=shop["class_id"], seat_id=shop["seat_id"]).count()


def _grants(shop):
    return EntitlementEvent.query.filter_by(
        class_id=shop["class_id"], target_seat_id=shop["seat_id"], event_type="GRANTED"
    ).count()


def _nsf_obligations(shop):
    return ObligationAssessment.query.filter_by(
        class_id=shop["class_id"], seat_id=shop["seat_id"], obligation_type="NSF_FEE"
    ).count()


def _balances(shop):
    return get_available_balances(shop["seat_id"], shop["class_id"])


def _buy(shop, product, quantity=1, key=None):
    return execute_store_purchase(
        canonical_context=shop["student"], policy_uuid=product.policy_uuid,
        quantity=quantity, idempotency_key=key,
    )


def _assert_refused_cleanly(shop, result, before_rows, before_balances, code):
    assert result.success is False
    assert result.error_code == code
    db.session.expire_all()
    assert _rows(shop) == before_rows, "a refused purchase posts nothing"
    assert _balances(shop) == before_balances
    assert _grants(shop) == 0
    assert _nsf_obligations(shop) == 0, "a refused purchase carries no NSF fee"


def test_production_case_is_refused_with_no_fee_and_no_grants(app, shop):
    """Checking $0.01, savings $426.97, protection on, fee $25: 32 x $750 goal."""
    with app.app_context():
        _banking(shop, protection=True, key="prod")
        _fund(shop, checking="0.01", savings="426.97", key="prod")
        goal = _collective(shop)
        before_rows, before_balances = _rows(shop), _balances(shop)

        result = _buy(shop, goal, quantity=32)

        # Refused on quantity before funds are even considered.
        _assert_refused_cleanly(shop, result, before_rows, before_balances, "QUANTITY_NOT_ALLOWED")

        # One unit is still more than checking plus savings can cover.
        result = _buy(shop, goal, quantity=1)
        _assert_refused_cleanly(shop, result, before_rows, before_balances, "INSUFFICIENT_FUNDS")


def test_short_checking_without_protection_is_refused_with_no_fee(app, shop):
    with app.app_context():
        _banking(shop, protection=False, key="noprot")
        _fund(shop, checking="5.00", savings="100.00", key="noprot")
        item = _product(shop, price="10.00")
        before_rows, before_balances = _rows(shop), _balances(shop)

        result = _buy(shop, item)

        _assert_refused_cleanly(shop, result, before_rows, before_balances, "INSUFFICIENT_FUNDS")


def test_partial_savings_cannot_rescue_a_purchase(app, shop):
    """Protection covers a shortfall only in full; $3 of savings cannot close a $5 gap."""
    with app.app_context():
        _banking(shop, protection=True, key="partial")
        _fund(shop, checking="5.00", savings="3.00", key="partial")
        item = _product(shop, price="10.00")
        before_rows, before_balances = _rows(shop), _balances(shop)

        result = _buy(shop, item)

        _assert_refused_cleanly(shop, result, before_rows, before_balances, "INSUFFICIENT_FUNDS")


def test_full_protection_transfer_still_funds_a_purchase(app, shop):
    with app.app_context():
        _banking(shop, protection=True, key="covered")
        _fund(shop, checking="2.00", savings="50.00", key="covered")
        item = _product(shop, price="10.00")

        result = _buy(shop, item)

        assert result.success is True
        db.session.expire_all()
        checking, savings = _balances(shop)
        assert checking == Decimal("0.00")
        assert savings == Decimal("42.00")
        assert _nsf_obligations(shop) == 0


def test_exact_balance_and_free_items_are_allowed(app, shop):
    with app.app_context():
        _banking(shop, protection=False, key="exact")
        _fund(shop, checking="10.00", key="exact")
        exact = _product(shop, price="10.00", name="Exact")
        free = _product(shop, price="0.00", name="Free")

        assert _buy(shop, exact).success is True
        db.session.expire_all()
        assert _balances(shop)[0] == Decimal("0.00")
        assert _buy(shop, free).success is True, "a zero-price item needs no funds"


def test_collective_goal_is_one_buy_in_per_student(app, shop):
    with app.app_context():
        _banking(shop, protection=False, key="goal")
        _fund(shop, checking="100.00", key="goal")
        goal = _collective(shop, price="5.00", name="Movie Day")

        two = _buy(shop, goal, quantity=2)
        assert two.success is False and two.error_code == "QUANTITY_NOT_ALLOWED"

        first = _buy(shop, goal, quantity=1)
        assert first.success is True

        second = _buy(shop, goal, quantity=1)
        assert second.success is False
        assert second.error_code == "COLLECTIVE_GOAL_ALREADY_JOINED"
        db.session.expire_all()
        assert _grants(shop) == 1
        assert _balances(shop)[0] == Decimal("95.00")


def test_shop_shows_spendable_amount_and_joined_goal(app, client):
    from tests.helpers.classroom_initializer import initialize_as_student
    from tests.helpers.class_domain import enable_class_feature

    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="store")
        state = {
            "class_id": classroom.class_id, "seat_id": student.seat.id,
            "student": CanonicalContext(user_id=student.user.id, class_id=classroom.class_id,
                                        seat_id=student.seat.id, actor_role="student"),
            "teacher_seat_id": classroom.teacher_seat_id,
        }
        _fund(state, checking="12.34", key="render")
        goal = _collective(state, price="5.00", name="Render Goal")
        assert _buy(state, goal).success is True

    page = client.get("/student/shop").get_data(as_text=True)

    assert 'id="spendableAmount" value="7.34"' in page
    import re
    assert re.search(r'data-item-name="Render Goal".*?disabled>\s*Joined\s*</button>', page, re.S), \
        "the joined goal's button is disabled and reads Joined"
    assert 'id="fundsWarning"' in page
