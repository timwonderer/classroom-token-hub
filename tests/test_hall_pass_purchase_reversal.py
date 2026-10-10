"""A purchased hall pass can be reversed, and a used one cannot.

Owner ruling 2026-10-08: reversing a purchase invalidates every entitlement it
paid for (SPEC-OPS-001 §3.3), hall passes included. DOM-STORE-001's direct-grant
rule governs revoking a pass on its own, not propagation from a reversed
purchase. v2.2.0 excluded HALL_PASS, so a 1,000-pass purchase made in production
on 2026-10-08 without the money could not be reversed.

Owner ruling 2026-10-09: a hall pass is used when, and only when, a hall-pass
log names it; using one writes no entitlement event. So "already used" for the
all-or-nothing gate (§3.4) is read from hall_pass_logs. An item with a request
still waiting is not reversed (owner ruling 2026-10-09): the teacher approves or
rejects the request first (DOM-SUP-001 §IX allows the reversal afterwards).
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.transaction_void_feat import PurchaseNotReversible, execute_void_transaction
from app.models import EntitlementEvent, PendingAction, Seat, Transaction
from app.routes.admin import _reversible_transaction_ids
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_hall_pass_balance
from app.services.ledger_balance_query_service import get_available_balance
from app.services.ledger_correction_service import resolve_purchase_resolution_eligibility
from app.services.ledger_provenance_query_service import has_exact_reversal
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import record_ledger_fixture
from tests.helpers.store_products import publish_store_product


@pytest.fixture
def shop(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        student = classroom.students[0]
        teacher = db.session.get(Seat, classroom.teacher_seat_id)
        with FEATContext("FEAT-LED-001", idempotency_key="hp-reversal:seed"):
            record_ledger_fixture(seat_id=student.seat_id, class_id=classroom.class_id,
                                  amount=Decimal("100.00"))
        db.session.commit()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="hp-reversal:product"):
            product = publish_store_product(
                class_id=classroom.class_id, entitlement_type="HALL_PASS", name="Hall Pass",
                price="5.00", created_by_seat_id=teacher.id,
            )
        db.session.commit()
        yield {
            "class_id": classroom.class_id,
            "seat_id": student.seat_id,
            "product": product,
            "student": CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                        seat_id=student.seat_id, actor_role="student"),
            "teacher": CanonicalContext(user_id=teacher.user_id, class_id=classroom.class_id,
                                        seat_id=teacher.id, actor_role="teacher"),
        }


def _buy(shop, quantity):
    result = execute_store_purchase(
        canonical_context=shop["student"], policy_uuid=shop["product"].policy_uuid,
        quantity=quantity,
    )
    assert result.success is True, result.error_code
    db.session.commit()
    return (
        Transaction.query
        .filter_by(class_id=shop["class_id"], seat_id=shop["seat_id"], type="purchase")
        .order_by(Transaction.id.desc())
        .first()
    )


def _use_one(shop, tag):
    from app.feats.prod import record_hall_pass_log

    log = record_hall_pass_log(
        ctx=shop["teacher"], requested_by_seat_id=shop["seat_id"],
        approved_by_seat_id=shop["teacher"].seat_id, destination="Bathroom",
        reason="teacher_approved", idempotency_key=f"hp-reversal:use:{tag}",
    ).hall_pass_log
    db.session.commit()
    return log


def _reverse(purchase):
    execute_void_transaction(
        purchase, correlation_id=purchase.correlation_id,
        idempotency_key=f"hp-reversal:void:{purchase.id}",
    )
    db.session.commit()


def test_a_purchased_hall_pass_reverses_refunds_and_revokes_every_pass(app, shop):
    with app.app_context():
        purchase = _buy(shop, 3)
        class_id, seat_id = shop["class_id"], shop["seat_id"]
        assert get_hall_pass_balance(seat_id, class_id) == 3
        assert purchase.id in _reversible_transaction_ids([purchase])

        _reverse(purchase)

        db.session.expire_all()
        assert get_available_balance(seat_id, class_id, "checking") == Decimal("100.00")
        assert has_exact_reversal(db.session.get(Transaction, purchase.id))
        assert EntitlementEvent.query.filter_by(
            class_id=class_id, target_seat_id=seat_id, entitlement_type="HALL_PASS",
            event_type="REVOKED",
        ).count() == 3
        assert get_hall_pass_balance(seat_id, class_id) == 0


def test_a_purchase_with_a_used_pass_is_refused_before_money_moves(app, shop):
    """All-or-nothing (§3.4): one logged use refuses the whole reversal."""
    with app.app_context():
        purchase = _buy(shop, 2)
        _use_one(shop, "used")
        class_id, seat_id = shop["class_id"], shop["seat_id"]
        before = get_available_balance(seat_id, class_id, "checking")

        assert resolve_purchase_resolution_eligibility(purchase).eligible is False
        assert purchase.id not in _reversible_transaction_ids([purchase])
        with pytest.raises(PurchaseNotReversible):
            execute_void_transaction(
                purchase, correlation_id=purchase.correlation_id,
                idempotency_key=f"hp-reversal:void:{purchase.id}",
            )
        db.session.rollback()

        db.session.expire_all()
        assert get_available_balance(seat_id, class_id, "checking") == before
        assert not has_exact_reversal(db.session.get(Transaction, purchase.id))
        assert get_hall_pass_balance(seat_id, class_id) == 1


def test_a_waiting_request_blocks_the_reversal_until_the_teacher_resolves_it(app, shop):
    """Owner ruling 2026-10-09: an item with a request still waiting is not reversed.

    The teacher rejects the request first; the pass is then neither pending nor
    used, and the reversal goes through (DOM-SUP-001 §IX).
    """
    from app.feats.hall_pass_request_feat import reject_hall_pass_request, submit_hall_pass_request

    with app.app_context():
        purchase = _buy(shop, 1)
        request = submit_hall_pass_request(
            ctx=shop["student"], destination="Bathroom", requested_at_utc=utc_now(),
            idempotency_key="hp-reversal:request",
        )
        db.session.commit()
        class_id, seat_id = shop["class_id"], shop["seat_id"]
        before = get_available_balance(seat_id, class_id, "checking")

        assert resolve_purchase_resolution_eligibility(purchase).eligible is False
        assert purchase.id not in _reversible_transaction_ids([purchase])
        with pytest.raises(PurchaseNotReversible, match="still waiting"):
            execute_void_transaction(
                purchase, correlation_id=purchase.correlation_id,
                idempotency_key=f"hp-reversal:void:{purchase.id}",
            )
        db.session.rollback()
        db.session.expire_all()
        assert get_available_balance(seat_id, class_id, "checking") == before

        reject_hall_pass_request(
            ctx=shop["teacher"], request_id=request.request_id,
            idempotency_key="hp-reversal:reject",
        )
        db.session.commit()
        assert PendingAction.query.filter_by(class_id=class_id).count() == 0

        _reverse(purchase)

        db.session.expire_all()
        assert has_exact_reversal(db.session.get(Transaction, purchase.id))
        assert get_hall_pass_balance(seat_id, class_id) == 0


def test_a_waiting_redemption_blocks_a_delayed_use_reversal(app, shop):
    """The same rule for every entitlement type: a pending redemption request."""
    from app.feats.entitlement_lifecycle_feat import execute_use_item_request

    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="hp-reversal:delayed-product"):
            delayed = publish_store_product(
                class_id=shop["class_id"], entitlement_type="DELAYED_USE", name="Homework Pass",
                price="5.00", created_by_seat_id=shop["teacher"].seat_id,
            )
        db.session.commit()
        result = execute_store_purchase(
            canonical_context=shop["student"], policy_uuid=delayed.policy_uuid, quantity=1,
        )
        assert result.success is True, result.error_code
        db.session.commit()
        purchase = (
            Transaction.query
            .filter_by(class_id=shop["class_id"], seat_id=shop["seat_id"], type="purchase")
            .order_by(Transaction.id.desc())
            .first()
        )
        grant = EntitlementEvent.query.filter_by(
            correlation_id=purchase.correlation_id, event_type="GRANTED",
        ).one()
        execute_use_item_request(
            class_id=shop["class_id"], seat_id=shop["seat_id"],
            entitlement_id=grant.entitlement_id, action_payload={"kind": "redemption"},
            idempotency_key="hp-reversal:redeem",
        )
        db.session.commit()

        eligibility = resolve_purchase_resolution_eligibility(purchase)
        assert eligibility.eligible is False
        assert "still waiting" in eligibility.reason
