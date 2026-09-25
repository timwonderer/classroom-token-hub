"""
Obligations Service — DOM-OBL-001

Read-only canonical interface for obligation facts and derived state.
Does not perform writes; FEATs own all mutation.
"""

from __future__ import annotations

import enum
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import NamedTuple, Optional

from app.extensions import db
from app.models import (
    ObligationAssessment, BillCycle, LedgerMechanism, ObligationCommandReservation, Transaction,
    TransactionStatus,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION, canonical_temporal_resolver, ensure_utc,
)


class BillCycleLifecycleError(Exception):
    """Raised when a bill-cycle mutation violates the lifecycle (DOM-OBL-001 §V.7).

    Succession (`schedule_next_bill_cycle`) is lawful only for an empty lineage or
    a non-terminal latest cycle whose ``next_assessment_at`` has arrived. The
    interim insurance genesis command (`establish_bill_cycle`) raises this when the
    lineage is not empty.
    """


class SuccessionNotDueError(BillCycleLifecycleError):
    """Succession requested before the latest cycle's ``next_assessment_at``."""


class SuccessionAfterTerminalError(BillCycleLifecycleError):
    """Succession requested for a lineage whose latest cycle is terminal."""


class SuccessionReplayMismatchError(Exception):
    """DOM-OBL-001 §V.7 case 2: a known command identity presented with different terms."""


class SuccessionConflictError(Exception):
    """DOM-OBL-001 §V.7 case 3: a different command created the derived successor.

    Never a replay and never a generic uniqueness failure. The command does not
    re-derive against the advanced lineage.
    """


def get_seat_ids_with_self_payments(class_id: str, window_start, window_end) -> set[int]:
    """Return seat ids with a self-originated obligation PAYMENT in ``[start, end)``.

    Read-only DOM-OBL-001 surface consumed by the Interpretation domain
    (SPEC-ITR-001 §6.2 third source): ``ObligationAssessment`` rows with
    ``event_type='PAYMENT'`` whose referenced Ledger row has ``mechanism=SELF``
    are the authoritative record of a student self-paying an obligation. The
    referenced-row provenance is checked by joining ``ledger_transaction_id`` to
    the Ledger; ``Transaction.type`` is never consulted (INV-ITR-015). Scoped by
    ``class_id`` and the half-open completed-cycle window.
    """
    if not class_id or window_start is None or window_end is None:
        return set()
    rows = (
        db.session.query(ObligationAssessment.seat_id)
        .join(Transaction, Transaction.id == ObligationAssessment.ledger_transaction_id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.event_type == "PAYMENT",
            ObligationAssessment.timestamp >= ensure_utc(window_start),
            ObligationAssessment.timestamp < ensure_utc(window_end),
            Transaction.mechanism == LedgerMechanism.SELF,
        )
        .distinct()
        .all()
    )
    return {row.seat_id for row in rows if row.seat_id is not None}


class ObligationEventRow(NamedTuple):
    """One obligation event, projected for Interpretation's Q3 read (SPEC-ITR-001 §8).

    A lightweight, read-only projection of an ``assessment_events`` row carrying
    exactly what Q3 is permitted to interpret. ``assessed_amount_cents`` is the
    canonical amount resolved from the upstream policy for ``ASSESSMENT`` events
    (``None`` for satisfaction events); ``ledger_amount_cents`` is the absolute
    magnitude of the referenced Ledger row for ``PAYMENT`` events (``None``
    otherwise). No Ledger ``type`` string is projected (INV-ITR-015).
    """

    correlation_id: str
    obligation_type: str
    event_type: str  # ASSESSMENT | PAYMENT | WAIVED
    timestamp: datetime
    ledger_transaction_id: int | None
    ledger_amount_cents: int | None
    assessed_amount_cents: int | None


