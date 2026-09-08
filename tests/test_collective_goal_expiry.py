"""Behavioral tests for the collective-goal expiry sweep.

DOM-STORE-001 §5 requires a collective-goal entitlement to "record ``EXPIRED``
when the goal is not reached by the deadline and coordinate a lawful refund."
Only the purchase-time half existed: a lapsed goal stopped selling, but everyone
already inside it kept an entitlement they could never exercise and stayed
charged for it.

Every test here asserts against the two surfaces the student actually feels —
whether the entitlement terminated, and whether the money came back — because
those are the two things that were missing, and it is entirely possible to get
one right while getting the other wrong.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, StoreProduct, Transaction, TransactionStatus
from app.scheduled_tasks import run_collective_goal_expiry_job
from app.services.context_resolver import CanonicalContext
from app.services.store.collective_goals import count_goal_participants
from app.services.ledger_balance_query_service import get_available_balances
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import (
    create_ledger_idempotent_transaction,
    settle_ledger_balances,
)
from tests.helpers.store_products import publish_store_product

pytestmark = [pytest.mark.regression]


@pytest.fixture
def classroom(app):
    """A class whose students are all funded.

    Funding matters for the same reason it does in the sale-mechanics suite: an
    unfunded seat resolves debits through overdraft, so a refund that never
    arrived and one that did would both leave a negative balance.
    """
    with app.app_context():
        room = provision_classroom("chemistry_p1")
        for student in room.students:
            with FEATContext(
                "FEAT-TEST-SETUP",
                idempotency_key=f"goal-expiry:fund:{student.seat_id}",
            ):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"goal-expiry-fund:{student.seat_id}",
                    seat_id=student.seat_id,
                    class_id=room.class_id,
                    user_id=student.user_id,
                    amount=Decimal("1000.00"),
                    account_type="checking",
                    type="payroll",
                    description="Goal expiry test funding",
                )
        db.session.commit()
        yield room


def _context(room, student):
    return CanonicalContext(
        user_id=student.user_id,
        class_id=room.class_id,
        seat_id=student.seat_id,
        actor_role="student",
    )


def _publish_goal(room, name, *, target, expires_at, price="10.00", goal_type="fixed"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"goal-expiry:publish:{name}"):
        product = publish_store_product(
            class_id=room.class_id,
            entitlement_type="COLLECTIVE_GOAL",
            created_by_seat_id=room.teacher_seat_id,
            name=name,
            price=price,
            collective_goal_type=goal_type,
            collective_goal_target=target,
            collective_goal_expires_at=expires_at,
        )
    db.session.commit()
    return product


def _buy(room, student, product):
    result = execute_store_purchase(
        canonical_context=_context(room, student),
        policy_uuid=product.policy_uuid,
        quantity=1,
    )
    assert result.success is True, result.error_message
    db.session.commit()
    return result


def _events(room, product, event_type):
    return (
        db.session.query(EntitlementEvent)
        .filter_by(
            class_id=room.class_id,
            product_id=product.product_lineage_uuid,
            event_type=event_type,
        )
        .all()
    )


def _checking(room, student):
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"goal-expiry:settle:{uuid.uuid4().hex}",
    ):
        settle_ledger_balances(student.seat_id, room.class_id)
    checking, _savings = get_available_balances(student.seat_id, room.class_id)
    return checking


def _expire_deadline(product):
    """Make a live goal lapse.

    Goals must be published with a future deadline (SPEC-STORE-001 §V.C.8) and
    the purchase gate refuses a lapsed one, so the only way into this state is
    to buy while the goal is live and then let the clock pass the deadline.

    What actually happens in production is that time moves, not that anyone
    edits the product — products are immutable and versioned, and the
    ``before_update`` guard on ``StoreProduct`` rightly rejects an in-place
    edit. This issues a Core UPDATE, which bypasses the ORM event, because the
    guard exists to stop application code from rewriting sold terms and this is
    standing in for the clock rather than doing that.
    """
    db.session.execute(
        sa.update(StoreProduct)
        .where(StoreProduct.policy_uuid == product.policy_uuid)
        .values(collective_goal_expires_at=utc_now() - timedelta(hours=1))
    )
    db.session.commit()


class TestUnmetGoalIsExpiredAndRefunded:
    """The defect: a goal that ran out of time kept both the entitlement and the money."""

    def test_lapsed_unmet_goal_expires_every_buy_in_and_refunds_it(self, app, classroom):
        with app.app_context():
            room = classroom
            student = room.students[0]
            product = _publish_goal(
                room, "Class Pizza Party",
                target=100,  # unreachable — the class is far smaller
                expires_at=utc_now() + timedelta(days=1),
            )
            before = _checking(room, student)
            _buy(room, student, product)
            assert before - _checking(room, student) == Decimal("10.00")

            _expire_deadline(product)
            run_collective_goal_expiry_job()
            db.session.commit()

            # The entitlement terminated...
            expired = _events(room, product, "EXPIRED")
            assert len(expired) == 1
            assert expired[0].target_seat_id == student.seat_id
            # ...reusing the grant's lineage, so there is one lifecycle, not two.
            granted = _events(room, product, "GRANTED")
            assert expired[0].entitlement_id == granted[0].entitlement_id

            # ...and the money came back in full.
            assert _checking(room, student) == before
            retired = StoreProduct.query.filter_by(
                product_lineage_uuid=product.product_lineage_uuid,
                class_id=room.class_id,
            ).filter(StoreProduct.availability_state == "RETIRED").first()
            assert retired is not None
            assert count_goal_participants(room.class_id, [product.product_lineage_uuid]) == {}

    def test_refund_is_linked_to_the_purchase_it_reverses(self, app, classroom):
        """A refund that is not linked to its purchase is an unexplained credit."""
        with app.app_context():
            room = classroom
            student = room.students[0]
            product = _publish_goal(
                room, "Linked Refund Goal",
                target=100, expires_at=utc_now() + timedelta(days=1),
            )
            _buy(room, student, product)
            # Settle first so the original is a posted, already-paid charge.
            _checking(room, student)
            purchase = (
                Transaction.query
                .filter_by(class_id=room.class_id, seat_id=student.seat_id, type="purchase")
                .one()
            )

            _expire_deadline(product)
            run_collective_goal_expiry_job()
            db.session.commit()

            db.session.refresh(purchase)
            # The original charge stands as historical fact; only the link
            # forward is added (SPEC-OPS-001 §3.2, INV-OPS-001).
            assert purchase.status == TransactionStatus.POSTED
            assert purchase.reversal_transaction_id is not None
            reversal = db.session.get(Transaction, purchase.reversal_transaction_id)
            assert reversal.type == "refund"
            assert reversal.amount == -purchase.amount

    def test_every_participant_is_refunded_not_just_the_first(self, app, classroom):
        with app.app_context():
            room = classroom
            buyers = room.students[:2]
            product = _publish_goal(
                room, "Multi Buyer Goal",
                target=100, expires_at=utc_now() + timedelta(days=1),
            )
            before = {s.seat_id: _checking(room, s) for s in buyers}
            for student in buyers:
                _buy(room, student, product)

            _expire_deadline(product)
            run_collective_goal_expiry_job()
            db.session.commit()

            assert len(_events(room, product, "EXPIRED")) == 2
            for student in buyers:
                assert _checking(room, student) == before[student.seat_id]


    def test_an_unsettled_charge_is_reversed_like_any_other(self, app, classroom):
        """A charge still pending at the deadline nets to zero, not to a windfall.

        Store purchases post lazily, so a goal can lapse before the debit ever
        settles. Money is only ever reversed, never voided (INV-OPS-001), so
        this takes the same path as a posted charge: the original settles, the
        compensating credit settles, and the student is where they started.
        Marking the original void instead would have dropped the debit at
        settlement while the credit still landed, leaving them ten dollars
        richer for joining a goal that failed.
        """
        with app.app_context():
            room = classroom
            student = room.students[0]
            product = _publish_goal(
                room, "Unsettled Charge Goal",
                target=100, expires_at=utc_now() + timedelta(days=1),
            )
            before = _checking(room, student)
            _buy(room, student, product)  # deliberately not settled

            _expire_deadline(product)
            run_collective_goal_expiry_job()
            db.session.commit()

            assert len(_events(room, product, "EXPIRED")) == 1
            assert _checking(room, student) == before

            purchase = (
                Transaction.query
                .filter_by(class_id=room.class_id, seat_id=student.seat_id, type="purchase")
                .one()
            )
            assert purchase.status == TransactionStatus.POSTED
            assert purchase.reversal_transaction_id is not None


class TestGoalProgressAuthority:
    """Display and sweep must read the same count.

    The student store used to count every GRANTED event while the teacher store
    additionally required ``acquisition_type == "PURCHASE"``, so a teacher's
    direct grant moved one bar and not the other. Once a sweep reads that count
    the disagreement decides who gets refunded, so it is asserted directly.
    """

    def test_direct_grants_do_not_count_toward_a_goal(self, app, classroom):
        with app.app_context():
            from app.services import entitlement_service
            from app.services.store import collective_goals

            room = classroom
            product = _publish_goal(
                room, "Buy-In Only Goal",
                target=100, expires_at=utc_now() + timedelta(days=1),
            )
            _buy(room, room.students[0], product)

            recipient = room.students[1]
            with FEATContext(
                "FEAT-TEST-SETUP", idempotency_key=f"goal-expiry:grant:{recipient.seat_id}"
            ):
                db.session.add(
                    EntitlementEvent(
                        event_id=str(uuid.uuid4()),
                        entitlement_id=str(uuid.uuid4()),
                        class_id=room.class_id,
                        target_seat_id=recipient.seat_id,
                        actor_seat_id=room.teacher_seat_id,
                        product_id=product.product_lineage_uuid,
                        entitlement_type="COLLECTIVE_GOAL",
                        acquisition_type="GRANT",
                        event_type="GRANTED",
                        correlation_id=f"direct_grant_{uuid.uuid4().hex}",
                        payload={},
                        timestamp=utc_now(),
                    )
                )
            db.session.commit()

            counts = collective_goals.count_goal_participants(
                room.class_id, [product.product_lineage_uuid]
            )
            # One buy-in. The gift did not join the goal.
            assert counts[product.product_lineage_uuid] == 1

    def test_an_unresolvable_target_is_never_treated_as_met(self, app):
        """A zero target must fail closed, or a misconfigured goal denies every refund."""
        from app.services.store import collective_goals

        assert collective_goals.is_goal_met(0, 0) is False
        assert collective_goals.is_goal_met(5, 0) is False
        assert collective_goals.is_goal_met(4, 5) is False
        assert collective_goals.is_goal_met(5, 5) is True
