"""
FEAT-OBL-002: Schedule Next Bill Cycle — bill-cycle succession (DOM-OBL-001 §V.7).

The single canonical writer for recurring successor creation. A caller requests
succession for a lineage; the domain decides whether it is lawful and which cycle
it is:

  - eligibility: the lineage is empty, or its latest cycle is non-terminal and its
    ``next_assessment_at`` has arrived at the resolved reference time (evaluated
    through the canonical temporal resolver, never a local clock);
  - position: the cycle number is derived from authoritative state (``1`` for an
    empty lineage, otherwise ``current + 1``) and is never caller-supplied;
  - replay: decided by command identity, never by row shape. Same identity and
    same fingerprint returns the original cycle; same identity with different
    terms fails closed; a different command that already created the derived
    successor is a conflict, and this command does not re-derive against the
    advanced lineage.

``uq_bill_cycles_ref_cycle`` is the integrity backstop for the race in the last
case, not the idempotency mechanism. ``internal_ref`` is opaque here.

Termination is a separate command (``terminate_bill_cycle``): cessation is not
succession.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import BillCycle, ObligationCommandReservation
from app.services import obligations_service
from app.services.obligations_service import (
    SuccessionEligibility,
    SuccessionAfterTerminalError,
    SuccessionConflictError,
    SuccessionNotDueError,
    SuccessionReplayMismatchError,
)
from app.feats.base import requires_feat_context, FEATContext
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


COMMAND_NAME = "schedule_next_bill_cycle"
FINGERPRINT_VERSION = 1
SUPPORTED_FINGERPRINT_VERSIONS = frozenset({1})
MAX_IDEMPOTENCY_KEY_LENGTH = 255


@dataclass
class ScheduleNextBillCycleRequest:
    """Input contract for bill-cycle succession.

    Caller intent (fingerprinted): ``internal_ref``, ``policy_uuid``,
    ``cycle_boundary_at``, ``next_assessment_at``, ``grace_boundary_at``,
    ``source_version_id``. Command identity: ``idempotency_key`` within
    ``class_id``. Execution context (not fingerprinted): ``reference_time_utc``.
    There is no cycle number: the domain derives it.
    """
    class_id: str  # Multi-tenancy scope (INV-CORE-000)
    internal_ref: str  # Opaque lineage key
    cycle_boundary_at: datetime  # Due boundary for invoking assessment
    next_assessment_at: datetime  # Next lawful boundary; strictly after cycle_boundary_at
    idempotency_key: str  # Command identity
    policy_uuid: str | None = None
    source_version_id: str | None = None
    grace_boundary_at: datetime | None = None
    reference_time_utc: datetime | None = None  # Defaults to the canonical current time


def _iso(value: datetime | None) -> str | None:
    return ensure_utc(value).isoformat() if value is not None else None


def _fingerprint(request: ScheduleNextBillCycleRequest, version: int) -> str:
    """Digest of caller intent only: no derived cycle number, ids, or execution time."""
    if version not in SUPPORTED_FINGERPRINT_VERSIONS:
        raise ValueError(f"Unsupported succession fingerprint version: {version!r}")
    representation = {
        "internal_ref": request.internal_ref,
        "policy_uuid": request.policy_uuid,
        "source_version_id": request.source_version_id,
        "cycle_boundary_at": _iso(request.cycle_boundary_at),
        "next_assessment_at": _iso(request.next_assessment_at),
        "grace_boundary_at": _iso(request.grace_boundary_at),
    }
    encoded = json.dumps(representation, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _replay(reservation: ObligationCommandReservation, request: ScheduleNextBillCycleRequest) -> BillCycle:
    """Cases 1 and 2: the command identity is already recorded."""
    version = reservation.fingerprint_version
    if version not in SUPPORTED_FINGERPRINT_VERSIONS or (
        reservation.replay_fingerprint != _fingerprint(request, version)
    ):
        raise SuccessionReplayMismatchError(
            f"{COMMAND_NAME} identity '{request.idempotency_key}' was already executed "
            f"with different terms; refusing to replay or re-execute."
        )
    return db.session.get(BillCycle, reservation.bill_cycle_id)


def _later_than(ctx, reference_time_utc: datetime, candidate: datetime, reference: datetime) -> bool:
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="later_than",
        reference_time_utc=reference_time_utc,
        candidate=candidate,
        reference=reference,
    ).is_later


def _validate_identity(request: ScheduleNextBillCycleRequest) -> None:
    if not request.class_id or not request.internal_ref:
        raise ValueError(f"{COMMAND_NAME} requires class_id and internal_ref.")
    key = request.idempotency_key
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"{COMMAND_NAME} requires a non-empty idempotency_key (command identity).")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(f"{COMMAND_NAME} idempotency_key exceeds {MAX_IDEMPOTENCY_KEY_LENGTH} characters.")


def schedule_next_bill_cycle(
    request: ScheduleNextBillCycleRequest,
    *,
    context: FEATContext | None = None,
) -> BillCycle:
    """Record the next lawful cycle for a lineage, or replay this command's outcome.

    Returns the BillCycle this command produced (on first execution or exact replay).

    Raises:
    - SuccessionReplayMismatchError: known identity, different terms (case 2).
    - SuccessionConflictError: a different command created the derived successor (case 3).
    - SuccessionAfterTerminalError: the latest cycle is terminal.
    - SuccessionNotDueError: the latest cycle's next_assessment_at has not arrived.
    - ValueError: missing identity, or next_assessment_at not strictly after cycle_boundary_at.
    """
    _validate_identity(request)

    # Replay is decided first, by identity, before any eligibility evaluation:
    # an exact replay returns the original outcome even after the lineage moved on.
    reservation = obligations_service.get_obligation_command_reservation(
        request.class_id, COMMAND_NAME, request.idempotency_key
    )
    if reservation is not None:
        return _replay(reservation, request)

    ctx = SimpleNamespace(class_id=request.class_id)
    reference_time_utc = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=request.reference_time_utc,
    ).canonical_now_utc

    if request.cycle_boundary_at is None or request.next_assessment_at is None:
        raise ValueError(f"{COMMAND_NAME} requires cycle_boundary_at and next_assessment_at.")
    if not _later_than(ctx, reference_time_utc, request.next_assessment_at, request.cycle_boundary_at):
        raise ValueError(
            f"next_assessment_at must be strictly after cycle_boundary_at "
            f"({request.next_assessment_at} <= {request.cycle_boundary_at})"
        )

    # Eligibility and position are read once, from authoritative state. The
    # successor derived here is the only one this command may create.
    eligibility, latest = obligations_service.get_succession_eligibility(
        request.class_id, request.internal_ref, reference_time_utc=reference_time_utc
    )
    if eligibility is SuccessionEligibility.TERMINAL:
        raise SuccessionAfterTerminalError(
            f"lineage '{request.internal_ref}' is terminated at cycle {latest.cycle_number}; "
            f"succession after a terminal cycle is unlawful."
        )
    if eligibility is SuccessionEligibility.NOT_DUE:
        raise SuccessionNotDueError(
            f"lineage '{request.internal_ref}' cycle {latest.cycle_number} is next assessed at "
            f"{latest.next_assessment_at}; succession is not due at {reference_time_utc}."
        )
    cycle_number = 1 if eligibility is SuccessionEligibility.EMPTY else latest.cycle_number + 1

    bill_cycle = BillCycle(
        class_id=request.class_id,
        internal_ref=request.internal_ref,
        cycle_number=cycle_number,
        source_version_id=request.source_version_id,
        policy_uuid=request.policy_uuid,
        cycle_boundary_at=request.cycle_boundary_at,
        next_assessment_at=request.next_assessment_at,
        grace_boundary_at=request.grace_boundary_at,
    )
    try:
        with db.session.begin_nested():
            db.session.add(bill_cycle)
            db.session.flush()
            db.session.add(ObligationCommandReservation(
                class_id=request.class_id,
                command_name=COMMAND_NAME,
                idempotency_key=request.idempotency_key,
                internal_ref=request.internal_ref,
                replay_fingerprint=_fingerprint(request, FINGERPRINT_VERSION),
                fingerprint_version=FINGERPRINT_VERSION,
                bill_cycle_id=bill_cycle.id,
            ))
            db.session.flush()
    except IntegrityError:
        # The identity lookup comes before any conflict verdict (§V.7 case 3):
        # a concurrent execution of this same command is a replay or mismatch.
        reservation = obligations_service.get_obligation_command_reservation(
            request.class_id, COMMAND_NAME, request.idempotency_key
        )
        if reservation is not None:
            return _replay(reservation, request)
        successor_taken = (
            db.session.query(BillCycle.id)
            .filter_by(internal_ref=request.internal_ref, cycle_number=cycle_number)
            .first()
        )
        if successor_taken is not None:
            raise SuccessionConflictError(
                f"cycle {cycle_number} of lineage '{request.internal_ref}' was created by a "
                f"different command; '{request.idempotency_key}' does not replay it and "
                f"does not advance past it."
            )
        raise

    return bill_cycle


@requires_feat_context("FEAT-OBL-002")
def execute_schedule_next_bill_cycle(
    class_id: str,
    internal_ref: str,
    cycle_boundary_at: datetime,
    next_assessment_at: datetime,
    *,
    idempotency_key: str,
    policy_uuid: str | None = None,
    source_version_id: str | None = None,
    grace_boundary_at: datetime | None = None,
    reference_time_utc: datetime | None = None,
) -> BillCycle:
    """Public FEAT interface for bill-cycle succession."""
    return schedule_next_bill_cycle(
        ScheduleNextBillCycleRequest(
            class_id=class_id,
            internal_ref=internal_ref,
            cycle_boundary_at=cycle_boundary_at,
            next_assessment_at=next_assessment_at,
            idempotency_key=idempotency_key,
            policy_uuid=policy_uuid,
            source_version_id=source_version_id,
            grace_boundary_at=grace_boundary_at,
            reference_time_utc=reference_time_utc,
        ),
        context=None,
    )