def _to_cents(amount: Decimal | None) -> int | None:
    if amount is None:
        return None
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def get_obligation_events_for_window(
    class_id: str, window_start, window_end
) -> list[ObligationEventRow]:
    """Return the obligation events needed to interpret Q3 over ``[start, end)``.

    The obligation set for the window is the ``ASSESSMENT`` events whose
    ``timestamp`` falls in ``[window_start, window_end)`` (DOM-OBL-001 §VII: one
    ASSESSMENT per correlation). For those obligations, this also returns their
    ``PAYMENT``/``WAIVED`` satisfaction events with ``timestamp < window_end`` —
    the events that determine the obligation's *final status at window end*
    (SPEC-ITR-001 §8.4). Assessment amounts are resolved from the upstream policy
    (:func:`resolve_assessment_amount`); PAYMENT ledger magnitudes are read from
    the referenced ``Transaction`` row. Scoped by ``class_id`` (multi-tenancy).

    This is a pure DOM-OBL read (INV-ARC-007). Interpretation classifies the
    final per-obligation outcome from these facts; it does not itself decide
    satisfaction here.
    """
    if not class_id or window_start is None or window_end is None:
        return []
    start = ensure_utc(window_start)
    end = ensure_utc(window_end)

    assessments = (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.event_type == "ASSESSMENT",
            ObligationAssessment.timestamp >= start,
            ObligationAssessment.timestamp < end,
        )
        .all()
    )
    if not assessments:
        return []

    correlation_ids = {a.correlation_id for a in assessments}

    rows: list[ObligationEventRow] = [
        ObligationEventRow(
            correlation_id=a.correlation_id,
            obligation_type=a.obligation_type,
            event_type="ASSESSMENT",
            timestamp=a.timestamp,
            ledger_transaction_id=None,
            ledger_amount_cents=None,
            assessed_amount_cents=_to_cents(resolve_assessment_amount(a)),
        )
        for a in assessments
    ]

    satisfaction = (
        db.session.query(ObligationAssessment, Transaction.amount_cents)
        .outerjoin(Transaction, Transaction.id == ObligationAssessment.ledger_transaction_id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.correlation_id.in_(correlation_ids),
            ObligationAssessment.event_type.in_(["PAYMENT", "WAIVED"]),
            ObligationAssessment.timestamp < end,
        )
        .all()
    )
    for event, amount_cents in satisfaction:
        ledger_cents = None
        if event.event_type == "PAYMENT" and amount_cents is not None:
            ledger_cents = abs(int(amount_cents))
        rows.append(
            ObligationEventRow(
                correlation_id=event.correlation_id,
                obligation_type=event.obligation_type,
                event_type=event.event_type,
                timestamp=event.timestamp,
                ledger_transaction_id=event.ledger_transaction_id,
                ledger_amount_cents=ledger_cents,
                assessed_amount_cents=None,
            )
        )
    return rows


def resolve_assessment_amount(assessment: ObligationAssessment) -> Decimal:
    """Resolve the assessed amount for an assessment event.

    Per DOM-OBL-001 §V.1 and §VII.1, no amount is persisted on
    assessment_events. Amount comes from the upstream policy definition
    addressed by `assessment.policy_uuid`, dispatched by obligation_type.

    Returns Decimal('0.00') when the upstream policy row cannot be
    located (row deleted, policy_uuid unset, or unsupported type). This
    is safe for derived-satisfaction math: an unknown amount treated as
    zero produces `is_satisfied = True` for any non-negative payment,
    which is the same behavior as the pre-remediation stub.
    """
    if assessment is None:
        return Decimal('0.00')

    obligation_type = assessment.obligation_type
    policy_uuid = assessment.policy_uuid

    if obligation_type == 'RENT' and policy_uuid:
        from app.models import RentSettings
        rent = RentSettings.query.filter_by(policy_uuid=policy_uuid).first()
        if rent and rent.rent_amount is not None:
            return Decimal(str(rent.rent_amount))

    if obligation_type == 'LATE_FEE' and policy_uuid:
        # A LATE_FEE obligation is its own immutable liability that AROSE FROM a
        # delinquent RENT (lineage recorded on `source_correlation_id`). Its
        # amount is the rent policy's configured late penalty, NOT the rent
        # principal. The LATE_FEE assessment carries the same rent policy_uuid so
        # the penalty amount resolves from the same authoritative settings row.
        from app.models import RentSettings
        rent = RentSettings.query.filter_by(policy_uuid=policy_uuid).first()
        if rent and rent.late_penalty_amount is not None:
            return Decimal(str(rent.late_penalty_amount))

    if obligation_type == 'INSURANCE_PREMIUM' and policy_uuid:
        # The premium is the frozen per-period contract amount of the exact
        # policy version the assessment carries (DOM-POL-001 §VII, frozen by
        # reference; SPEC-ECON-003 §4.4.2). It does not scale with period length.
        from app.services.insurance_definition_service import get_insurance_definition
        policy = get_insurance_definition(policy_uuid, class_id=assessment.class_id)
        if policy is not None and policy.premium is not None:
            return Decimal(str(policy.premium))

    # IMMEDIATE / other types: their upstream contract lives in
    # domain-specific tables not yet centralized here. Callers that need a
    # non-zero amount for those types must resolve upstream and pass
    # explicitly.
    return Decimal('0.00')


