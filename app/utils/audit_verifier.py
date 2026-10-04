"""Audit Chain Verifier — Phase 5 implementation.

Provides:
  verify_chain(chain_scope, limit)       — Walk a chain and validate HMAC continuity
  verify_row_lineage(table_name, pk, m)  — Spot-check a single row's payload digest
  run_full_invariant_check()             — Nightly sweep across all active chains

These functions only READ from the DB. They never write.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import sqlalchemy as sa

from app.extensions import db
from app.utils.canonical_temporal_resolver import utc_now

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protected fields per table — must match the fields passed to audit_protected()
# at write time. Missing a field here → false INVALID; extra field here → false
# INVALID too. Keep in sync with the canonical Ledger write services.
# ---------------------------------------------------------------------------

PROTECTED_FIELDS_BY_TABLE: dict[str, list[str]] = {
    "attendance_interval_invalidation": ["id", "class_id", "actor_seat_id", "target_seat_id", "opening_event_id", "closing_event_id", "recorded_at", "reason_code", "idempotency_key", "correlation_id", "receipt_json"],
    "payroll_event": [
        "id", "class_id", "payroll_cycle_id", "actor_seat_id", "target_seat_id",
        "correlation_id", "idempotency_key", "policy_uuid", "mechanism",
        "payroll_event_type", "recorded_at", "summary_json",
    ],
    # Keep both names during the Wave 5 table rename transition.
    "transaction": [
        "amount", "account_type", "type", "status",
        "class_id", "seat_id", "description", "correlation_id",
    ],
    "ledger_transaction": [
        "id", "class_id", "actor_seat_id", "target_seat_id", "mechanism", "amount_cents",
        "timestamp", "account_type", "description", "correlation_id", "feat_code",
        "idempotency_key", "policy_id", "type", "posting_sequence", "command_reservation_id",
        "compensation_origin_locator", "compensation_amount_cents", "correction_intent_locator"],
}


LEDGER_FIELDS_BY_VERSION = {
    2: (
        "id", "class_id", "actor_seat_id", "target_seat_id", "mechanism", "amount_cents",
        "timestamp", "account_type", "description", "correlation_id", "feat_code",
        "idempotency_key", "policy_id", "type", "posting_sequence", "command_reservation_id",
    ),
    3: (
        "id", "class_id", "actor_seat_id", "target_seat_id", "mechanism", "amount_cents",
        "timestamp", "account_type", "description", "correlation_id", "feat_code",
        "idempotency_key", "policy_id", "type", "posting_sequence", "command_reservation_id",
        "compensation_origin_locator", "compensation_amount_cents", "correction_intent_locator",
    ),
}



# ---------------------------------------------------------------------------
# Result types (re-exported from audit_service for convenience)
# ---------------------------------------------------------------------------

from datetime import timezone as _UTC

from app.services.audit_service import (
    LineageState,
    VerificationResult,
    RowVerificationResult,
    _compute_event_hash,
    _compute_payload_digest,
    _SIGNING_KEY,
)


def _utc_isoformat(dt) -> str:
    """Return an ISO-8601 string normalized to UTC ("+00:00" suffix).

    The emit path computes event_hash using `now_utc.isoformat()` where
    now_utc is always UTC (from the centralized `utc_now()` helper). SQLAlchemy may
    return stored datetimes in the local session timezone. Normalizing here
    ensures the verifier recomputes the same string used at emit time.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC.utc)
    else:
        dt = dt.astimezone(_UTC.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Internal helper: rebuild actor_context_json from AuditEvent fields
# ---------------------------------------------------------------------------

def _rebuild_actor_context_json(event) -> str:
    ctx = {
        "actor_type": event.actor_type,
        "actor_id_hash": event.actor_id_hash,
        "feat_id": event.feat_id,
        "correlation_id": event.correlation_id,
    }
    return json.dumps(ctx, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

def verify_chain(chain_scope: str, limit: int = 500) -> VerificationResult:
    """Walk the chain for chain_scope and verify HMAC and hash continuity.

    Steps:
    1. Load events ordered by sequence_number (up to limit).
    2. Recompute each event's event_hash from stored fields.
    3. Verify that previous_hash on event N equals event_hash of event N-1.
    4. Verify no sequence gaps.

    Returns VerificationResult with state VERIFIED, INVALID, or DEGRADED.
    """
    from app.models import AuditEvent, ChainHead  # late import

    try:
        head = ChainHead.query.filter_by(chain_scope=chain_scope).first()
        if head is None:
            return VerificationResult(
                chain_scope=chain_scope,
                state=LineageState.DEGRADED,
                event_count=0,
                failure_type="MISSING_CHAIN_HEAD",
                first_bad_sequence=None,
                last_good_hash=None,
                detail=f"No ChainHead row found for scope '{chain_scope}'",
            )

        events = (
            AuditEvent.query
            .filter_by(chain_scope=chain_scope)
            .order_by(AuditEvent.sequence_number.asc())
            .limit(limit)
            .all()
        )

        if not events:
            return VerificationResult(
                chain_scope=chain_scope,
                state=LineageState.VERIFIED,
                event_count=0,
                failure_type=None,
                first_bad_sequence=None,
                last_good_hash="genesis",
                detail="Chain is empty (no events yet)",
            )

        previous_hash = "genesis"
        last_good_hash = "genesis"
        expected_sequence = 1

        for event in events:
            # Sequence gap check
            if event.sequence_number != expected_sequence:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="SEQUENCE_GAP",
                    first_bad_sequence=expected_sequence,
                    last_good_hash=last_good_hash,
                    detail=(
                        f"Expected sequence {expected_sequence}, "
                        f"found {event.sequence_number}"
                    ),
                )

            # previous_hash continuity check
            if event.previous_hash != previous_hash:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="BAD_HASH",
                    first_bad_sequence=event.sequence_number,
                    last_good_hash=last_good_hash,
                    detail=(
                        f"Hash chain broken at sequence {event.sequence_number}: "
                        f"expected previous_hash={previous_hash!r}, "
                        f"stored={event.previous_hash!r}"
                    ),
                )

            # HMAC recomputation — normalize to UTC so isoformat matches emit path
            created_at_str = _utc_isoformat(event.created_at_utc)
            actor_context_json = _rebuild_actor_context_json(event)
            expected_hash = _compute_event_hash(
                _SIGNING_KEY,
                previous_hash,
                chain_scope,
                event.sequence_number,
                event.table_name,
                event.row_pk,
                event.operation,
                actor_context_json,
                event.payload_digest,
                created_at_str,
            )
            if expected_hash != event.event_hash:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="BAD_HMAC",
                    first_bad_sequence=event.sequence_number,
                    last_good_hash=last_good_hash,
                    detail=f"HMAC mismatch at sequence {event.sequence_number}",
                )

            previous_hash = event.event_hash
            last_good_hash = event.event_hash
            expected_sequence += 1

        return VerificationResult(
            chain_scope=chain_scope,
            state=LineageState.VERIFIED,
            event_count=len(events),
            failure_type=None,
            first_bad_sequence=None,
            last_good_hash=last_good_hash,
            detail=f"Verified {len(events)} event(s) (limit={limit})",
        )

    except Exception as exc:
        logger.exception("Chain verification failed for scope %s", chain_scope)
        return VerificationResult(
            chain_scope=chain_scope,
            state=LineageState.DEGRADED,
            event_count=0,
            failure_type="VERIFIER_ERROR",
            first_bad_sequence=None,
            last_good_hash=None,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Row-level lineage verification
# ---------------------------------------------------------------------------

def verify_row_lineage(
    table_name: str,
    row_pk: str | int,
    model_instance,
) -> RowVerificationResult:
    """Verify that a row's current field values match its linked AuditEvent.

    Lineage state:
    - UNVERIFIED: lineage_event_id is NULL — pre-rollout row, NOT an incident.
    - INVALID: payload_digest mismatch — row was mutated outside a lawful path.
    - VERIFIED: current field values hash to the stored payload_digest.
    - DEGRADED: unexpected error during verification (infrastructure failure).
    """
    from app.models import AuditEvent  # late import

    row_pk_str = str(row_pk)

    lineage_event_id = getattr(model_instance, "lineage_event_id", None)
    if lineage_event_id is None:
        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.UNVERIFIED,
            lineage_event_id=None,
            failure_type=None,
            detail="Row predates lineage rollout — UNVERIFIED is expected, not an incident",
        )

    try:
        event = AuditEvent.query.get(lineage_event_id)
        if event is None:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.INVALID,
                lineage_event_id=lineage_event_id,
                failure_type="MISSING_EVENT",
                detail=f"AuditEvent id={lineage_event_id} not found — deleted or never created",
            )

        if table_name == "ledger_transaction" and event.signature_version not in {2,3}:
            return RowVerificationResult(table_name=table_name, row_pk=row_pk_str,
                state=LineageState.DEGRADED, lineage_event_id=lineage_event_id,
                failure_type="VERIFIER_COVERAGE_UNAVAILABLE",
                detail="Historical Ledger signature uses a retired stored-state payload; current canonical coverage is unavailable.")

        protected_fields = PROTECTED_FIELDS_BY_TABLE.get(table_name)
        if table_name == "ledger_transaction":
            protected_fields = LEDGER_FIELDS_BY_VERSION[event.signature_version]
        if protected_fields is None:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.DEGRADED,
                lineage_event_id=lineage_event_id,
                failure_type="UNKNOWN_TABLE",
                detail=f"No protected field definition for table '{table_name}'",
            )

        if any(not hasattr(model_instance, field) for field in protected_fields):
            return RowVerificationResult(table_name=table_name, row_pk=row_pk_str,
                state=LineageState.DEGRADED, lineage_event_id=lineage_event_id,
                failure_type="VERIFIER_COVERAGE_UNAVAILABLE", detail="Required protected field is unavailable.")
        current_values = {f: getattr(model_instance, f) for f in protected_fields}
        current_digest = _compute_payload_digest(
            event.table_name,
            event.row_pk,
            event.operation,
            event.class_id,
            current_values,
        )

        if current_digest != event.payload_digest:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.INVALID,
                lineage_event_id=lineage_event_id,
                failure_type="PAYLOAD_MISMATCH",
                detail=(
                    f"Payload digest mismatch for {table_name}:{row_pk_str} — "
                    f"row may have been mutated outside the canonical write path"
                ),
            )

        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.VERIFIED,
            lineage_event_id=lineage_event_id,
            failure_type=None,
            detail=None,
        )

    except Exception as exc:
        logger.exception(
            "Row lineage verification failed for %s:%s", table_name, row_pk_str
        )
        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.DEGRADED,
            lineage_event_id=lineage_event_id,
            failure_type="VERIFIER_ERROR",
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Full invariant check (called by nightly scheduled job)
# ---------------------------------------------------------------------------

