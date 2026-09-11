"""INV-LED-015: the seat row serializes a seat's money (#1364).

Debit FEATs locked the `seats` row; settlement locked the class row, pending
transactions and snapshots, and never `seats`. A `FOR UPDATE` only serializes
against transactions that take the same lock, so a debit and a settlement for
one seat did not serialize at all. Meanwhile `get_available_balance` was two
statements, posted then pending: a settlement committing between them moved a
pending debit out of the second term after the first was read, and the debit
was counted in neither.

Two traps shape these tests. A foreign key takes `FOR KEY SHARE` on the parent
`seats` row whenever a child row is inserted, and `FOR KEY SHARE` conflicts
with `FOR UPDATE`. So a settlement that has to insert a snapshot blocks on a
held seat lock with or without the fix. The blocking test therefore settles
once first, so the snapshot rows already exist and the only thing left that can
wait on the seat is the lock under test. The ordering tests assert on emitted
SQL, because the lock mode and its position relative to the balance read are
what the fix changes, and those are only visible in the statement stream.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment
from app.models import Transaction, TransactionStatus
from app.services.ledger_balance_query_service import (
    get_available_balance,
    get_available_balances,
    get_pending_balance_delta,
    get_posted_balance,
)
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction, settle_ledger_balances
from tests.test_insurance_purchase_feat import _setup as _setup_insurance_class
from tests.test_insurance_purchase_feat import _student_ctx
from tests.test_rent_lifecycle import _T_INITIAL, _setup_rent_class

pytestmark = [pytest.mark.regression]


def _fund(student, class_id, amount, key):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"inv-led-015:{key}:{student.seat.id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"inv-led-015-fund:{key}:{student.seat.id}",
            seat_id=student.seat.id,
            class_id=class_id,
            user_id=student.user.id,
            amount=Decimal(amount),
            account_type="checking",
            type="payroll",
            description="INV-LED-015 test funding",
        )
    db.session.commit()


def _settle(seat_id, class_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"inv-led-015:settle:{uuid4().hex}"):
        settle_ledger_balances(seat_id, class_id)


@contextmanager
def _recorded_statements():
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()))

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(db.engine, "before_cursor_execute", record)


def _first_index(statements, predicate):
    return next((i for i, s in enumerate(statements) if predicate(s)), None)


def _is_seat_lock(statement):
    return "FROM seats" in statement and "FOR UPDATE" in statement


def _is_balance_read(statement):
    return "ledger_balance_snapshot" in statement and "posted_balance_cents" in statement


def test_INV_LED_015__settlement_waits_for_a_debit_holding_the_seat_lock(app):
    """A settlement cannot proceed while another transaction holds the seat row."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        student = classroom.students[0]
        seat_id, class_id = student.seat.id, classroom.class_id

        _fund(student, class_id, "100.00", "posted")
        _settle(seat_id, class_id)
        _fund(student, class_id, "5.00", "pending")

        holder = db.engine.connect()
        holder_tx = holder.begin()
        try:
            holder.execute(
                text("SELECT id FROM seats WHERE id = :seat_id FOR UPDATE"),
                {"seat_id": seat_id},
            )
            with pytest.raises(OperationalError) as excinfo:
                with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"inv-led-015:blocked:{uuid4().hex}"):
                    db.session.execute(text("SET LOCAL lock_timeout = '500ms'"))
                    settle_ledger_balances(seat_id, class_id)
            assert "lock timeout" in str(excinfo.value).lower()
        finally:
            db.session.rollback()
            holder_tx.rollback()
            holder.close()

        _settle(seat_id, class_id)
        still_pending = Transaction.query.filter_by(
            seat_id=seat_id, class_id=class_id, status=TransactionStatus.PENDING
        ).count()
        assert still_pending == 0
        assert get_posted_balance(seat_id, class_id, "checking") == Decimal("105.00")


def test_INV_LED_015__settlement_locks_the_seat_before_the_class_row(app):
    """Lock order is seat, then class, so settlement cannot deadlock a debit."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        student = classroom.students[0]
        seat_id, class_id = student.seat.id, classroom.class_id
        _fund(student, class_id, "20.00", "order")

        with _recorded_statements() as statements:
            _settle(seat_id, class_id)

        seat_lock = _first_index(statements, _is_seat_lock)
        class_lock = _first_index(
            statements, lambda s: "FROM classes" in s and "FOR UPDATE" in s
        )
        assert seat_lock is not None, "settlement did not lock the seat row"
        assert class_lock is not None, "settlement did not lock the class row"
        assert seat_lock < class_lock


def test_INV_LED_015__rent_payment_locks_the_seat_before_reading_the_balance(app):
    """pay_rent's affordability check must run under the seat lock."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom)
        student = classroom.students[0]
        seat_id, class_id = student.seat.id, classroom.class_id
        execute_reconcile_rent(class_id, reference_time_utc=_T_INITIAL)
        _fund(student, class_id, "100.00", "rent")
        correlation_id = f"rent:{class_id}:{seat_id}:cycle:1"

        with _recorded_statements() as statements:
            result = execute_rent_payment(
                class_id, seat_id, correlation_id,
                idempotency_key=f"inv-led-015:rent:{correlation_id}",
            )
        assert result.success is True, result.error_message

        seat_lock = _first_index(statements, _is_seat_lock)
        balance_read = _first_index(statements, _is_balance_read)
        assert seat_lock is not None, "rent payment did not lock the seat row"
        assert balance_read is not None, "rent payment did not read the balance"
        assert seat_lock < balance_read


def test_INV_LED_015__insurance_purchase_locks_the_seat_before_reading_the_balance(app):
    """The first-premium affordability check must run under the seat lock."""
    classroom, policy_uuid = _setup_insurance_class(app)
    with app.app_context():
        with _recorded_statements() as statements:
            result = execute_purchase_insurance(
                canonical_context=_student_ctx(classroom),
                policy_uuid=policy_uuid,
                idempotency_key="inv-led-015:insurance",
            )
        assert result.success, result.error_message
        db.session.commit()

        seat_lock = _first_index(statements, _is_seat_lock)
        balance_read = _first_index(statements, _is_balance_read)
        assert seat_lock is not None, "insurance purchase did not lock the seat row"
        assert balance_read is not None, "insurance purchase did not read the balance"
        assert seat_lock < balance_read


def test_INV_LED_015__available_balance_is_read_in_one_statement(app):
    """Posted and pending must come from one snapshot, not two statements."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        student = classroom.students[0]
        seat_id, class_id = student.seat.id, classroom.class_id

        def assert_single_statement_and_consistent():
            with _recorded_statements() as single:
                checking = get_available_balance(seat_id, class_id, "checking")
            assert len(single) == 1, single
            with _recorded_statements() as pair:
                both = get_available_balances(seat_id, class_id)
            assert len(pair) == 1, pair
            expected = get_posted_balance(seat_id, class_id, "checking") + get_pending_balance_delta(
                seat_id, class_id, "checking"
            )
            assert checking == expected
            assert both[0] == expected
            return checking

        _fund(student, class_id, "40.00", "pending-only")
        assert assert_single_statement_and_consistent() == Decimal("40.00")

        db.session.commit()
        _settle(seat_id, class_id)
        _fund(student, class_id, "2.50", "snapshot-plus-pending")
        assert assert_single_statement_and_consistent() == Decimal("42.50")