def resolve_assessment_due_at(assessment: ObligationAssessment) -> datetime | None:
    """Resolve the "due at" boundary for an assessment event.

    Per DOM-OBL-001 §VII.2, temporal boundaries are owned by
    `bill_cycles`:

    - `bill_cycle.cycle_boundary_at` = the current cycle's own due date D —
      the moment this rent became due.
    - `bill_cycle.next_assessment_at` = pre-set scheduling for when the
      NEXT cycle's due boundary will fire. NOT the current cycle's due
      boundary; do not confuse.

    For cyclic obligations (rent), the due boundary is
    `bill_cycle.cycle_boundary_at`. For immediate charges (§II.C, no
    bill_cycle), the assessment is due at creation time — return the
    event's canonical `timestamp`.

    Returns None only if both bill_cycle lookup fails and no timestamp
    exists on the assessment (should not occur for lawful rows).
    """
    if assessment is None:
        return None

    if assessment.bill_cycle_id:
        cycle = db.session.get(BillCycle, assessment.bill_cycle_id)
        if cycle and cycle.cycle_boundary_at:
            return cycle.cycle_boundary_at

    # Immediate charge (or bill_cycle missing): due at assessment time.
    return assessment.timestamp


class ObligationStatusCode(str, enum.Enum):
    """Derived status of one assessed obligation (DOM-OBL-001 §VIII)."""
    OUTSTANDING = "OUTSTANDING"
    SATISFIED = "SATISFIED"


@dataclass(frozen=True)
class ObligationState:
    """The authoritative derived state of one assessed obligation (DOM-OBL-001 §VIII).

    This is the single derivation of paid / outstanding / waived for an
    obligation. Consumers read it (or a narrower read built on it); they do not
    recompute it from assessment events or Ledger rows (INV-ARC-009 §V).
    """
    correlation_id: str
    class_id: str
    seat_id: int
    obligation_type: str
    internal_ref: str
    bill_cycle_id: int | None
    assessed_amount: Decimal
    satisfied_amount: Decimal  # paid magnitude, excluding voided payments
    remaining_amount: Decimal  # zero unless OUTSTANDING
    is_waived: bool
    status: ObligationStatusCode
    due_at: datetime | None

    @property
    def is_satisfied(self) -> bool:
        return self.status is ObligationStatusCode.SATISFIED

    @property
    def is_outstanding(self) -> bool:
        return self.status is ObligationStatusCode.OUTSTANDING

    @property
    def is_payable(self) -> bool:
        return self.status is ObligationStatusCode.OUTSTANDING


def get_assessment_for_correlation(correlation_id: str) -> ObligationAssessment | None:
    """
    Retrieve the original ASSESSMENT event for a correlation.

    Per DOM-OBL-001 §VII: exactly one ASSESSMENT per correlation_id.
    """
    return (
        db.session.query(ObligationAssessment)
        .filter_by(correlation_id=correlation_id, event_type='ASSESSMENT')
        .first()
    )