def run_full_invariant_check() -> list[VerificationResult]:
    """Sweep all active class chains and the system chain.

    Returns one VerificationResult per chain scope. Callers should check
    any result with state != VERIFIED and record the failure details.
    """
    from app.models import ChainHead

    results: list[VerificationResult] = []

    try:
        scopes = [row.chain_scope for row in ChainHead.query.all()]
    except Exception as exc:
        logger.exception("Failed to load chain scopes for invariant check")
        return [
            VerificationResult(
                chain_scope="(all)",
                state=LineageState.DEGRADED,
                event_count=0,
                failure_type="SCOPE_LOAD_ERROR",
                first_bad_sequence=None,
                last_good_hash=None,
                detail=str(exc),
            )
        ]

    for scope in scopes:
        result = verify_chain(scope, limit=1000)
        results.append(result)
        if result.state != LineageState.VERIFIED:
            logger.error(
                "Audit chain INVALID for scope=%s: type=%s seq=%s detail=%s",
                scope, result.failure_type, result.first_bad_sequence, result.detail,
            )

    return results


# ---------------------------------------------------------------------------
# Verifier output recorder (called by scheduled job after invariant check)
# ---------------------------------------------------------------------------

def record_integrity_verification(results: list[VerificationResult]) -> None:
    """Record verifier output without writing to a removed status table."""
    failed = [
        {"scope": r.chain_scope, "type": r.failure_type, "detail": r.detail}
        for r in results
        if r.state != LineageState.VERIFIED
    ]
    if failed:
        logger.warning("Invariant check failures: %s", json.dumps(failed))


