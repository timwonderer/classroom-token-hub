"""Every write that can end a hall pass waits on the holder's seat lock.

A hall pass ends by use (a hall-pass log, FEAT-PROD-002 §III) or by a REVOKED or
EXPIRED event. Those live in different tables, so no index can stop an approval
and a reversal (or a removal, or a rent-perk expiry) from both ending the same
pass: a refund for a pass that was also used. Before 2026-10-09 the Store's
one-terminal-event index caught that, because use also wrote CONSUMED.

So every such writer takes ``lock_hall_pass_holder`` on the holder's seat row
before it reads whether the pass is spent. These tests hold that row from a
second connection (FOR NO KEY UPDATE, so foreign-key inserts are not blocked by
it) and give the writer a short lock timeout: a writer that takes the lock times
out; one that skipped it runs straight through and fails the test.
"""

from contextlib import contextmanager
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.transaction_void_feat import execute_void_transaction
from app.models import EntitlementEvent, Seat, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import (
    expire_rent_perks,
    grant_hall_passes,
    remove_hall_passes,
    revoke_entitlement,
)
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import record_ledger_fixture
from tests.helpers.store_products import publish_store_product


@pytest.fixture
def holder(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        student = classroom.students[0]
        teacher = db.session.get(Seat, classroom.teacher_seat_id)
        yield {
            "classroom": classroom,
            "class_id": classroom.class_id,
            "seat_id": student.seat_id,
            "student": CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                        seat_id=student.seat_id, actor_role="student"),
            "teacher": CanonicalContext(user_id=teacher.user_id, class_id=classroom.class_id,
                                        seat_id=teacher.id, actor_role="teacher"),
        }


@contextmanager
def seat_held_elsewhere(seat_id):
    """Hold the seat row FOR NO KEY UPDATE from a separate connection.

    Not FOR UPDATE: that also blocks every insert carrying a foreign key to the
    seat (an insert takes FOR KEY SHARE on the parent row), so any writer would
    wait whether or not it takes lock_hall_pass_holder, and the test would pass
    for the wrong reason. FOR NO KEY UPDATE conflicts with the FOR UPDATE that
    lock_hall_pass_holder takes, and not with a foreign-key insert.
    """
    other = db.engine.connect()
    tx = other.begin()
    try:
        other.execute(sa.text("SELECT id FROM seats WHERE id = :id FOR NO KEY UPDATE"), {"id": seat_id})
        yield
    finally:
        tx.rollback()
        other.close()


@contextmanager
def short_lock_timeouts():
    """Apply a short lock timeout to every transaction the session opens.

    A FEAT context starts its own transaction, so a one-off SET would not reach
    it. The statement timeout is a backstop: a writer that blocks on something
    else fails the test instead of hanging the run.
    """
    def _after_begin(session, transaction, connection):
        connection.exec_driver_sql("SET LOCAL lock_timeout = '300ms'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")

    target = db.session()
    sa.event.listen(target, "after_begin", _after_begin)
    try:
        db.session.rollback()  # the next statement opens a fresh, timed transaction
        yield
    finally:
        sa.event.remove(target, "after_begin", _after_begin)


def _assert_waits_on_the_seat(seat_id, write):
    with seat_held_elsewhere(seat_id):
        with short_lock_timeouts():
            with pytest.raises(OperationalError, match="lock timeout"):
                write()
            db.session.rollback()