def get_obligations_arising_from(source_correlation_id: str) -> list[ObligationAssessment]:
    """Retrieve ASSESSMENT events that AROSE FROM a source obligation.

    Uses the lawful, persisted ``source_correlation_id`` reference — never a
    parsed correlation string. Canonically: the LATE_FEE obligations charged
    against a delinquent RENT share that rent's correlation as their source, so
    this returns a bill's late fees given the rent correlation. Ordered by
    assessment time (oldest first) for stable, chronological settlement/display.
    """
    if not source_correlation_id:
        return []
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.source_correlation_id == source_correlation_id,
            ObligationAssessment.event_type == 'ASSESSMENT',
        )
        .order_by(ObligationAssessment.timestamp.asc(), ObligationAssessment.id.asc())
        .all()
    )


def get_satisfaction_events(correlation_id: str) -> list[ObligationAssessment]:
    """Retrieve all PAYMENT and WAIVED events for a correlation (in order)."""
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.correlation_id == correlation_id,
            ObligationAssessment.event_type.in_(['PAYMENT', 'WAIVED'])
        )
        .order_by(ObligationAssessment.timestamp.asc())
        .all()
    )


def payment_event_magnitude(event: ObligationAssessment) -> Decimal:
    """The amount one PAYMENT event applied: its Ledger magnitude, or zero if voided."""
    if event.event_type != "PAYMENT" or not event.ledger_transaction_id:
        return Decimal("0.00")
    txn = db.session.get(Transaction, event.ledger_transaction_id)
    if txn is None or txn.amount is None or txn.status == TransactionStatus.VOID:
        return Decimal("0.00")
    return abs(Decimal(str(txn.amount)))


def get_paid_magnitude(correlation_id: str) -> Decimal:
    """Canonical paid amount for an obligation: sum of PAYMENT ledger MAGNITUDES.

    Per DOM-OBL-001 §VIII, paid = sum of the authoritative Ledger amounts from
    PAYMENT events sharing this correlation. Rent payments are posted as NEGATIVE
    debits, so the magnitude (abs) is applied toward the obligation. Multiple
    PAYMENT events (partial payments) accumulate here under one correlation.
    A voided payment applies nothing: its money was reversed.
    """
    return sum(
        (payment_event_magnitude(event) for event in get_satisfaction_events(correlation_id)),
        Decimal("0.00"),
    )


def get_paid_magnitude_through_event(
    correlation_id: str, boundary_event: ObligationAssessment
) -> Decimal:
    """Sum PAYMENT magnitudes through one immutable satisfaction event."""
    total = Decimal('0.00')
    for event in get_satisfaction_events(correlation_id):
        if event.event_type == 'PAYMENT' and (
            event.timestamp < boundary_event.timestamp
            or (event.timestamp == boundary_event.timestamp and event.id <= boundary_event.id)
        ) and event.ledger_transaction_id:
            from app.models import Transaction
            txn = db.session.get(Transaction, event.ledger_transaction_id)
            if txn is not None and txn.amount is not None:
                total += abs(Decimal(str(txn.amount)))
    return total


def get_payment_event_by_ledger(
    ledger_transaction_id: int | None,
) -> ObligationAssessment | None:
    """Return the PAYMENT event referencing a specific ledger transaction, if any.

    A PAYMENT's replay identity is the ledger transaction it settles (the payment
    command's owned, idempotent ledger write). Deduping on this — rather than on
    "any PAYMENT exists for the correlation" — is what allows multiple lawful
    partial payments to coexist under one obligation while each individual payment
    command remains replay-safe.
    """
    if ledger_transaction_id is None:
        return None
    return (
        db.session.query(ObligationAssessment)
        .filter_by(
            ledger_transaction_id=ledger_transaction_id,
            event_type='PAYMENT',
        )
        .first()
    )