def verify_record_creation_lineage(table, row, class_id, *, required_fields=()):
    """Pure Operations proof: scoped creation pointer, payload, coverage and complete chain.

    Required field coverage fails closed when an owner needs evidence its runtime
    protected-field registration does not yet provide. It never substitutes old
    field values or repairs historical evidence.
    """
    from app.services.audit_service import LineageState
    from app.models import AuditEvent, ChainHead
    pointer = getattr(row, "lineage_event_id", None)
    if pointer is None:
        return False
    event = db.session.get(AuditEvent, pointer)
    if event is None or event.table_name != table or event.row_pk != str(row.id) or event.class_id != class_id:
        return False
    fields=PROTECTED_FIELDS_BY_TABLE.get(table, ())
    if table == "ledger_transaction":
        fields = LEDGER_FIELDS_BY_VERSION.get(event.signature_version, ())
    if not set(required_fields).issubset(fields) or any(not hasattr(row,field) for field in fields):
        return False
    if event.chain_scope != f"class:{class_id}" or event.operation != "INSERT":
        return False
    if row.lineage_token != event.hmac_signature or row.lineage_version != event.signature_version:
        return False
    head = db.session.get(ChainHead, event.chain_scope)
    if head is None or event.sequence_number > head.latest_sequence:
        return False
    verification = verify_chain(event.chain_scope, limit=head.latest_sequence + 1)
    if (verification.state != LineageState.VERIFIED or verification.event_count != head.latest_sequence
            or verification.last_good_hash != head.latest_hash or head.event_count != verification.event_count):
        return False
    return verify_row_lineage(table, row.id, row).state == LineageState.VERIFIED


