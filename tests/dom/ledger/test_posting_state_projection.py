"""Batch posting-state projection (DOM-LED-001 §VIII, INV-LED-008).

PENDING/POSTED is derived by comparing an effect's immutable
``posting_sequence`` with the reconciliation cursor of its exact
``(class_id, seat_id, account_type)`` scope. The ``Transaction.posting_state``
instance getter reads that cursor with one query per access, so a transaction
loop issued one query per row. ``project_posting_states`` resolves every
cursor a list needs in one pure read. These tests hold it to the hybrid SQL
expression, to scope isolation, and to a query count that does not grow with
the number of rows.
"""

from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import event

from app import db
from app.feats.base import FEATContext
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus
from app.services.ledger.builders import build_transaction_list_view
from app.services.ledger_balance_query_service import (
    classify_posting_state,
    project_posting_states,
    resolve_reconciliation_cursors,
)
from app.services.ledger_interest_service import _savings_ledger
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.ledger import provision_ledger_classroom, record_ledger_fixture


@contextmanager
def _snapshot_queries():
    """Collect every SQL statement that reads the snapshot table."""
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _executemany):
        if "ledger_balance_snapshot" in statement:
            statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)


def _record(seat, key, *, amount="5.00", account_type="checking", posted=False):
    with FEATContext("FEAT-LED-001", idempotency_key=key):
        tx = record_ledger_fixture(
            seat_id=seat.id, class_id=seat.class_id, amount=Decimal(amount),
            account_type=account_type, posted=posted, description=key,
        )
    db.session.commit()
    return tx


def _settle(seat, key):
    with FEATContext("FEAT-LED-003", idempotency_key=key):
        settle_balances(seat.id, seat.class_id)
    db.session.commit()


def _sql_states(transactions):
    """The hybrid SQL expression's answer, one row per transaction id."""
    ids = [tx.id for tx in transactions]
    return {
        tx_id: TransactionStatus(value)
        for tx_id, value in db.session.query(Transaction.id, Transaction.posting_state)
        .filter(Transaction.id.in_(ids)).all()
    }


@pytest.fixture
def mixed_ledger(app):
    """Posted and pending effects across two classes, two seats and both accounts.

    The same student holds a seat in each class, so a projection keyed by user
    or seat alone, rather than by the exact account scope, would mis-classify.
    """
    chem = provision_ledger_classroom("chemistry_p1", app)
    csp = provision_ledger_classroom("ap_csp_p3", app)
    chem_a, chem_b = chem.students[0].seat, chem.students[1].seat
    csp_a = csp.students[0].seat

    rows = [
        _record(chem_a, "proj:chem-a:chk:1"),
        _record(chem_a, "proj:chem-a:sav:1", account_type="savings"),
        _record(chem_b, "proj:chem-b:chk:1"),
        _record(csp_a, "proj:csp-a:chk:1"),
        _record(csp_a, "proj:csp-a:sav:1", account_type="savings"),
    ]
    _settle(chem_a, "proj:settle:chem-a")
    _settle(csp_a, "proj:settle:csp-a")
    # Recorded after settlement: above their cursors, so pending.
    rows += [
        _record(chem_a, "proj:chem-a:sav:2", account_type="savings"),
        _record(csp_a, "proj:csp-a:chk:2"),
        _record(chem_b, "proj:chem-b:sav:1", account_type="savings"),
    ]
    return rows


def test_projection_agrees_with_hybrid_sql_expression(client, app, mixed_ledger):
    projected = dict(zip((tx.id for tx in mixed_ledger), project_posting_states(mixed_ledger)))

    assert projected == _sql_states(mixed_ledger)
    assert projected == {tx.id: tx.posting_state for tx in mixed_ledger}
    # The fixture really is mixed, so agreement is not agreement on one value.
    assert set(projected.values()) == {TransactionStatus.POSTED, TransactionStatus.PENDING}


def test_projection_isolates_class_seat_and_account(client, app, mixed_ledger):
    states = dict(zip((tx.id for tx in mixed_ledger), project_posting_states(mixed_ledger)))
    by_key = {tx.description: states[tx.id] for tx in mixed_ledger}

    # Settled scopes: posted.
    assert by_key["proj:chem-a:chk:1"] is TransactionStatus.POSTED
    assert by_key["proj:csp-a:sav:1"] is TransactionStatus.POSTED
    # Same seat, other account, recorded after its cursor: pending.
    assert by_key["proj:chem-a:sav:2"] is TransactionStatus.PENDING
    # Same student's seat in another class, recorded after that cursor: pending.
    assert by_key["proj:csp-a:chk:2"] is TransactionStatus.PENDING
    # Another seat in a settled class, never settled itself: pending.
    assert by_key["proj:chem-b:chk:1"] is TransactionStatus.PENDING