def test_approval_waits_on_the_seat(app, holder):
    from app.feats.prod import record_hall_pass_log

    with app.app_context():
        seat = db.session.get(Seat, holder["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-approve-setup"):
            grant_hall_passes(seat, 1)
        db.session.commit()

        def write():
            record_hall_pass_log(
                ctx=holder["teacher"], requested_by_seat_id=holder["seat_id"],
                approved_by_seat_id=holder["teacher"].seat_id, destination="Bathroom",
                reason="teacher_approved", idempotency_key="ser-approve",
            )

        _assert_waits_on_the_seat(holder["seat_id"], write)


def test_reversal_waits_on_the_seat_before_deciding(app, holder, monkeypatch):
    """The lock comes before the eligibility read, not just somewhere in the reversal.

    The ledger posting also locks the seat, later. Without the up-front lock the
    reversal would decide "nothing used" unlocked and only then wait, which is
    the race. So reading eligibility while the seat is held elsewhere fails here.
    """
    from app.services import ledger_correction_service

    real_resolve = ledger_correction_service.resolve_purchase_resolution_eligibility
    held = {"now": False}

    def resolve_only_under_the_lock(transaction):
        if held["now"]:
            raise AssertionError("eligibility was read before the seat lock was taken")
        return real_resolve(transaction)

    monkeypatch.setattr(ledger_correction_service, "resolve_purchase_resolution_eligibility",
                        resolve_only_under_the_lock)
    with app.app_context():
        teacher = holder["teacher"]
        with FEATContext("FEAT-LED-001", idempotency_key="ser-reverse-seed"):
            record_ledger_fixture(seat_id=holder["seat_id"], class_id=holder["class_id"],
                                  amount=Decimal("50.00"))
        db.session.commit()
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="ser-reverse-product"):
            product = publish_store_product(
                class_id=holder["class_id"], entitlement_type="HALL_PASS", name="Hall Pass",
                price="5.00", created_by_seat_id=teacher.seat_id,
            )
        db.session.commit()
        assert execute_store_purchase(
            canonical_context=holder["student"], policy_uuid=product.policy_uuid, quantity=2,
        ).success
        db.session.commit()
        purchase = (
            Transaction.query.filter_by(class_id=holder["class_id"], seat_id=holder["seat_id"],
                                        type="purchase")
            .order_by(Transaction.id.desc()).first()
        )

        def write():
            held["now"] = True
            try:
                execute_void_transaction(
                    purchase, correlation_id=purchase.correlation_id,
                    idempotency_key=f"ser-reverse:{purchase.id}",
                )
            finally:
                held["now"] = False

        _assert_waits_on_the_seat(holder["seat_id"], write)


def test_removal_waits_on_the_seat(app, holder):
    with app.app_context():
        seat = db.session.get(Seat, holder["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-remove-setup"):
            grant_hall_passes(seat, 2)
        db.session.commit()

        def write():
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-remove"):
                remove_hall_passes(db.session.get(Seat, holder["seat_id"]), 1)

        _assert_waits_on_the_seat(holder["seat_id"], write)


def test_rent_perk_expiry_waits_on_the_seat(app, holder):
    with app.app_context():
        seat = db.session.get(Seat, holder["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-expire-setup"):
            grant_hall_passes(seat, 2, acquisition_type="PERK", correlation_id="ser-rent-cycle")
        db.session.commit()

        def write():
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-expire"):
                expire_rent_perks(correlation_id="ser-rent-cycle", class_id=holder["class_id"],
                                  actor_seat_id=holder["teacher"].seat_id)

        _assert_waits_on_the_seat(holder["seat_id"], write)


def test_revoking_a_hall_pass_waits_on_the_seat(app, holder):
    with app.app_context():
        seat = db.session.get(Seat, holder["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-revoke-setup"):
            grant_hall_passes(seat, 1)
        db.session.commit()
        grant = EntitlementEvent.query.filter_by(
            target_seat_id=holder["seat_id"], event_type="GRANTED",
        ).one()

        def write():
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="ser-revoke"):
                revoke_entitlement(
                    entitlement_id=grant.entitlement_id, class_id=grant.class_id,
                    target_seat_id=grant.target_seat_id, actor_seat_id=holder["teacher"].seat_id,
                    product_id=grant.product_id, entitlement_type="HALL_PASS",
                    acquisition_type=grant.acquisition_type, correlation_id="ser-revoke",
                )

        _assert_waits_on_the_seat(holder["seat_id"], write)