@dataclass(frozen=True)
class VerifiedCreationEvidence:
    """Operations-owned immutable result supplied by an authorized FEAT.

    Consumers match the complete scoped result against their own current
    sources; this is never a client boolean or permission to omit a candidate.
    """
    table_name: str
    row_pk: str
    class_id: str
    lineage_event_id: int
    lineage_token: str
    signature_version: int
    protected_fields: tuple[str, ...]
    protected_values: tuple[tuple[str, object], ...]


def _freeze_evidence_value(value):
    if isinstance(value, dict):
        return tuple((key, _freeze_evidence_value(item)) for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_evidence_value(item) for item in value)
    return value


def verified_creation_evidence(table, row, class_id, *, required_fields=()):
    """Pure scoped Operations proof with exact linked-version coverage.

    Returns None on any unavailable or failed proof. Ledger and other owners
    receive this result through FEAT orchestration, never through domain calls.
    """
    if not verify_record_creation_lineage(table, row, class_id, required_fields=required_fields):
        return None
    from app.models import AuditEvent
    event = db.session.get(AuditEvent, row.lineage_event_id)
    fields = (LEDGER_FIELDS_BY_VERSION.get(event.signature_version, ())
        if table == 'ledger_transaction' else tuple(PROTECTED_FIELDS_BY_TABLE.get(table, ())))
    return VerifiedCreationEvidence(table, str(row.id), class_id, row.lineage_event_id,
        row.lineage_token, event.signature_version, tuple(fields),
        tuple((field, _freeze_evidence_value(getattr(row, field))) for field in fields))


# Server-owned ceilings for the batch creation-proof query (DOM-OPS-002 §6.2C).
# Callers may ask for less, never more. Exceeding either returns unavailable
# evidence for every row: a verified chain prefix is never a complete chain.
CREATION_PROOF_MAX_CHAIN_EVENTS = 100_000
CREATION_PROOF_MAX_ROWS = 2_000
_CREATION_PROOF_STREAM_CHUNK = 2_000

_CHAIN_WALK_COLUMNS = (
    "id", "sequence_number", "previous_hash", "event_hash", "table_name", "row_pk",
    "operation", "actor_type", "actor_id_hash", "feat_id", "correlation_id",
    "payload_digest", "created_at_utc", "class_id", "chain_scope",
    "signature_version", "hmac_signature",
)


@dataclass(frozen=True)
class CreationEvidenceBatch:
    """Operations-owned batch result: one entry per requested row, in order.

    ``chain_status`` is COMPLETE when the whole class chain and its head were
    verified once for this invocation; then a ``None`` entry is a row-specific
    proof failure. UNAVAILABLE (budget, head changed during the read, missing
    key or infrastructure) and INVALID (chain or head contradiction) make every
    entry ``None``. Unavailable evidence grants no authority.
    """
    evidence: tuple
    chain_status: str
    reason: str | None = None


