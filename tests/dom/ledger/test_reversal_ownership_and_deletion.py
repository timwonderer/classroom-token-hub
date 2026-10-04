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
from tests.helpers.ledger import compensate_ledger_posted_transaction as reverse_transaction
from app.services.ledger_settlement_service import settle_balances
from app.services.ledger_provenance_query_service import get_exact_reversal, exact_reversal_query
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
            amount=Decimal("40.00"),
            account_type="checking",
            type="payroll",
            description="Seed funding",
            actor_seat_id=classroom.teacher_seat_id,
        )
        settle_balances(tx.seat_id, tx.class_id)
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
    original_values = {column.key: getattr(original, column.key) for column in Transaction.__table__.columns}

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
    assert original.reversal_transaction_id is None
    assert get_exact_reversal(original).id == reversal.id
    assert {column.key: getattr(original, column.key) for column in Transaction.__table__.columns} == original_values

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

    # Precondition: an immutable reversal names its original. Without this the test
    # could pass against a student who was never refunded.
    db.session.expire_all()
    assert db.session.get(Transaction, original_id).reversal_transaction_id is None
    assert get_exact_reversal(db.session.get(Transaction, original_id)).id == reversal_id
    assert db.session.get(Transaction, reversal_id).original_transaction_id == original_id

    # The live removal path the roster deletion FEAT composes.
    with FEATContext("FEAT-IDEN-007", idempotency_key="rev-del:delete"):
        removed = remove_student_from_teacher_scope(seat_id, classroom.teacher_user_id)
    db.session.commit()
    db.session.expire_all()

    assert removed is True
    # Deletion physically destroys the Seat (FEAT-IDEN-006); it is not an
    # implicit unclaim, and the principal left with no seat goes with it.
    assert db.session.get(Seat, seat_id) is None
    assert db.session.get(User, user_id) is None
    assert db.session.get(Transaction, original_id) is None, (
        "The original must not outlive the seat that owned it."
    )
    assert db.session.get(Transaction, reversal_id) is None, (
        "The reversal shares the original's owner, so it must go in the same "
        "cascade — leaving it behind would strand a financial fact whose "
        "counterparty no longer exists."
    )


