"""Bounded batch creation proof (DOM-OPS-002 §6.2C; issue #1479).

``verified_creation_evidence`` verifies the complete class chain for every row,
so a batch of N rows cost O(N × chain length) HMAC computations.
``verified_creation_evidences`` walks the chain once per invocation, inside an
explicit budget and between two independent scalar head reads, then applies
every row-specific §6.2 check. These tests hold it to exact parity with the
single-row proof, to a work count that does not grow with rows, and to
fail-closed behaviour for every unavailable or contradictory chain.
"""
from collections import namedtuple
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ChainHead, Transaction
from app.services.audit_service import system_audit_authority
from app.services.ledger_posting_service import create_pending_transaction
from app.utils import audit_verifier as verifier
from tests.helpers.ledger import provision_ledger_classroom


Head = namedtuple("Head", "latest_sequence event_count latest_hash")


@pytest.fixture
def ledger_rows(app):
    """Real v3 Ledger effects with complete creation lineage in one class chain."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    rows = []
    for index in range(4):
        with FEATContext("FEAT-LED-001", idempotency_key=f"batch-proof:{index}"):
            rows.append(create_pending_transaction(
                seat_id=seat.id, class_id=classroom.class_id, target_seat_id=seat.id,
                actor_seat_id=seat.id, mechanism="self", amount=Decimal(index + 1),
                account_type="checking", type="Deposit", description=f"Batch proof {index}",
            ))
        db.session.commit()
    return classroom.class_id, rows


def _items(rows):
    return [("ledger_transaction", row) for row in rows]


def _chain_length(class_id):
    return verifier._historical_head_snapshot(f"class:{class_id}").latest_sequence


@contextmanager
def _work_counter(monkeypatch):
    """Count HMAC recomputations and audit-event queries."""
    counts = {"hmac": 0, "event_queries": 0}
    compute = verifier._compute_event_hash

    def counting_hash(*args, **kwargs):
        counts["hmac"] += 1
        return compute(*args, **kwargs)

    def on_query(_conn, _cursor, statement, *_args):
        if "FROM audit_events" in statement:
            counts["event_queries"] += 1

    monkeypatch.setattr(verifier, "_compute_event_hash", counting_hash)
    sa_event.listen(db.engine, "before_cursor_execute", on_query)
    try:
        yield counts
    finally:
        sa_event.remove(db.engine, "before_cursor_execute", on_query)
        monkeypatch.setattr(verifier, "_compute_event_hash", compute)


def _copy(row, **changes):
    values = {column.key: getattr(row, column.key) for column in Transaction.__table__.columns}
    values.update(changes)
    return SimpleNamespace(**values)


# ---------------------------------------------------------------------------
# Parity with the single-row proof
# ---------------------------------------------------------------------------

def test_batch_matches_single_row_proof_for_valid_rows(client, app, ledger_rows):
    class_id, rows = ledger_rows
    batch = verifier.verified_creation_evidences(_items(rows), class_id)

    assert batch.chain_status == "COMPLETE" and batch.reason is None
    assert batch.evidence == tuple(
        verifier.verified_creation_evidence("ledger_transaction", row, class_id) for row in rows
    )
    assert all(isinstance(proof, verifier.VerifiedCreationEvidence) for proof in batch.evidence)


@pytest.mark.parametrize("mutation", [
    "payload", "token", "version", "pointer", "missing_pointer", "table", "row_pk", "required_field",
])
def test_row_specific_failures_match_single_row_proof(client, app, ledger_rows, mutation):
    """Each row keeps its own scope, INSERT linkage, token/version, coverage and payload checks."""
    class_id, rows = ledger_rows
    good, other = rows[0], rows[1]
    table, required = "ledger_transaction", ()
    bad = {
        "payload": lambda: _copy(good, amount_cents=good.amount_cents + 1),
        "token": lambda: _copy(good, lineage_token="0" * 64),
        "version": lambda: _copy(good, lineage_version=2),
        "pointer": lambda: _copy(good, lineage_event_id=other.lineage_event_id),
        "missing_pointer": lambda: _copy(good, lineage_event_id=None),
        "table": lambda: good,
        "row_pk": lambda: _copy(good, id=other.id),
        "required_field": lambda: good,
    }[mutation]()
    if mutation == "table":
        table = "payroll_event"
    if mutation == "required_field":
        required = ("not_a_protected_field",)

    batch = verifier.verified_creation_evidences(
        [(table, bad), ("ledger_transaction", other)], class_id, required_fields=required,
    )

    assert batch.chain_status == "COMPLETE"
    assert batch.evidence[0] is None
    assert verifier.verified_creation_evidence(table, bad, class_id, required_fields=required) is None
    # A neighbour's failure never leaks into, or rescues, another row.
    expected_other = verifier.verified_creation_evidence(
        "ledger_transaction", other, class_id, required_fields=required,
    )
    assert batch.evidence[1] == expected_other


def test_foreign_class_rows_are_not_proven(client, app, ledger_rows):
    class_id, rows = ledger_rows
    foreign = provision_ledger_classroom("ap_csp_p3", app).class_id
    batch = verifier.verified_creation_evidences(_items(rows), foreign)
    assert all(proof is None for proof in batch.evidence)
    assert all(verifier.verified_creation_evidence("ledger_transaction", row, foreign) is None for row in rows)


# ---------------------------------------------------------------------------
# Work bound
# ---------------------------------------------------------------------------

def test_batch_walks_the_chain_once_however_many_rows(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    chain = _chain_length(class_id)
    assert chain >= len(rows)

    with _work_counter(monkeypatch) as one_row:
        verifier.verified_creation_evidences(_items(rows[:1]), class_id)
    with _work_counter(monkeypatch) as all_rows:
        batch = verifier.verified_creation_evidences(_items(rows * 3), class_id)

    assert all(proof is not None for proof in batch.evidence)
    assert one_row == all_rows == {"hmac": chain, "event_queries": 1}


def test_single_row_loop_is_the_quadratic_cost_being_replaced(client, app, ledger_rows, monkeypatch):
    """Documents the regression the batch prevents: per-row proof re-walks the chain."""
    class_id, rows = ledger_rows
    chain = _chain_length(class_id)
    with _work_counter(monkeypatch) as per_row:
        for row in rows:
            verifier.verified_creation_evidence("ledger_transaction", row, class_id)
    assert per_row["hmac"] == chain * len(rows)


def test_feat_ledger_creation_proofs_use_one_walk(client, app, ledger_rows, monkeypatch):
    from app.feats.attendance_interval_invalidation_feat import ledger_creation_proofs
    class_id, rows = ledger_rows
    with _work_counter(monkeypatch) as counts:
        proofs = ledger_creation_proofs(rows, class_id)
    assert [proof.row_pk for proof in proofs] == [str(row.id) for row in rows]
    assert counts == {"hmac": _chain_length(class_id), "event_queries": 1}


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def test_chain_budget_exhaustion_is_unavailable_never_a_prefix(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    with _work_counter(monkeypatch) as counts:
        batch = verifier.verified_creation_evidences(
            _items(rows), class_id, max_chain_events=_chain_length(class_id) - 1,
        )
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")
    assert batch.evidence == (None,) * len(rows)
    assert counts["hmac"] == 0


def test_walk_stops_at_budget_when_head_understates_the_chain(client, app, ledger_rows, monkeypatch):
    """More stored events than the budget is unavailable even if the head claims fewer."""
    class_id, rows = ledger_rows
    chain = _chain_length(class_id)
    real = verifier._historical_head_snapshot(f"class:{class_id}")
    small = Head(chain - 1, chain - 1, real.latest_hash)
    monkeypatch.setattr(verifier, "_historical_head_snapshot", lambda scope: small)
    batch = verifier.verified_creation_evidences(_items(rows), class_id, max_chain_events=chain - 1)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")
    assert batch.evidence == (None,) * len(rows)


def test_row_budget_exhaustion_is_unavailable(client, app, ledger_rows):
    class_id, rows = ledger_rows
    batch = verifier.verified_creation_evidences(_items(rows), class_id, max_rows=len(rows) - 1)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")
    assert batch.evidence == (None,) * len(rows)


@pytest.mark.parametrize("keyword, bound", [
    ("max_chain_events", 0), ("max_chain_events", True), ("max_chain_events", "10"),
    ("max_chain_events", verifier.CREATION_PROOF_MAX_CHAIN_EVENTS + 1),
    ("max_rows", 0), ("max_rows", -1), ("max_rows", verifier.CREATION_PROOF_MAX_ROWS + 1),
])
def test_invalid_or_raised_budgets_are_rejected(client, app, ledger_rows, keyword, bound):
    class_id, rows = ledger_rows
    with pytest.raises(ValueError, match="bound"):
        verifier.verified_creation_evidences(_items(rows), class_id, **{keyword: bound})


def test_requests_must_be_table_row_pairs(client, app, ledger_rows):
    class_id, rows = ledger_rows
    with pytest.raises(ValueError, match="pairs"):
        verifier.verified_creation_evidences(rows, class_id)


# ---------------------------------------------------------------------------
# Unavailable and contradictory chains
# ---------------------------------------------------------------------------

def test_head_changed_during_read_is_unavailable(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    real = verifier._historical_head_snapshot
    reads = []

    def advancing(scope):
        head = real(scope)
        reads.append(head)
        if len(reads) == 1:
            return head
        return Head(head.latest_sequence + 1, head.event_count + 1, "advanced")

    monkeypatch.setattr(verifier, "_historical_head_snapshot", advancing)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "EVIDENCE_CHANGED_DURING_READ")
    assert batch.evidence == (None,) * len(rows)
    assert len(reads) == 2


def test_missing_head_is_unavailable(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    monkeypatch.setattr(verifier, "_historical_head_snapshot", lambda scope: None)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "MISSING_CHAIN_HEAD")
    assert batch.evidence == (None,) * len(rows)


@pytest.mark.parametrize("head", [Head(-1, 0, "x"), Head(1, -1, "x"), Head("1", 1, "x"), Head(1, 1, None)])
def test_malformed_head_is_invalid(client, app, ledger_rows, monkeypatch, head):
    class_id, rows = ledger_rows
    monkeypatch.setattr(verifier, "_historical_head_snapshot", lambda scope: head)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("INVALID", "MALFORMED_CHAIN_HEAD")
    assert batch.evidence == (None,) * len(rows)


def test_inconsistent_head_is_invalid(client, app, ledger_rows):
    class_id, rows = ledger_rows
    head = db.session.get(ChainHead, f"class:{class_id}")
    # Synthetic corruption fixture, not a lawful creation assertion.
    with system_audit_authority("synthetic batch-proof inconsistent head"):
        head.event_count += 1
        db.session.commit()
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("INVALID", "CHAIN_HEAD_MISMATCH")
    assert batch.evidence == (None,) * len(rows)
    assert all(verifier.verified_creation_evidence("ledger_transaction", row, class_id) is None for row in rows)


def test_hmac_mismatch_is_invalid(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    compute = verifier._compute_event_hash

    def tamper_second(key, previous, scope, sequence, *rest):
        value = compute(key, previous, scope, sequence, *rest)
        return "0" * 64 if sequence == 2 else value

    monkeypatch.setattr(verifier, "_compute_event_hash", tamper_second)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("INVALID", "ENVELOPE_HMAC_MISMATCH")
    assert batch.evidence == (None,) * len(rows)


def test_continuity_break_is_invalid(client, app, ledger_rows, monkeypatch):
    """A stored previous_hash that does not chain is a contradiction, not a prefix."""
    class_id, rows = ledger_rows
    original_execute = db.session.execute

    class Broken:
        def __init__(self, item):
            self._item = item

        def __getattr__(self, name):
            if name == "previous_hash" and self._item.sequence_number == 2:
                return "f" * 64
            return getattr(self._item, name)

    class Result:
        def __init__(self, inner):
            self._inner = inner

        def __iter__(self):
            return (Broken(item) for item in self._inner)

        def close(self):
            self._inner.close()

    def execute(statement, *args, **kwargs):
        result = original_execute(statement, *args, **kwargs)
        return Result(result) if "audit_events" in str(statement) else result

    monkeypatch.setattr(db.session, "execute", execute)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("INVALID", "CHAIN_CONTINUITY_MISMATCH")
    assert batch.evidence == (None,) * len(rows)


def test_missing_signing_key_is_unavailable(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    monkeypatch.setattr(verifier, "_SIGNING_KEY", b"")
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "AUDIT_KEY_UNAVAILABLE")
    assert batch.evidence == (None,) * len(rows)


def test_infrastructure_failure_is_unavailable(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows

    def fail(scope):
        raise OperationalError("SELECT", {}, Exception("database unavailable"))

    monkeypatch.setattr(verifier, "_historical_head_snapshot", fail)
    batch = verifier.verified_creation_evidences(_items(rows), class_id)
    assert (batch.chain_status, batch.reason) == ("UNAVAILABLE", "AUDIT_INFRASTRUCTURE_UNAVAILABLE")
    assert batch.evidence == (None,) * len(rows)


def test_rows_without_lineage_need_no_walk(client, app, ledger_rows, monkeypatch):
    class_id, rows = ledger_rows
    with _work_counter(monkeypatch) as counts:
        batch = verifier.verified_creation_evidences(
            [("ledger_transaction", _copy(rows[0], lineage_event_id=None))], class_id,
        )
    assert batch.evidence == (None,)
    assert counts == {"hmac": 0, "event_queries": 0}


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------

def test_batch_is_pure_and_does_not_autoflush(client, app, ledger_rows):
    class_id, rows = ledger_rows
    head = db.session.get(ChainHead, f"class:{class_id}")
    stored = (head.latest_sequence, head.event_count, head.latest_hash)
    session = db.session()
    flushes = []

    def on_flush(*_args):
        flushes.append(True)

    sa_event.listen(session, "before_flush", on_flush)
    try:
        # An unflushed change to a mutable ORM head is neither flushed nor trusted.
        head.event_count += 1
        batch = verifier.verified_creation_evidences(_items(rows), class_id)
        assert batch.chain_status == "COMPLETE"
        assert all(proof is not None for proof in batch.evidence)
        assert flushes == []
        assert head in session.dirty
    finally:
        sa_event.remove(session, "before_flush", on_flush)
        db.session.rollback()
    head = db.session.get(ChainHead, f"class:{class_id}")
    assert (head.latest_sequence, head.event_count, head.latest_hash) == stored