def _creation_proof_fields(table, signature_version):
    if table == "ledger_transaction":
        return tuple(LEDGER_FIELDS_BY_VERSION.get(signature_version, ()))
    return tuple(PROTECTED_FIELDS_BY_TABLE.get(table, ()))


def _row_creation_evidence(table, row, class_id, event, latest_sequence, required_fields):
    """Every row-specific check of §6.2, against an event from a verified walk.

    Mirrors ``verify_record_creation_lineage`` followed by ``verify_row_lineage``:
    scoped pointer and INSERT linkage, token and version, exact linked-version
    field coverage (and the caller's required fields), then the current
    protected payload digest. Returns ``VerifiedCreationEvidence`` or ``None``.
    """
    pointer = getattr(row, "lineage_event_id", None)
    if pointer is None or event is None or event.id != pointer:
        return None
    if (event.table_name != table or event.row_pk != str(getattr(row, "id", None))
            or event.class_id != class_id or event.chain_scope != f"class:{class_id}"
            or event.operation != "INSERT"):
        return None
    if (getattr(row, "lineage_token", None) != event.hmac_signature
            or getattr(row, "lineage_version", None) != event.signature_version):
        return None
    if event.sequence_number > latest_sequence:
        return None
    if table == "ledger_transaction" and event.signature_version not in {2, 3}:
        return None
    fields = _creation_proof_fields(table, event.signature_version)
    if not fields or not set(required_fields).issubset(fields):
        return None
    if any(not hasattr(row, field) for field in fields):
        return None
    values = {field: getattr(row, field) for field in fields}
    digest = _compute_payload_digest(event.table_name, event.row_pk, event.operation, event.class_id, values)
    if digest != event.payload_digest:
        return None
    return VerifiedCreationEvidence(
        table, str(row.id), class_id, pointer, row.lineage_token, event.signature_version,
        fields, tuple((field, _freeze_evidence_value(values[field])) for field in fields),
    )


def _creation_evidence_batch(items, class_id, required_fields, max_chain_events):
    from app.models import AuditEvent

    def unavailable(status, reason):
        return CreationEvidenceBatch(tuple(None for _ in items), status, reason)

    pointers = {getattr(row, "lineage_event_id", None) for _table, row in items} - {None}
    if not pointers:
        # Nothing links to the chain, so nothing can be proven; no walk is needed.
        return CreationEvidenceBatch(tuple(None for _ in items), "COMPLETE", None)
    if not _SIGNING_KEY:
        return unavailable("UNAVAILABLE", "AUDIT_KEY_UNAVAILABLE")
    scope = f"class:{class_id}"
    head = _historical_head_snapshot(scope)
    if head is None:
        return unavailable("UNAVAILABLE", "MISSING_CHAIN_HEAD")
    if (not isinstance(head.latest_sequence, int) or head.latest_sequence < 0
            or not isinstance(head.event_count, int) or head.event_count < 0
            or not isinstance(head.latest_hash, str)):
        return unavailable("INVALID", "MALFORMED_CHAIN_HEAD")
    if head.latest_sequence > max_chain_events or head.event_count > max_chain_events:
        return unavailable("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")

    columns = [getattr(AuditEvent, name) for name in _CHAIN_WALK_COLUMNS]
    statement = (sa.select(*columns)
                 .where(AuditEvent.chain_scope == scope)
                 .order_by(AuditEvent.sequence_number.asc())
                 .limit(max_chain_events + 1)
                 .execution_options(yield_per=_CREATION_PROOF_STREAM_CHUNK))
    linked = {}
    previous = "genesis"
    walked = 0
    failure = None
    result = db.session.execute(statement)
    try:
        for item in result:
            walked += 1
            if walked > max_chain_events:
                failure = ("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")
                break
            if item.sequence_number != walked or item.previous_hash != previous:
                failure = ("INVALID", "CHAIN_CONTINUITY_MISMATCH")
                break
            expected = _compute_event_hash(
                _SIGNING_KEY, previous, scope, item.sequence_number, item.table_name,
                item.row_pk, item.operation, _rebuild_actor_context_json(item),
                item.payload_digest, _utc_isoformat(item.created_at_utc),
            )
            if expected != item.event_hash:
                failure = ("INVALID", "ENVELOPE_HMAC_MISMATCH")
                break
            if item.id in pointers:
                linked[item.id] = item
            previous = item.event_hash
    finally:
        result.close()

    final_head = _historical_head_snapshot(scope)
    if final_head != head:
        # A legitimate concurrent append moves the head atomically: stale, not corrupt.
        return unavailable("UNAVAILABLE", "EVIDENCE_CHANGED_DURING_READ")
    if failure is not None:
        return unavailable(*failure)
    if walked != head.latest_sequence or walked != head.event_count or previous != head.latest_hash:
        return unavailable("INVALID", "CHAIN_HEAD_MISMATCH")
    return CreationEvidenceBatch(tuple(
        _row_creation_evidence(table, row, class_id, linked.get(getattr(row, "lineage_event_id", None)),
                               head.latest_sequence, required_fields)
        for table, row in items
    ), "COMPLETE", None)


