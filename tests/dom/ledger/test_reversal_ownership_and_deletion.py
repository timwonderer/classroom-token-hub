"""A reversal pair shares one economic owner, and dies with that owner.

This pins the property that makes ledger immutability (DOM-LED-001 §VII,
INV-LED-002) compatible with lawful seat destruction (§VII.2).

`original_transaction_id` / `reversal_transaction_id` are *not* FK-enforced, so
nothing in the schema stops a link from spanning two seats. What stops it is the
policy layer: every writer binds both ends to a single `seat_id`. That matters
because it is the only reason deletion is safe. If a reversal could name a
transaction owned by a different seat, deleting that seat would leave a surviving
row pointing at a deleted one, and "cleaning up" the pointer would be an in-place
rewrite of surviving financial history — exactly the mutation §VII.2 forbids and
the `ledger_transaction_no_rewrite` trigger rejects.

`app/utils/student_deletion.py` used to perform that rewrite. It was never
reachable (the illegal state it defended against cannot occur) and, once the
trigger landed, it would have aborted every deletion of a student who had ever
been refunded. The second test here is the regression that would have caught it.
"""

from decimal import Decimal

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus, Seat, User
from app.services.ledger_correction_service import reverse_transaction
from app.utils.student_deletion import remove_student_from_teacher_scope
from tests.helpers.ledger import (
    create_ledger_idempotent_transaction,
    provision_ledger_classroom,
)


def _funded_transaction(classroom, student, *, key):
    """Post one settled charge the student owns outright."""
    with FEATContext("FEAT-LED-001", idempotency_key=key):
        tx, _ = create_ledger_idempotent_transaction(
            idempotency_key=key,
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            user_id=student.user.id,
            amount=Decimal("40.00"),
            account_type="checking",
            type="payroll",
            description="Seed funding",
            actor_seat_id=classroom.teacher_seat_id,
        )
        tx.status = TransactionStatus.POSTED
        db.session.flush()
    db.session.commit()
    return tx


def test_reversal_pair_shares_one_economic_owner(app, client):
    """INV-LED-013 / §VII.2: the reversal inherits the original's seat and class.

    Only `actor_seat_id` — provenance, not ownership — may name a different seat.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0]
    original = _funded_transaction(classroom, student, key="rev-own:seed")
    original_id = original.id

    with FEATContext("FEAT-LED-002", idempotency_key="rev-own:reverse"):
        reversal = reverse_transaction(
            original,
            description="Refund",
            idempotency_key="rev-own:reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    db.session.commit()
    db.session.expire_all()

    original = db.session.get(Transaction, original_id)
    reversal = db.session.get(Transaction, reversal.id)

    assert reversal.seat_id == original.seat_id, (
        "A reversal must be owned by the same seat as the transaction it "
        "counteracts; a cross-seat link would make lawful seat deletion "
        "produce a dangling reference to a deleted financial fact."
    )
    assert reversal.class_id == original.class_id
    assert reversal.target_seat_id == original.target_seat_id
    assert reversal.original_transaction_id == original.id
    assert original.reversal_transaction_id == reversal.id

    # The one column that is allowed to differ, and why it is allowed to:
    # it records who acted, not who owns the money.
    assert reversal.actor_seat_id == classroom.teacher_seat_id
    assert reversal.actor_seat_id != reversal.seat_id


def test_deleting_a_refunded_student_removes_both_ends_of_the_pair(app, client):
    """§VII.2: destruction takes the whole pair; it never rewrites a survivor.

    Regression: the deletion path nulled `original_transaction_id` /
    `reversal_transaction_id` on rows referencing the doomed transactions. Against
    the immutability trigger that raises, so a student who had ever been refunded
    could not be deleted at all.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    user_id = student.user.id

    original = _funded_transaction(classroom, student, key="rev-del:seed")
    original_id = original.id

    with FEATContext("FEAT-LED-002", idempotency_key="rev-del:reverse"):
        reversal = reverse_transaction(
            original,
            description="Refund",
            idempotency_key="rev-del:reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    db.session.commit()
    reversal_id = reversal.id

    # Precondition: a live link exists in both directions. Without this the test
    # could pass against a student who was never refunded.
    db.session.expire_all()
    assert db.session.get(Transaction, original_id).reversal_transaction_id == reversal_id
    assert db.session.get(Transaction, reversal_id).original_transaction_id == original_id

    # The live removal path (`app/feats/identity_feat.py:48` imports this).
    with FEATContext("FEAT-IDEN-007", idempotency_key="rev-del:delete"):
        removed = remove_student_from_teacher_scope(seat_id, classroom.teacher_user_id)
    db.session.commit()
    db.session.expire_all()

    assert removed is True
    # The seat row survives as an unclaimed roster slot owned by the class; the
    # principal behind it does not.
    assert db.session.get(Seat, seat_id).user_id is None
    assert db.session.get(User, user_id) is None
    assert db.session.get(Transaction, original_id) is None, (
        "The original must not outlive the seat that owned it."
    )
    assert db.session.get(Transaction, reversal_id) is None, (
        "The reversal shares the original's owner, so it must go in the same "
        "cascade — leaving it behind would strand a financial fact whose "
        "counterparty no longer exists."
    )
