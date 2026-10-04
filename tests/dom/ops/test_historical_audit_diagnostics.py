"""Bounded observation fixtures, not genuine predecessor-created evidence.

Exact-source definitions are checked separately. These synthetic Ops envelopes
exercise diagnostics without pretending to establish historical writer identity.
"""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest
from sqlalchemy import event as sa_event

from app.extensions import db
from app.models import ChainHead
from app.services.audit_service import emit_audit_event, system_audit_authority
from app.utils import audit_verifier as verifier


@pytest.fixture
def scoped_envelope(app):
    row = SimpleNamespace(
        id=123, class_id="historical-diagnostic-class", amount=Decimal("1.00"),
        account_type="checking", type="payroll", status="PENDING", seat_id=7,
        target_seat_id=7, actor_seat_id=9, mechanism="teacher", description="fixture",
        correlation_id="fixture-correlation",
    )
    fields = {name: getattr(row, name) for name in verifier.HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS}
    with system_audit_authority("synthetic diagnostic envelope; not historical proof"):
        event = emit_audit_event(
            "ledger_transaction", str(row.id), "INSERT", fields,
            class_id=row.class_id, signature_version=1,
        )
    db.session.commit()
    row.lineage_event_id = event.id
    row.lineage_token = event.hmac_signature
    row.lineage_version = 1
    return row


def test_authenticated_envelope_does_not_prove_historical_payload(scoped_envelope):
    row = scoped_envelope
    row.status = "POSTED"  # Creation PENDING is intentionally never reconstructed.
    proof = verifier.diagnose_historical_audit_coverage("ledger_transaction", row, row.class_id)
    assert proof.envelope_status == "AUTHENTICATED"
    assert proof.chain_status == "COMPLETE"
    assert len(proof.candidate_protected_fields) == 11
    assert proof.confirmed_protected_fields == ()
    assert "status" in proof.unavailable_protected_fields
    assert "PER_RECORD_EMITTER_PROVENANCE_UNAVAILABLE" in proof.reasons
    assert not isinstance(proof, verifier.VerifiedCreationEvidence)


@pytest.mark.parametrize("argument", ["source_descriptor", "emitter_provenance"])
def test_caller_claim_cannot_establish_original_emitter(scoped_envelope, argument):
    with pytest.raises(ValueError, match="assignment is unavailable"):
        verifier.diagnose_historical_audit_coverage(
            "ledger_transaction", scoped_envelope, scoped_envelope.class_id,
            **{argument: verifier.HISTORICAL_LEDGER_V1_SOURCE_REVISION},
        )


@pytest.mark.parametrize("bound", [0, -1, True, "1", 1001])
def test_invalid_chain_budget_denied_before_query(scoped_envelope, bound):
    with pytest.raises(ValueError, match="bound"):
        verifier.diagnose_historical_audit_coverage(
            "ledger_transaction", scoped_envelope, scoped_envelope.class_id,
            max_chain_events=bound,
        )


def test_foreign_class_is_denied(scoped_envelope):
    with pytest.raises(ValueError, match="scope"):
        verifier.diagnose_historical_audit_coverage("ledger_transaction", scoped_envelope, "foreign")


def test_chain_budget_never_accepts_verified_prefix(scoped_envelope):
    row = scoped_envelope
    with system_audit_authority("synthetic second diagnostic event"):
        emit_audit_event("ledger_transaction", "124", "INSERT", {}, class_id=row.class_id)
    db.session.commit()
    result = verifier.diagnose_historical_audit_coverage(
        "ledger_transaction", row, row.class_id, max_chain_events=1,
    )
    assert result.envelope_status == "UNAVAILABLE"
    assert result.chain_status == "UNAVAILABLE"
    assert result.reasons == ("EVIDENCE_LIMIT_EXCEEDED",)


def test_head_disagreement_is_integrity_failure(scoped_envelope):
    row = scoped_envelope
    head = db.session.get(ChainHead, f"class:{row.class_id}")
    # Synthetic corruption fixture, not a lawful historical creation assertion.
    with system_audit_authority("synthetic diagnostic inconsistent head"):
        head.event_count += 1
        db.session.commit()
    result = verifier.diagnose_historical_audit_coverage("ledger_transaction", row, row.class_id)
    assert result.chain_status == "INVALID"
    assert result.reasons == ("CHAIN_HEAD_MISMATCH",)


def test_missing_linkage_is_coverage_gap(scoped_envelope):
    row = scoped_envelope
    row.lineage_event_id = None
    result = verifier.diagnose_historical_audit_coverage("ledger_transaction", row, row.class_id)
    assert result.envelope_status == "UNAVAILABLE"
    assert result.reasons == ("MISSING_LINEAGE",)