def verified_creation_evidences(items, class_id, *, required_fields=(),
                                max_chain_events=CREATION_PROOF_MAX_CHAIN_EVENTS,
                                max_rows=CREATION_PROOF_MAX_ROWS):
    """Bounded batch form of ``verified_creation_evidence`` (DOM-OPS-002 §6.2C).

    ``items`` is an iterable of ``(table, row)`` pairs, all in one class. The
    class chain is walked and its head verified once for the invocation, within
    an explicit event budget, between two independent scalar head reads; every
    row then receives every row-specific §6.2 check against that walk. Reuse is
    confined to this call: nothing is cached or persisted, no caller-supplied
    verification result is accepted, and the read neither autoflushes nor writes.
    """
    from sqlalchemy.exc import SQLAlchemyError

    for budget, ceiling in ((max_chain_events, CREATION_PROOF_MAX_CHAIN_EVENTS), (max_rows, CREATION_PROOF_MAX_ROWS)):
        if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= ceiling:
            raise ValueError("Invalid audit evidence bound.")
    if not class_id:
        raise ValueError("Unsupported audit evidence scope.")
    with db.session.no_autoflush:
        # Callers hold their scoped rows already; keep one result per request.
        selected = tuple(items)
        if any(not isinstance(item, tuple) or len(item) != 2 for item in selected):
            raise ValueError("Creation evidence requests are (table, row) pairs.")
        if len(selected) > max_rows:
            return CreationEvidenceBatch(tuple(None for _ in selected), "UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED")
        if not selected:
            return CreationEvidenceBatch((), "COMPLETE", None)
        try:
            return _creation_evidence_batch(selected, class_id, tuple(required_fields), max_chain_events)
        except SQLAlchemyError:
            logger.exception("Batch creation-evidence read failed for class scope")
            return CreationEvidenceBatch(tuple(None for _ in selected), "UNAVAILABLE",
                                         "AUDIT_INFRASTRUCTURE_UNAVAILABLE")


# A source descriptor, not a per-record emitter assignment. The exact deployed
# writers both declared eleven fields; the retired verifier listed only eight.
HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS = (
    "amount", "account_type", "type", "status", "class_id", "seat_id",
    "target_seat_id", "actor_seat_id", "mechanism", "description", "correlation_id",
)
HISTORICAL_LEDGER_V1_SOURCE_REVISION = "ad9574334d72fd92cc93402e851ab0ebc22aaad9"


@dataclass(frozen=True)
class HistoricalAuditCoverage:
    """Observations only: never lawful-creation or compensation proof."""

    table_name: str
    row_pk: str
    class_id: str
    signature_version: int | None
    envelope_status: str
    chain_status: str
    candidate_protected_fields: tuple[str, ...]
    confirmed_protected_fields: tuple[str, ...]
    unavailable_protected_fields: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self):
        from dataclasses import asdict
        return asdict(self)


def diagnose_historical_audit_coverage(
    table, row, class_id, *, source_descriptor=None, emitter_provenance=None,
    max_chain_events=1000,
):
    """Single-row form of the bounded diagnostic; never creation evidence."""
    return diagnose_historical_audit_coverages(
        table, (row,), class_id, source_descriptor=source_descriptor,
        emitter_provenance=emitter_provenance, max_chain_events=max_chain_events,
    )[0]


