"""A collective-goal buy-in can be reversed, and Reverse is offered only where it works.

On 2026-10-07 a teacher in production could not reverse a student's
collective-goal purchase: the Reverse button was shown, and every press failed
with "Only delayed-use item purchases are voidable." The button and the action
decided reversibility separately. The banking page asked
``resolve_purchase_resolution_eligibility``, which accepted any active
non-insurance purchase; the action accepted delayed-use items only. The student
detail page asked neither and offered Reverse on almost every row, including an
NSF fee settled through an obligation, which SPEC-OPS-001 §VII makes final.

DOM-STORE-001 §VIII.E lets a reversal withdraw a collective-goal buy-in with a
refund, so the action now accepts it, and both pages and the action share one
gate. A purchase the Store domain does not let a reversal revoke (a privilege
here) is refused by that same gate before any money moves.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.transaction_void_feat import PurchaseNotReversible, execute_void_transaction
from app.models import EntitlementEvent, Seat, Transaction
from app.routes.admin import _reversible_transaction_ids
from app.services.context_resolver import CanonicalContext
from app.services.ledger_balance_query_service import get_available_balance
from app.services.ledger_correction_service import resolve_purchase_resolution_eligibility
from app.services.ledger_provenance_query_service import has_exact_reversal
from app.services.store.collective_goals import count_goal_participants
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import record_ledger_fixture
from tests.helpers.store_products import publish_store_product


def _student_context(classroom):
    student = classroom.students[0]
    return student.seat_id, CanonicalContext(
        user_id=student.user_id, class_id=classroom.class_id,
        seat_id=student.seat_id, actor_role="student",
    )


def _fund(class_id, seat_id, amount, key):
    with FEATContext("FEAT-LED-001", idempotency_key=f"goal-reversal:seed:{key}"):
        record_ledger_fixture(seat_id=seat_id, class_id=class_id, amount=Decimal(amount))
    db.session.commit()


def _publish(class_id, teacher_seat_id, *, entitlement_type, name, price, **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"goal-reversal:product:{name}"):
        product = publish_store_product(
            class_id=class_id, entitlement_type=entitlement_type, name=name,
            price=price, created_by_seat_id=teacher_seat_id, **definition,
        )
    db.session.commit()
    return product


def _goal(class_id, teacher_seat_id, name="Pizza Party"):
    return _publish(
        class_id, teacher_seat_id, entitlement_type="COLLECTIVE_GOAL", name=name,
        price="750.00", collective_goal_type="whole_class",
        collective_goal_expires_at=utc_now() + timedelta(days=60),
    )


def _buy(context, product):
    result = execute_store_purchase(
        canonical_context=context, policy_uuid=product.policy_uuid, quantity=1,
    )
    assert result.success is True, result.error_code
    db.session.commit()
    return (
        Transaction.query
        .filter_by(class_id=context.class_id, seat_id=context.seat_id, type="purchase")
        .order_by(Transaction.id.desc())
        .first()
    )


@pytest.fixture
def goal_purchase(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        seat_id, context = _student_context(classroom)
        _fund(classroom.class_id, seat_id, "1000.00", "goal")
        goal = _goal(classroom.class_id, classroom.teacher_seat_id)
        purchase = _buy(context, goal)
        yield {
            "class_id": classroom.class_id, "seat_id": seat_id,
            "teacher_seat_id": classroom.teacher_seat_id,
            "goal": goal, "purchase_id": purchase.id,
        }


def test_collective_goal_buy_in_reverses_refunds_and_withdraws(app, goal_purchase):
    with app.app_context():
        purchase = db.session.get(Transaction, goal_purchase["purchase_id"])
        lineage = goal_purchase["goal"].product_lineage_uuid
        class_id, seat_id = goal_purchase["class_id"], goal_purchase["seat_id"]
        assert get_available_balance(seat_id, class_id, "checking") == Decimal("250.00")
        assert count_goal_participants(class_id, [lineage]) == {lineage: 1}

        execute_void_transaction(
            purchase, correlation_id=purchase.correlation_id,
            idempotency_key=f"goal-reversal:void:{purchase.id}",
        )
        db.session.commit()

        db.session.expire_all()
        assert get_available_balance(seat_id, class_id, "checking") == Decimal("1000.00")
        assert has_exact_reversal(purchase)
        revoked = EntitlementEvent.query.filter_by(
            class_id=class_id, target_seat_id=seat_id, event_type="REVOKED",
        ).one()
        assert revoked.payload["reversed_transaction_id"] == purchase.id
        assert count_goal_participants(class_id, [lineage]) == {}, \
            "a reversed buy-in no longer counts toward the goal"


def test_reverse_route_accepts_a_collective_goal_purchase(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        seat_id, context = _student_context(classroom)
        _fund(classroom.class_id, seat_id, "1000.00", "route")
        purchase = _buy(context, _goal(classroom.class_id, classroom.teacher_seat_id, "Route Goal"))
        purchase_id = purchase.id

    response = client.post(
        f"/admin/void-transaction/{purchase_id}",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "success"
    with app.app_context():
        assert get_available_balance(seat_id, classroom.class_id, "checking") == Decimal("1000.00")


def test_a_purchase_the_store_does_not_let_reversal_revoke_is_refused_before_money_moves(app, goal_purchase):
    with app.app_context():
        class_id, seat_id = goal_purchase["class_id"], goal_purchase["seat_id"]
        classroom_seat = db.session.get(Seat, seat_id)
        context = CanonicalContext(
            user_id=classroom_seat.user_id, class_id=class_id, seat_id=seat_id, actor_role="student",
        )
        privilege = _publish(
            class_id, goal_purchase["teacher_seat_id"], entitlement_type="PRIVILEGE",
            name="Window Seat", price="10.00",
        )
        purchase = _buy(context, privilege)
        before = get_available_balance(seat_id, class_id, "checking")

        eligibility = resolve_purchase_resolution_eligibility(purchase)
        assert eligibility.eligible is False

        with pytest.raises(PurchaseNotReversible):
            execute_void_transaction(
                purchase, correlation_id=purchase.correlation_id,
                idempotency_key=f"goal-reversal:void:{purchase.id}",
            )
        db.session.rollback()

        db.session.expire_all()
        assert get_available_balance(seat_id, class_id, "checking") == before
        assert not has_exact_reversal(purchase)
        assert purchase.id not in _reversible_transaction_ids([purchase])


def test_student_detail_offers_reverse_only_where_the_action_would_accept(app, goal_purchase):
    from app.feats.assess_obligation_feat import execute_assess_obligation
    from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_payment

    with app.app_context():
        class_id, seat_id = goal_purchase["class_id"], goal_purchase["seat_id"]
        purchase = db.session.get(Transaction, goal_purchase["purchase_id"])

        # A charge settled through an obligation, as the production NSF fee was.
        with FEATContext("FEAT-LED-001", idempotency_key="goal-reversal:fee"):
            fee = record_ledger_fixture(
                seat_id=seat_id, class_id=class_id, amount=Decimal("-25.00"),
                type="overdraft_fee", description="Non-sufficient funds fee",
            )
            db.session.flush()
            fee_id = fee.id
        db.session.commit()
        execute_assess_obligation(
            seat_id=seat_id, class_id=class_id, internal_ref="nsf:test",
            correlation_id="goal-reversal:nsf", obligation_type="NSF_FEE",
        )
        db.session.commit()
        execute_satisfy_obligation_payment(
            correlation_id="goal-reversal:nsf", class_id=class_id, seat_id=seat_id,
            ledger_transaction_id=fee_id,
        )
        db.session.commit()

        fee = db.session.get(Transaction, fee_id)
        assert _reversible_transaction_ids([purchase, fee]) == {purchase.id}

        execute_void_transaction(
            purchase, correlation_id=purchase.correlation_id,
            idempotency_key=f"goal-reversal:void:{purchase.id}",
        )
        db.session.commit()
        db.session.expire_all()
        purchase = db.session.get(Transaction, goal_purchase["purchase_id"])
        assert _reversible_transaction_ids([purchase]) == frozenset(), \
            "a reversed purchase offers no second reversal"