def test_batch_walks_once_and_does_not_flush_pending_changes(scoped_envelope):
    row = scoped_envelope
    head = db.session.get(ChainHead, f"class:{row.class_id}")
    head.last_updated_utc = head.last_updated_utc.replace(microsecond=0)
    flushes, queries = [], []
    def on_flush(*args):
        flushes.append(True)
    def on_query(conn, cursor, statement, *args):
        if "FROM audit_events" in statement:
            queries.append(statement)
    sa_event.listen(db.session(), "before_flush", on_flush)
    sa_event.listen(db.engine, "before_cursor_execute", on_query)
    try:
        results = verifier.diagnose_historical_audit_coverages(
            "ledger_transaction", (row, row), row.class_id,
        )
        assert all(item.chain_status == "COMPLETE" for item in results)
        assert flushes == []
        assert len(queries) == 1
        assert head in db.session.dirty
    finally:
        sa_event.remove(db.session(), "before_flush", on_flush)
        sa_event.remove(db.engine, "before_cursor_execute", on_query)
        db.session.rollback()


def test_broken_linkage_rejected_even_with_good_chain(scoped_envelope):
    row = scoped_envelope
    row.lineage_token = "incorrect"
    result = verifier.diagnose_historical_audit_coverage("ledger_transaction", row, row.class_id)
    assert result.envelope_status == "INVALID"
    assert result.reasons == ("LINKAGE_MISMATCH",)


def _source(path):
    repository = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["git", "show", f"{verifier.HISTORICAL_LEDGER_V1_SOURCE_REVISION}:{path}"],
        cwd=repository, text=True, capture_output=True,
    )
    assert result.returncode == 0, (
        "Historical source verification requires the immutable predecessor commit "
        f"{verifier.HISTORICAL_LEDGER_V1_SOURCE_REVISION}. Fetch complete git history "
        "before running this test; missing source evidence must not be skipped."
    )
    return result.stdout


def _assignment(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise AssertionError(name)


def test_actual_deployed_emitters_declared_eleven_old_verifier_only_eight():
    for path in ("app/services/ledger_posting_service.py", "app/utils/transaction_idempotency.py"):
        fields = _assignment(_source(path), "_TRANSACTION_AUDIT_FIELDS")
        assert tuple(fields) == verifier.HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS
    old_registry = _assignment(_source("app/utils/audit_verifier.py"), "PROTECTED_FIELDS_BY_TABLE")
    assert len(old_registry["ledger_transaction"]) == 8
    assert set(old_registry["ledger_transaction"]) < set(verifier.HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS)


def test_historical_payload_serialization_is_exact_without_verifier_field_substitution():
    source = ast.parse(_source("app/services/audit_service.py"))
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                 and node.name in ("_canonical_payload", "_sha256_hex", "_compute_payload_digest")]
    from datetime import datetime
    import hashlib
    import json
    from app.utils.canonical_temporal_resolver import ensure_utc
    namespace = dict(Any=object, datetime=datetime, ensure_utc=ensure_utc, hashlib=hashlib, json=json)
    exec(compile(ast.Module(body=functions, type_ignores=[]), "deployed-audit-source", "exec"), namespace)
    fields = {name: None for name in verifier.HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS}
    fields.update(amount=Decimal("1.00"), status="PENDING")
    historical = namespace["_compute_payload_digest"]("ledger_transaction", "123", "INSERT", "scope", fields)
    assert historical == verifier._compute_payload_digest("ledger_transaction", "123", "INSERT", "scope", fields)
    eight = {name: value for name, value in fields.items()
             if name not in ("target_seat_id", "actor_seat_id", "mechanism")}
    assert namespace["_compute_payload_digest"]("ledger_transaction", "123", "INSERT", "scope", eight) != historical


def test_infrastructure_unavailable_is_not_false_integrity_failure(scoped_envelope, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    def broken(*args, **kwargs):
        raise SQLAlchemyError("sensitive driver detail must not escape")
    monkeypatch.setattr(verifier, "_diagnose_historical_audit_coverages", broken)
    result = verifier.diagnose_historical_audit_coverage(
        "ledger_transaction", scoped_envelope, scoped_envelope.class_id,
    )
    assert result.envelope_status == "UNAVAILABLE"
    assert result.reasons == ("AUDIT_INFRASTRUCTURE_UNAVAILABLE",)
    assert "sensitive" not in str(result)


def test_batch_rejects_over_budget_without_truncating(scoped_envelope):
    with pytest.raises(ValueError, match="row bound"):
        verifier.diagnose_historical_audit_coverages(
            "ledger_transaction", (scoped_envelope, scoped_envelope),
            scoped_envelope.class_id, max_rows=1,
        )


def test_legitimate_head_change_during_walk_is_unavailable(scoped_envelope, monkeypatch):
    from collections import namedtuple
    Head = namedtuple("Head", "latest_sequence event_count latest_hash")
    first = verifier._historical_head_snapshot(f"class:{scoped_envelope.class_id}")
    observations = iter((first, Head(first.latest_sequence + 1, first.event_count + 1, "new-head")))
    monkeypatch.setattr(verifier, "_historical_head_snapshot", lambda scope: next(observations))
    result = verifier.diagnose_historical_audit_coverage(
        "ledger_transaction", scoped_envelope, scoped_envelope.class_id,
    )
    assert result.envelope_status == "UNAVAILABLE"
    assert result.chain_status == "UNAVAILABLE"
    assert result.reasons == ("EVIDENCE_CHANGED_DURING_READ",)