def test_cursor_queries_do_not_grow_with_row_count(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_a, seat_b = classroom.students[0].seat, classroom.students[1].seat
    few = [_record(seat_a, "proj:count:a:0"), _record(seat_b, "proj:count:b:0", account_type="savings")]
    _settle(seat_a, "proj:count:settle")
    many = few + [_record(seat_a, f"proj:count:a:{i}") for i in range(1, 9)] + [
        _record(seat_b, f"proj:count:b:{i}", account_type="savings") for i in range(1, 9)
    ]
    db.session.expire_all()

    with _snapshot_queries() as small:
        project_posting_states(few)
    with _snapshot_queries() as large:
        states = project_posting_states(many)

    assert len(small) == len(large) == 1
    assert states == [_sql_states(many)[tx.id] for tx in many]


def test_builder_issues_one_cursor_query_for_a_list(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    rows = [_record(seat, f"proj:builder:{i}", posted=(i == 0)) for i in range(6)]
    db.session.expire_all()
    rows = Transaction.query.filter(Transaction.id.in_([tx.id for tx in rows])).all()

    with _snapshot_queries() as statements:
        views = build_transaction_list_view(rows, seat.class_id)

    assert len(statements) == 1
    expected = _sql_states(rows)
    assert [view.status for view in views] == [expected[tx.id].value for tx in rows]


def test_savings_ledger_resolves_its_cursor_once(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    for i in range(6):
        _record(seat, f"proj:interest:{i}", account_type="savings", posted=(i < 3))
    db.session.expire_all()

    with _snapshot_queries() as statements:
        ledger = _savings_ledger(seat.id, seat.class_id, "monthly")

    assert len(statements) == 1
    posted = Transaction.query.filter(
        Transaction.seat_id == seat.id, Transaction.class_id == seat.class_id,
        Transaction.account_type == "savings",
        Transaction.posting_state == TransactionStatus.POSTED,
    ).count()
    # Only posted ordinary savings effects enter the daily balance history.
    assert posted == 3
    assert len(ledger.history) == posted


@pytest.mark.parametrize(
    "sequence, cursor, expected",
    [
        (None, None, TransactionStatus.PENDING),   # no posting sequence
        (None, 10, TransactionStatus.PENDING),     # no posting sequence, cursor present
        (5, None, TransactionStatus.PENDING),      # missing snapshot / NULL cursor
        (5, 5, TransactionStatus.POSTED),          # at the cursor
        (4, 5, TransactionStatus.POSTED),          # below the cursor
        (6, 5, TransactionStatus.PENDING),         # above the cursor
    ],
)
def test_classify_posting_state_boundaries(sequence, cursor, expected):
    assert classify_posting_state(sequence, cursor) is expected


def test_missing_snapshot_and_null_cursor_resolve_to_none(client, app):
    """An unreconciled scope has no cursor, whether or not a snapshot row exists."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    tx = _record(seat, "proj:null-cursor")
    scope = (str(seat.class_id), int(seat.id), "checking")

    assert resolve_reconciliation_cursors([scope, None]) == {scope: None}
    assert project_posting_states([tx]) == [TransactionStatus.PENDING]
    assert _sql_states([tx]) == {tx.id: TransactionStatus.PENDING}


def test_projection_is_a_pure_read_without_autoflush(client, app, mixed_ledger):
    """Projection neither flushes pending session state nor writes anything."""
    first = mixed_ledger[0]
    scope = dict(class_id=first.class_id, seat_id=first.seat_id, account_type="checking")
    snapshot = LedgerBalanceSnapshot.query.filter_by(**scope).one()
    cursor_before = snapshot.reconciled_through_posting_sequence
    expected = project_posting_states(mixed_ledger)

    session = db.session()
    flushes = []

    def record_flush(*_args):
        flushes.append(True)

    event.listen(session, "before_flush", record_flush)
    try:
        # An unflushed change the projection must neither flush nor observe.
        snapshot.reconciled_through_posting_sequence = 0
        states = project_posting_states(mixed_ledger)
        assert flushes == []
        assert snapshot in session.dirty
        assert states == expected
    finally:
        event.remove(session, "before_flush", record_flush)
        db.session.rollback()

    db.session.expire_all()
    assert LedgerBalanceSnapshot.query.filter_by(**scope).one().reconciled_through_posting_sequence == cursor_before