def get_obligation_state(
    correlation_id: str,
    *,
    as_of: datetime | None = None,
) -> ObligationState | None:
    """Derive the authoritative state of one obligation (DOM-OBL-001 §VIII).

    ``as_of`` limits the satisfaction facts to those recorded at or before it;
    omitted, every recorded fact counts. Voided payments never count.
    """
    assessment = get_assessment_for_correlation(correlation_id)
    if assessment is None:
        return None

    satisfied_amount = Decimal("0.00")
    is_waived = False
    cutoff = ensure_utc(as_of) if as_of is not None else None
    for event in get_satisfaction_events(correlation_id):
        if cutoff is not None and ensure_utc(event.timestamp) > cutoff:
            continue
        if event.event_type == "PAYMENT":
            satisfied_amount += payment_event_magnitude(event)
        elif event.event_type == "WAIVED":
            is_waived = True

    assessed_amount = resolve_assessment_amount(assessment)
    if is_waived or satisfied_amount >= assessed_amount:
        status = ObligationStatusCode.SATISFIED
        remaining = Decimal("0.00")
    else:
        status = ObligationStatusCode.OUTSTANDING
        remaining = assessed_amount - satisfied_amount

    return ObligationState(
        correlation_id=correlation_id,
        class_id=assessment.class_id,
        seat_id=assessment.seat_id,
        obligation_type=assessment.obligation_type,
        internal_ref=assessment.internal_ref,
        bill_cycle_id=assessment.bill_cycle_id,
        assessed_amount=assessed_amount,
        satisfied_amount=satisfied_amount,
        remaining_amount=remaining,
        is_waived=is_waived,
        status=status,
        due_at=resolve_assessment_due_at(assessment),
    )


def is_obligation_past_due(
    state: ObligationState,
    *,
    reference_time_utc: datetime | None = None,
) -> bool:
    """Past due = OUTSTANDING and the reference time is after ``due_at``.

    "After" is evaluated through the canonical temporal resolver in the class's
    authority (INV-ARC-015 §VII), never against a database or process clock.
    """
    if not state.is_outstanding or state.due_at is None:
        return False
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=state.class_id),
        primitive="later_than",
        reference_time_utc=reference_time_utc,
        candidate=_current_reference(state.class_id, reference_time_utc),
        reference=state.due_at,
    ).is_later


def _current_reference(class_id: str, reference_time_utc: datetime | None) -> datetime:
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc


def get_assessment_events_for_seat_class(
    seat_id: int,
    class_id: str,
    obligation_type: str | None = None,
) -> list[ObligationAssessment]:
    """
    Retrieve all assessment events for a seat in a class.

    Optionally filter by obligation_type (RENT, INSURANCE_PREMIUM).
    Returns in creation order (immutable append-only facts).
    """
    query = (
        db.session.query(ObligationAssessment)
        .filter_by(seat_id=seat_id, class_id=class_id)
    )
    if obligation_type:
        query = query.filter_by(obligation_type=obligation_type)

    return query.order_by(ObligationAssessment.timestamp.asc()).all()


