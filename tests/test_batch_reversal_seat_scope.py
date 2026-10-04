"""Whole-reversal batches serialize seats and preserve class isolation."""

import pytest

from app.extensions import db
from app.feats.transaction_void_feat import execute_void_transactions
from app.models import AuditEvent, Transaction
from app.services.ledger_provenance_query_service import get_exact_reversal
from tests.dom.interpretation.helpers import unused_store_purchase
from tests.helpers.classroom_initializer import initialize


def test_batch_reversal_two_seats_preserves_originals_and_cannot_double_recover(app):
    room = initialize("chemistry_p1", app)
    purchases = [unused_store_purchase(room, student, key=f"batch-reverse:{index}")
                 for index, student in enumerate(room.students[:2])]
    facts = [(tx.amount, tx.correlation_id, tx.lineage_token) for tx in purchases]
    results = execute_void_transactions(
        list(reversed(purchases)), correlation_id="batch-reverse:command",
        idempotency_key="batch-reverse:command", actor_seat_id=room.teacher_seat.id,
    )
    assert len(results) == 2
    for tx, original in zip(purchases, facts):
        db.session.refresh(tx)
        assert (tx.amount, tx.correlation_id, tx.lineage_token) == original
        assert tx.reversal_transaction_id is None
        child = get_exact_reversal(tx)
        assert child is not None
        assert child.original_transaction_id == tx.id
        assert child.correlation_id == tx.correlation_id
        assert child.amount == -tx.amount
    before = Transaction.query.count()
    with pytest.raises(ValueError):
        execute_void_transactions(
            purchases, correlation_id="batch-reverse:command",
            idempotency_key="batch-reverse:command", actor_seat_id=room.teacher_seat.id,
        )
    db.session.rollback()
    assert Transaction.query.count() == before
    assert Transaction.query.filter(Transaction.original_transaction_id.in_([tx.id for tx in purchases])).count() == 2


def test_batch_reversal_cross_class_denial_has_no_effects(app):
    rooms = [initialize("chemistry_p1", app), initialize("biology_block_a", app)]
    purchases = [unused_store_purchase(room, room.students[0], key=f"batch-scope:{index}")
                 for index, room in enumerate(rooms)]
    before = (Transaction.query.count(), AuditEvent.query.count())
    with pytest.raises(ValueError, match="within one class"):
        execute_void_transactions(
            purchases, correlation_id="batch-scope:command",
            idempotency_key="batch-scope:command", actor_seat_id=rooms[0].teacher_seat.id,
        )
    db.session.rollback()
    assert (Transaction.query.count(), AuditEvent.query.count()) == before
    for tx in purchases:
        assert get_exact_reversal(tx) is None