def test_reversal_inherits_the_original_correlation_under_a_ledger_feat(app, client):
    """FEAT-LED-002 §II.2 / SPEC-OPS-001 §3.1A: the compensating row keeps the
    original's economic correlation, not the active FEAT's.

    Left unset, it took the active correlation, so a scheduled collective-goal
    refund named an unrelated operation. Setting it under a Tier-1 Ledger FEAT
    also has to pass the insert-time correlation check, which used to accept a
    compensating row in one place and reject it in the other.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0]
    original = _funded_transaction(classroom, student, key="rev-corr:seed")

    with FEATContext("FEAT-LED-002", idempotency_key="rev-corr:reverse"):
        reversal = reverse_transaction(
            original,
            description="Refund",
            idempotency_key="rev-corr:reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    db.session.commit()

    assert reversal.correlation_id == original.correlation_id


def test_a_reversal_cannot_itself_be_reversed(app, client):
    """SPEC-OPS-001 §3.6: a reversal is terminal. The original carries the link;
    the compensating row carries none, so its type is what must refuse."""
    from app.services.ledger_correction_service import ReversalNotAuthorized

    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0]
    original = _funded_transaction(classroom, student, key="rev-terminal:seed")
    with FEATContext("FEAT-LED-002", idempotency_key="rev-terminal:reverse"):
        reversal = reverse_transaction(
            original,
            description="Refund",
            idempotency_key="rev-terminal:reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    db.session.commit()

    with FEATContext("FEAT-LED-002", idempotency_key="rev-terminal:again"):
        with pytest.raises(ReversalNotAuthorized):
            reverse_transaction(
                reversal,
                description="Refund the refund",
                idempotency_key="rev-terminal:again",
                actor_seat_id=classroom.teacher_seat_id,
            )
    db.session.rollback()
    assert Transaction.query.filter_by(original_transaction_id=reversal.id).count() == 0



def _purchase_debit(classroom, *, key):
    student = classroom.students[0]
    with FEATContext("FEAT-LED-001", idempotency_key=key):
        original, _ = create_ledger_idempotent_transaction(
            idempotency_key=key, seat_id=student.seat.id,
            target_seat_id=student.seat.id, class_id=classroom.class_id,
            amount=Decimal("-5.00"), account_type="checking", type="purchase",
            description="Purchase", actor_seat_id=classroom.teacher_seat_id,
        )
    return original


def test_debit_reversal_derives_link_replays_and_scopes_immutable_children(app):
    from app.services.ledger_correction_service import TransactionAlreadyReversed

    classroom = provision_ledger_classroom("chemistry_p1", app)
    original = _purchase_debit(classroom, key="derived-debit")
    original_values = {column.key: getattr(original, column.key) for column in Transaction.__table__.columns}
    with FEATContext("FEAT-LED-002", idempotency_key="derived-reverse"):
        reversal = reverse_transaction(
            original, description="Refund", idempotency_key="derived-reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    reversal_id = reversal.id
    with FEATContext("FEAT-LED-002", idempotency_key="derived-reverse"):
        replay = reverse_transaction(
            original, description="Refund", idempotency_key="derived-reverse",
            actor_seat_id=classroom.teacher_seat_id,
        )
    assert replay.id == reversal_id
    assert get_exact_reversal(original).id == reversal_id
    assert reversal.original_transaction_id == original.id
    assert reversal.correlation_id == original.correlation_id
    assert reversal.amount_cents == -original.amount_cents
    assert {column.key: getattr(original, column.key) for column in Transaction.__table__.columns} == original_values
    scope = dict(class_id=original.class_id, seat_id=original.seat_id,
                 account_type=original.account_type, original_transaction_id=original.id,
                 correlation_id=original.correlation_id)
    for changed in ({"class_id": "other-class"},
                    {"seat_id": classroom.students[1].seat.id},
                    {"account_type": "savings"},
                    {"original_transaction_id": reversal.id},
                    {"correlation_id": "unrelated-operation"}):
        assert exact_reversal_query(**dict(scope, **changed)).count() == 0
    with pytest.raises(TransactionAlreadyReversed):
        with FEATContext("FEAT-LED-002", idempotency_key="another-reverse"):
            reverse_transaction(
                original, description="Again", idempotency_key="another-reverse",
                actor_seat_id=classroom.teacher_seat_id,
            )
    assert Transaction.query.filter_by(type="REVERSAL", original_transaction_id=original.id).count() == 1


def test_concurrent_debit_reversals_serialize_without_changing_original(app, monkeypatch):
    from app.services import ledger_recovery_service
    from app.services.ledger_correction_service import TransactionAlreadyReversed
    from tests.dom.prod.test_attendance_correction_concurrency import _ordered_race

    classroom = provision_ledger_classroom("chemistry_p1", app)
    original = _purchase_debit(classroom, key="concurrent-derived-debit")
    original_id = original.id
    actor_id = classroom.teacher_seat_id
    original_values = {column.key: getattr(original, column.key) for column in Transaction.__table__.columns}

    def action(key):
        def run():
            try:
                with FEATContext("FEAT-LED-002", idempotency_key=key):
                    source = db.session.get(Transaction, original_id)
                    row = reverse_transaction(
                        source, description="Refund", idempotency_key=key,
                        actor_seat_id=actor_id,
                    )
                    result_id = row.id
                return result_id
            except TransactionAlreadyReversed as error:
                raise ValueError("ALREADY_REVERSED") from error
        return run

    outcomes = _ordered_race(
        app, monkeypatch, action("first-debit-reverse"), action("second-debit-reverse"),
        [(ledger_recovery_service, "lock_recovery_scope")],
    )
    assert outcomes[0][0] == "accepted"
    assert outcomes[1] == ("denied", "ALREADY_REVERSED")
    source = db.session.get(Transaction, original_id)
    assert {column.key: getattr(source, column.key) for column in Transaction.__table__.columns} == original_values
    assert get_exact_reversal(source).id == outcomes[0][1]
    assert Transaction.query.filter_by(type="REVERSAL", original_transaction_id=original_id).count() == 1



def test_reversal_link_distinguishes_originals_sharing_one_correlation(app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0]
    originals = []
    for index in range(2):
        with FEATContext("FEAT-LED-001", correlation_id="corr_shared-economic-operation",
                         idempotency_key=f"shared-source-{index}"):
            original, _ = create_ledger_idempotent_transaction(
                idempotency_key=f"shared-source-{index}", seat_id=student.seat.id,
                target_seat_id=student.seat.id, class_id=classroom.class_id,
                amount=Decimal("-5.00"), account_type="checking", type="purchase",
                description="Purchase", actor_seat_id=classroom.teacher_seat_id,
            )
            originals.append(original)
    with FEATContext("FEAT-LED-002", idempotency_key="shared-first-reversal"):
        first = reverse_transaction(
            originals[0], description="First refund", idempotency_key="shared-first-reversal",
            actor_seat_id=classroom.teacher_seat_id,
        )
    assert get_exact_reversal(originals[0]).id == first.id
    assert get_exact_reversal(originals[1]) is None
    with FEATContext("FEAT-LED-002", idempotency_key="shared-second-reversal"):
        second = reverse_transaction(
            originals[1], description="Second refund", idempotency_key="shared-second-reversal",
            actor_seat_id=classroom.teacher_seat_id,
        )
    assert first.correlation_id == second.correlation_id == "corr_shared-economic-operation"
    assert get_exact_reversal(originals[1]).id == second.id
    assert first.original_transaction_id != second.original_transaction_id
    assert all(original.reversal_transaction_id is None for original in originals)



def test_positive_credit_reversal_preserves_subtype_and_denies_changed_retry(app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    original = _funded_transaction(classroom, classroom.students[0], key="positive-subtype-source")
    original_values = {column.key: getattr(original, column.key) for column in Transaction.__table__.columns}
    with FEATContext("FEAT-LED-002", idempotency_key="positive-subtype-reversal"):
        reversal = reverse_transaction(
            original, description="Issue refund", compensation_type="issue_refund",
            idempotency_key="positive-subtype-reversal", actor_seat_id=classroom.teacher_seat_id,
        )
    assert reversal.compensation_subtype == "issue_refund"
    assert reversal.command_reservation.fingerprint_version == 5
    with FEATContext("FEAT-LED-002", idempotency_key="positive-subtype-reversal"):
        replay = reverse_transaction(
            original, description="Issue refund", compensation_type="issue_refund",
            idempotency_key="positive-subtype-reversal", actor_seat_id=classroom.teacher_seat_id,
        )
    assert replay.id == reversal.id
    with pytest.raises(ValueError, match="compensation subtype"):
        with FEATContext("FEAT-LED-002", idempotency_key="positive-subtype-reversal"):
            reverse_transaction(
                original, description="Issue reversal", compensation_type="issue_reversal",
                idempotency_key="positive-subtype-reversal", actor_seat_id=classroom.teacher_seat_id,
            )
    assert {column.key: getattr(original, column.key) for column in Transaction.__table__.columns} == original_values



@pytest.mark.parametrize("source_kind", ["credit", "debit"])
def test_reversal_replay_denies_changed_actor_without_repricing(app, source_kind):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    original = (_funded_transaction(classroom, classroom.students[0], key="actor-replay-source")
                if source_kind == "credit" else _purchase_debit(classroom, key="actor-replay-source"))
    with FEATContext("FEAT-LED-002", idempotency_key="actor-replay-reversal"):
        accepted = reverse_transaction(
            original, description="Refund", idempotency_key="actor-replay-reversal",
            actor_seat_id=classroom.teacher_seat_id,
        )
    with pytest.raises(ValueError, match="fingerprint"):
        with FEATContext("FEAT-LED-002", idempotency_key="actor-replay-reversal"):
            reverse_transaction(
                original, description="Refund", idempotency_key="actor-replay-reversal",
                actor_seat_id=classroom.students[0].seat.id,
            )
    assert get_exact_reversal(original).id == accepted.id
    assert original.reversal_transaction_id is None
