"""J-1: the transfer sufficiency check belongs under the seat row lock.

`/student/transfer` reads the balance, checks it, and then writes. Its
idempotency key is a fresh uuid4 per request, so the
UNIQUE(class_id, feat_code, idempotency_key) reservation cannot collapse a
double submit, and the single-use `transfer_token` lives in the session cookie,
which two concurrent requests each pop from their own deserialized copy. The
only thing that actually serializes them is the row lock the FEAT now takes.

A real two-connection race is not what these assert. They assert the property
that makes the race harmless: the authoritative sufficiency verdict is issued
inside `execute_account_transfer`, after the lock, so a route-level check that
has gone stale cannot let an over-balance transfer through.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import event

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.transfer_feat import InsufficientFunds, execute_account_transfer
from app.models import Transaction
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _fund(student, class_id, amount):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{student.seat.id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund-seat:{student.seat.id}",
            seat_id=student.seat.id,
            class_id=class_id,
            user_id=student.user.id,
            amount=amount,
            account_type="checking",
            type="payroll",
            description="Test funding",
        )
    db.session.commit()


def test_J1__feat_rejects_over_balance_transfer_even_when_route_check_is_bypassed(client, app):
    """Calling the FEAT directly — as a stale route check effectively does — is refused."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with app.app_context():
        seat_id = student.seat.id
        _fund(student, class_id, Decimal("10.00"))
        legs_before = Transaction.query.filter_by(class_id=class_id, seat_id=seat_id).count()

        with pytest.raises(InsufficientFunds):
            with FEATContext("FEAT-LED-000", idempotency_key=f"j1:over:{seat_id}"):
                execute_account_transfer(
                    seat_id=seat_id,
                    class_id=class_id,
                    user_id=student.user.id,
                    amount=Decimal("25.00"),
                    from_account="checking",
                    to_account="savings",
                )
        db.session.rollback()

        assert Transaction.query.filter_by(class_id=class_id, seat_id=seat_id).count() == legs_before


def test_J1__transfer_takes_an_exclusive_lock_on_the_seat_row(client, app):
    """The seat SELECT carries FOR UPDATE.

    Asserted against the emitted SQL rather than by racing two connections. A
    live race is not decisive here: the ledger insert takes a FOR KEY SHARE lock
    on the parent `seats` row through the foreign key no matter what, so
    "something locks the row" is true with or without the fix. FOR KEY SHARE
    does not block another FOR KEY SHARE — which is precisely why the FK lock
    fails to serialize two transfers and an explicit exclusive lock is needed.
    Only the lock mode distinguishes the two cases, and the statement text is
    where the mode is visible.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with app.app_context():
        seat_id = student.seat.id
        _fund(student, class_id, Decimal("50.00"))

        statements: list[str] = []

        def record(_conn, _cursor, statement, *_args):
            statements.append(" ".join(statement.split()))

        event.listen(db.engine, "before_cursor_execute", record)
        try:
            with FEATContext("FEAT-LED-000", idempotency_key=f"j1:lock:{seat_id}"):
                execute_account_transfer(
                    seat_id=seat_id,
                    class_id=class_id,
                    user_id=student.user.id,
                    amount=Decimal("5.00"),
                    from_account="checking",
                    to_account="savings",
                )
        finally:
            event.remove(db.engine, "before_cursor_execute", record)
            db.session.rollback()

        assert any(
            "FROM seats" in s and "FOR UPDATE" in s for s in statements
        ), "transfer did not lock the seat row; see J-1"