def _historical_head_snapshot(scope):
    """Scalar read avoids ORM identity caching and preserves pending changes."""
    from app.models import ChainHead
    return (ChainHead.query.with_entities(
        ChainHead.latest_sequence, ChainHead.event_count, ChainHead.latest_hash,
    ).filter_by(chain_scope=scope).first())


def _diagnose_historical_audit_coverages(
    table, rows, class_id, *, source_descriptor=None, emitter_provenance=None,
    max_chain_events=1000, max_rows=1000,
):
    """Pure batch: one complete class-chain walk, row-local coverage checks.

    All reuse is within this invocation. No caller-provided verification result,
    historic state substitution, persisted cache, or canonical helper override.
    """
    from itertools import islice
    from app.models import AuditEvent, ChainHead

    for budget in (max_chain_events, max_rows):
        if (not isinstance(budget, int) or isinstance(budget, bool)
                or not 1 <= budget <= 1000):
            raise ValueError("Invalid audit evidence bound.")
    if source_descriptor is not None or emitter_provenance is not None:
        raise ValueError("Historical emitter assignment is unavailable.")
    if table not in PROTECTED_FIELDS_BY_TABLE or not class_id:
        raise ValueError("Unsupported audit diagnostic scope.")
    selected = tuple(islice(iter(rows), max_rows + 1))
    if len(selected) > max_rows:
        raise ValueError("Audit diagnostic row bound exceeded.")
    if any(getattr(row, "class_id", None) != class_id for row in selected):
        raise ValueError("Unauthorized audit diagnostic scope.")
    if not selected:
        return ()
    scope = f"class:{class_id}"
    with db.session.no_autoflush:
        head = None
        events = ()
        chain_status, chain_reason = "UNAVAILABLE", "MISSING_CHAIN_HEAD"
        if any(getattr(row, "lineage_event_id", None) is not None for row in selected):
            head = _historical_head_snapshot(scope)
            if not _SIGNING_KEY:
                chain_reason = "AUDIT_KEY_UNAVAILABLE"
            elif head is not None:
                if (not isinstance(head.latest_sequence, int) or head.latest_sequence < 0
                        or not isinstance(head.event_count, int) or head.event_count < 0):
                    return tuple(HistoricalAuditCoverage(
                        table, str(getattr(row, "id", "")), class_id, None,
                        "INVALID", "INVALID", (), (), (), ("MALFORMED_CHAIN_HEAD",),
                    ) for row in selected)
                events = (AuditEvent.query.filter_by(chain_scope=scope)
                          .order_by(AuditEvent.sequence_number.asc())
                          .limit(max_chain_events + 1).all())
                if len(events) > max_chain_events or head.latest_sequence > max_chain_events:
                    chain_reason = "EVIDENCE_LIMIT_EXCEEDED"
                else:
                    previous = "genesis"
                    chain_status, chain_reason = "COMPLETE", None
                    for position, item in enumerate(events, 1):
                        if (item.sequence_number != position or item.previous_hash != previous
                                or item.class_id != class_id):
                            chain_status, chain_reason = "INVALID", "CHAIN_CONTINUITY_MISMATCH"
                            break
                        expected = _compute_event_hash(
                            _SIGNING_KEY, previous, scope, position, item.table_name,
                            item.row_pk, item.operation, _rebuild_actor_context_json(item),
                            item.payload_digest, _utc_isoformat(item.created_at_utc),
                        )
                        if expected != item.event_hash or item.hmac_signature != item.event_hash:
                            chain_status, chain_reason = "INVALID", "ENVELOPE_HMAC_MISMATCH"
                            break
                        previous = item.event_hash
                    final_head = _historical_head_snapshot(scope)
                    if final_head != head:
                        # A legitimate concurrent append changes the head atomically.
                        # Report a stale observation, not an integrity incident.
                        chain_status, chain_reason = "UNAVAILABLE", "EVIDENCE_CHANGED_DURING_READ"
                    elif chain_status == "COMPLETE" and (
                            len(events) != head.latest_sequence or len(events) != head.event_count
                            or previous != head.latest_hash):
                        chain_status, chain_reason = "INVALID", "CHAIN_HEAD_MISMATCH"
        by_id = {event.id: event for event in events}
        outcomes = []
        for row in selected:
            row_pk = str(getattr(row, "id", ""))
            pointer = getattr(row, "lineage_event_id", None)
            event = by_id.get(pointer)
            version = event.signature_version if event is not None else None
            candidate = (HISTORICAL_LEDGER_V1_CANDIDATE_FIELDS if version == 1
                         and table in ("ledger_transaction", "transaction")
                         else LEDGER_FIELDS_BY_VERSION.get(version, ())
                         if table == "ledger_transaction"
                         else tuple(PROTECTED_FIELDS_BY_TABLE.get(table, ())))

            def result(envelope, reason, confirmed=(), row_chain_status=None):
                reasons = () if reason is None else (reason,) if isinstance(reason, str) else reason
                outcomes.append(HistoricalAuditCoverage(
                    table, row_pk, class_id, version, envelope,
                    row_chain_status or chain_status, tuple(candidate), tuple(confirmed),
                    tuple(field for field in candidate if field not in confirmed), tuple(reasons),
                ))

            if pointer is None:
                result("UNAVAILABLE", "MISSING_LINEAGE", row_chain_status="UNAVAILABLE")
            elif chain_status == "UNAVAILABLE":
                result("UNAVAILABLE", chain_reason)
            elif event is None:
                result("INVALID", "LINKED_EVENT_SCOPE_OR_MISSING")
            elif (event.class_id != class_id or event.chain_scope != scope
                    or event.table_name != table or event.row_pk != row_pk
                    or event.operation != "INSERT"
                    or getattr(row, "lineage_token", None) != event.hmac_signature
                    or getattr(row, "lineage_version", None) != version):
                result("INVALID", "LINKAGE_MISMATCH")
            elif chain_status == "INVALID":
                result("INVALID", chain_reason)
            elif version == 1 and table in ("ledger_transaction", "transaction"):
                result("AUTHENTICATED", (
                    "PER_RECORD_EMITTER_PROVENANCE_UNAVAILABLE",
                    "ORIGINAL_PROTECTED_VALUES_UNAVAILABLE", "UNSIGNED_MONETARY_PROVENANCE",
                ))
            elif not candidate:
                result("AUTHENTICATED", "UNSUPPORTED_SIGNATURE_VERSION")
            elif any(not hasattr(row, field) for field in candidate):
                result("AUTHENTICATED", "PROTECTED_FIELD_UNAVAILABLE")
            elif _compute_payload_digest(
                    table, row_pk, "INSERT", class_id,
                    {field: getattr(row, field) for field in candidate},
            ) != event.payload_digest:
                result("AUTHENTICATED", "PROTECTED_PAYLOAD_MISMATCH")
            else:
                result("AUTHENTICATED", None, confirmed=candidate)
        return tuple(outcomes)


def diagnose_historical_audit_coverages(
    table, rows, class_id, *, source_descriptor=None, emitter_provenance=None,
    max_chain_events=1000, max_rows=1000,
):
    """Bounded batch public boundary; infrastructure failures remain unavailable."""
    from itertools import islice
    from sqlalchemy.exc import SQLAlchemyError
    if (not isinstance(max_rows, int) or isinstance(max_rows, bool)
            or not 1 <= max_rows <= 1000):
        raise ValueError("Invalid audit evidence bound.")
    with db.session.no_autoflush:
        selected = tuple(islice(iter(rows), max_rows + 1))
        try:
            return _diagnose_historical_audit_coverages(
                table, selected, class_id, source_descriptor=source_descriptor,
                emitter_provenance=emitter_provenance, max_chain_events=max_chain_events,
                max_rows=max_rows,
            )
        except SQLAlchemyError:
            # Do not repair IntegrityStatus or roll back another owner's transaction.
            return tuple(HistoricalAuditCoverage(
                table, str(getattr(row, "id", "")), class_id, None, "UNAVAILABLE",
                "UNAVAILABLE", (), (), (), ("AUDIT_INFRASTRUCTURE_UNAVAILABLE",),
            ) for row in selected)