def get_bill_cycles_for_internal_ref(internal_ref: str) -> list[BillCycle]:
    """
    Retrieve all bill cycles for an internal reference.

    Per DOM-OBL-001 §VII.3: identity-blind temporal reminder state.
    Returns in cycle number order.
    """
    return (
        db.session.query(BillCycle)
        .filter_by(internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def get_latest_bill_cycle(internal_ref: str) -> BillCycle | None:
    """Get the most recent cycle for an internal reference."""
    return (
        db.session.query(BillCycle)
        .filter_by(internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.desc())
        .first()
    )


def check_idempotency_assessment(
    internal_ref: str,
    correlation_id: str,
) -> bool:
    """
    Check if an assessment already exists for this lineage.

    Per FEAT-OBLI-001: assessment must be idempotent by (internal_ref, correlation_id).
    Returns True if already exists.
    """
    existing = (
        db.session.query(ObligationAssessment)
        .filter_by(
            internal_ref=internal_ref,
            correlation_id=correlation_id,
            event_type='ASSESSMENT',
        )
        .first()
    )
    return existing is not None


def check_idempotency_satisfaction(
    correlation_id: str,
    method: str,  # 'PAYMENT' or 'WAIVED'
) -> bool:
    """
    Check if a satisfaction of this type already exists.

    Per FEAT-OBL-003: satisfaction must be idempotent by (correlation_id, method).
    Returns True if already exists.
    """
    existing = (
        db.session.query(ObligationAssessment)
        .filter_by(
            correlation_id=correlation_id,
            event_type=method,
        )
        .first()
    )
    return existing is not None


class SuccessionEligibility(enum.Enum):
    """Succession eligibility of a bill-cycle lineage (DOM-OBL-001 §V.7)."""
    EMPTY = "EMPTY"  # no cycle yet: succession creates cycle 1
    DUE = "DUE"  # non-terminal latest cycle whose next_assessment_at has arrived
    NOT_DUE = "NOT_DUE"  # non-terminal latest cycle, next_assessment_at still ahead
    TERMINAL = "TERMINAL"  # latest cycle is terminal: succession is unlawful


def get_succession_eligibility(
    class_id: str,
    internal_ref: str,
    *,
    reference_time_utc: datetime | None = None,
) -> tuple[SuccessionEligibility, BillCycle | None]:
    """Whether a lineage may lawfully be succeeded at the reference time.

    The single authoritative answer, used by ``schedule_next_bill_cycle`` itself
    and by any caller that needs to know before asking (INV-ARC-009 §V: callers
    do not reconstruct domain eligibility). "Arrived" is evaluated through the
    canonical temporal resolver (INV-ARC-015 §VII). Returns the latest cycle read,
    so the caller derives from the same state it evaluated.
    """
    latest = (
        db.session.query(BillCycle)
        .filter_by(class_id=class_id, internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.desc())
        .first()
    )
    if latest is None:
        return SuccessionEligibility.EMPTY, None
    if latest.next_assessment_at is None:
        return SuccessionEligibility.TERMINAL, latest
    ctx = SimpleNamespace(class_id=class_id)
    reference = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc
    not_yet = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="later_than",
        reference_time_utc=reference,
        candidate=latest.next_assessment_at,
        reference=reference,
    ).is_later
    return (SuccessionEligibility.NOT_DUE if not_yet else SuccessionEligibility.DUE), latest


def get_obligation_command_reservation(
    class_id: str,
    command_name: str,
    idempotency_key: str,
) -> ObligationCommandReservation | None:
    """Look up a recorded Obligations command by its identity (DOM-OBL-001 §V.7).

    Replay is decided by command identity, never by whether a bill-cycle row of
    a given shape exists.
    """
    return (
        db.session.query(ObligationCommandReservation)
        .filter_by(
            class_id=class_id,
            command_name=command_name,
            idempotency_key=idempotency_key,
        )
        .one_or_none()
    )


# ---- Rent-specific read models (domain-aware projections) ----


def get_assessments_for_bill_cycle(
    bill_cycle_id: int,
    obligation_type: str | None = None,
) -> list[ObligationAssessment]:
    """
    Retrieve ASSESSMENT events linked to a specific bill cycle.

    Per DOM-OBL-001 v2.5: bill_cycles define periods; assessments link via bill_cycle_id FK.
    This is the canonical way to find assessments for a coverage period.

    Args:
        bill_cycle_id: The bill cycle ID
        obligation_type: Optional filter for obligation type (RENT, INSURANCE_PREMIUM, etc.)

    Returns:
        List of ASSESSMENT events (not PAYMENT or WAIVED events)
    """
    query = (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.bill_cycle_id == bill_cycle_id,
            ObligationAssessment.event_type == 'ASSESSMENT',
        )
    )

    if obligation_type:
        query = query.filter(ObligationAssessment.obligation_type == obligation_type)

    return query.order_by(ObligationAssessment.timestamp.asc()).all()


def get_paid_rent_assessments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Return PAID RENT ASSESSMENT events for a coverage cycle.

    Canonical semantics (DOM-OBL-001 §VII/§VIII): obligations are event-sourced
    and identity-blind by type. A RENT ASSESSMENT is *paid* iff it has at least
    one PAYMENT satisfaction event sharing its correlation_id. The coverage cycle
    is resolved via bill_cycles whose cycle_boundary_at falls in the requested
    (coverage_month, coverage_year), scoped to the class for multi-tenancy.

    Note: this replaces a removed pre-v2.5 helper that was a thin alias returning
    *all* rent assessments regardless of payment. The canonical "paid" filter
    (payment evidence) is applied here so callers observing "has paid rent" get
    the meaning the name promises.

    Args:
        class_id: Class scope (multi-tenancy boundary).
        coverage_month: Calendar month the cycle covers (1-12).
        coverage_year: Calendar year the cycle covers.
        seat_ids: Optional restriction to specific seats.

    Returns:
        List of paid RENT ASSESSMENT events (each exposes .seat, .id,
        .correlation_id), in assessment-timestamp order.
    """
    from sqlalchemy import extract

    matching_bill_cycle_ids = [
        row[0]
        for row in (
            db.session.query(BillCycle.id)
            .filter(
                BillCycle.class_id == class_id,
                extract('month', BillCycle.cycle_boundary_at) == coverage_month,
                extract('year', BillCycle.cycle_boundary_at) == coverage_year,
            )
            .all()
        )
    ]
    if not matching_bill_cycle_ids:
        return []

    query = (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'ASSESSMENT',
            ObligationAssessment.bill_cycle_id.in_(matching_bill_cycle_ids),
        )
    )
    if seat_ids:
        query = query.filter(ObligationAssessment.seat_id.in_(seat_ids))

    assessments = query.order_by(ObligationAssessment.timestamp.asc()).all()

    # Canonical paid-filter: keep only assessments with a PAYMENT satisfaction event.
    return [
        assessment
        for assessment in assessments
        if any(
            event.event_type == 'PAYMENT'
            for event in get_satisfaction_events(assessment.correlation_id)
        )
    ]


def is_obligation_related_transaction(transaction_id: int | None) -> bool:
    """Return True iff a ledger transaction has obligation provenance.

    Per SPEC-OPS-001 §VII (INV-OPS-008), obligation-relatedness is determined by
    *provenance*, not representation: a monetary transaction is obligation-related
    iff an obligation event (assessment_events) references it via
    ``ledger_transaction_id``. Such transactions are neither voidable nor
    reversible; monetary remediation must be a new, independently authorized
    adjustment (INV-OPS-009).

    Args:
        transaction_id: Ledger transaction id to test (None → False).

    Returns:
        True if any obligation event references this transaction, else False.
    """
    if transaction_id is None:
        return False
    return (
        db.session.query(ObligationAssessment.id)
        .filter(ObligationAssessment.ledger_transaction_id == transaction_id)
        .first()
        is not None
    )


def get_payment_events_for_assessment(
    assessment_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """
    Retrieve all PAYMENT events for an assessment.

    Per DOM-OBL-001 §VII.1: multiple PAYMENT rows may exist per assessment.
    Returns in creation order.
    """
    assessment = db.session.get(ObligationAssessment, assessment_id)
    if not assessment:
        return []

    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.correlation_id == assessment.correlation_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.event_type == 'PAYMENT',
        )
        .order_by(ObligationAssessment.timestamp.asc())
        .all()
    )




def get_waived_seats_for_bill_cycle(
    bill_cycle_id: int,
) -> set[int]:
    """
    Retrieve seat IDs where obligations were waived for a specific bill cycle.

    Per DOM-OBL-001 v2.5: WAIVED events link to bill_cycles via bill_cycle_id.
    Returns set of seat IDs that have WAIVED events for this cycle.
    """
    query = (
        db.session.query(ObligationAssessment.seat_id.distinct())
        .filter(
            ObligationAssessment.bill_cycle_id == bill_cycle_id,
            ObligationAssessment.event_type == 'WAIVED',
        )
    )

    return set(row[0] for row in query.all())


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    limit: int = 24,
) -> list[ObligationAssessment]:
    """
    Retrieve rent-related assessment events (ASSESSMENT, PAYMENT, WAIVED)
    for a seat in reverse chronological order.

    Used for displaying payment history in student rent view.
    Limits to most recent N events.
    """
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
        )
        .order_by(ObligationAssessment.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_rent_waivers_for_seat(
    seat_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Retrieve all active rent waivers for a seat in a class."""
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'WAIVED',
        )
        .order_by(ObligationAssessment.timestamp.desc())
        .all()
    )


@dataclass(frozen=True)
class RentWaiverView:
    """Derived projection of a rent WAIVED event with its coverage window.

    Per DOM-OBL-001 §VII, assessment events do not store coverage windows.
    The window is derived from the linked bill_cycle
    (cycle_boundary_at, next_assessment_at). This projection resolves the
    derivation once so callers work with a stable shape.
    """
    id: int
    seat_id: int
    correlation_id: str
    timestamp: datetime  # When the waiver was granted (event canonical timestamp)
    coverage_start_time: Optional[datetime]  # Derived from bill_cycle.cycle_boundary_at
    coverage_end_time: Optional[datetime]  # Derived from bill_cycle.next_assessment_at


def get_active_rent_waivers_for_class(
    class_id: str,
    coverage_date: datetime | None = None,
) -> list[RentWaiverView]:
    """DEPRECATED — "active waiver" is not a lawful concept.

    Per DOM-OBL-001 §V.6, a waiver is a one-time immutable satisfaction
    of a specific already-assessed liability. It does not create an
    ongoing state and does not affect later assessments. Any UI that
    presents waivers as "currently active" or as a lifecycle object
    encodes the wrong domain semantics.

    This helper is retained temporarily so existing callers do not
    crash; it returns the WAIVED-event history with the actual bill-cycle
    coverage bounds. New callers should use `get_rent_waiver_history_for_class`
    directly.

    TODO: remove after all callers migrate.
    """
    waivers = get_rent_waiver_history_for_class(class_id)
    if coverage_date is not None:
        waivers = [
            w for w in waivers
            if w['coverage_start_time'] and w['coverage_end_time']
            and w['coverage_start_time'] <= coverage_date < w['coverage_end_time']
        ]
    return [
        RentWaiverView(
            id=w['id'],
            seat_id=w['seat_id'],
            correlation_id=w['correlation_id'],
            timestamp=w['waived_at'],
            coverage_start_time=w['coverage_start_time'],
            coverage_end_time=w['coverage_end_time'],
        )
        for w in waivers
    ]


def get_rent_waiver_history_for_class(
    class_id: str,
    limit: int = 100,
) -> list[dict]:
    """Read-only audit list of rent waiver events for a class.

    Per DOM-OBL-001 §V.6 a waiver is an immutable satisfaction of one
    specific assessment. This helper returns that history in reverse
    chronological order (most recent waiver first) so the teacher-facing
    UI can present it as an audit log, not as active state.

    Each row:

        {
            'id': int,                      # WAIVED event id
            'correlation_id': str,          # links back to assessment
            'seat_id': int,
            'waived_at': datetime,          # WAIVED event timestamp
            'due_at': datetime | None,      # from linked bill_cycle
                                            # (assessment_at); None for
                                            # immediate charges
            'notes': str | None,            # teacher-entered reason
                                            # (DOM-OBL-001 §VII.1 notes)
        }

    Downstream renderers may resolve seat_id → student_name and
    correlation_id → assessed_amount via their own view models; those
    are presentation concerns and not persisted on the WAIVED event
    per §VII.1 ("no amount is persisted here").
    """
    from app.models import ObligationAssessment, BillCycle

    q = (
        db.session.query(ObligationAssessment, BillCycle)
        .outerjoin(BillCycle, ObligationAssessment.bill_cycle_id == BillCycle.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'WAIVED',
        )
        .order_by(ObligationAssessment.timestamp.desc())
        .limit(limit)
    )
    return [
        {
            'id': waiver.id,
            'correlation_id': waiver.correlation_id,
            'seat_id': waiver.seat_id,
            'waived_at': waiver.timestamp,
            'due_at': cycle.cycle_boundary_at if cycle else None,
            'coverage_start_time': cycle.cycle_boundary_at if cycle else None,
            'coverage_end_time': cycle.next_assessment_at if cycle else None,
            'notes': waiver.notes,
        }
        for waiver, cycle in q.all()
    ]


def get_cycle_rent_amount(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> float | None:
    """
    STUB: Get rent amount for a cycle.

    This function DOES NOT BELONG in Obligations domain (violates DOM-OBL-001).
    Rent amount is Class Configuration authority, not Obligations authority.

    Obligations domain stores assessment amounts in policy_version_id references
    to the upstream PolicyVersion, not in obligation tables.

    Caller should fetch amount from Class Configuration, pass to assessment creator.

    TODO: Remove this function. Rent amount should be determined upstream by
    Class Configuration and passed to FEAT-OBLI-001 via correlation/policy_version_id.
    """
    return None
