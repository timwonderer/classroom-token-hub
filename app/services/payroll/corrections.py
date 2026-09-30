"""One-time payroll corrections for platform defects (incident PROD-PAY-001).

Before the closed-session rule (DOM-PROD-001 §VI.3), a payroll run loaded only
the attendance rows after the seat's previous payroll, so a session still running
at that payroll lost its clock-in and the rest of it went unpaid. This module
reproduces, for each run settled by that earlier rule, what the run paid and what
the time worked inside its window came to, and proposes the difference.

Authority stays with the class (the incident's recorded decision): this module
only computes. Nothing is posted until a teacher who owns the class approves.
Each correction is then a ``manual_credit`` whose actor is the approving
teacher's seat and whose mechanism is ``SYSTEM``, because the platform computed
the amount; ``SYSTEM`` confers no authority to post.

Reads are pure (INV-ARC-007). Amounts are recomputed at approval; a client never
supplies one.

Each earlier-rule run is priced at the payroll setting that was in force when it
ran — the rate that run actually paid at — resolved through the one
payroll-settings resolver (DOM-PROD-001 §XV.3). The correction's provenance is
the setting that priced its latest corrected run.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.models import AttendanceSession, PayrollEvent, Seat, Transaction
from app.services.attendance_service import (
    CLOSED_SESSION_SETTLEMENT_RULE,
    _day_end_utc,
    _split_sessions,
)
from app.services.context_resolver import CanonicalContext
from app.services.payroll.settings import pay_rate_per_second, payroll_setting_governing_work
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
    utc_now,
)

CENT = Decimal("0.01")


@dataclass(frozen=True)
class PayrollIncident:
    incident_id: str
    ledger_description: str
    expires_at: datetime
    expires_on_label: str


PROD_PAY_001 = PayrollIncident(
    incident_id="PROD-PAY-001",
    ledger_description="Payroll correction: unpaid work time from Sep 28 (system-calculated)",
    # End of Oct 31, 2026 in Pacific time, about 30 days after the tool ships.
    expires_at=datetime(2026, 11, 1, 7, 0, tzinfo=timezone.utc),
    expires_on_label="October 31, 2026",
)

PROPOSED = "proposed"
CORRECTED = "corrected"
NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class SeatCorrection:
    seat_id: int
    student_name: str
    unpaid_seconds: int
    amount: Decimal
    status: str
    corrected_event_ids: tuple[int, ...]
    corrected_at: datetime | None = None


@dataclass(frozen=True)
class ClassCorrectionProposal:
    incident: PayrollIncident
    class_id: str
    rows: tuple[SeatCorrection, ...]

    @property
    def proposed(self) -> tuple[SeatCorrection, ...]:
        return tuple(row for row in self.rows if row.status == PROPOSED)

    @property
    def proposed_total(self) -> Decimal:
        return sum((row.amount for row in self.proposed), Decimal("0.00"))


def correction_key(incident: PayrollIncident, class_id: str, seat_id: int) -> str:
    """Deterministic per-student key: the correction is at most one event."""
    return f"payroll-correction:{incident.incident_id}:{class_id}:{seat_id}"


def correction_correlation_id(key: str) -> str:
    """Deterministic correlation id for a correction key.

    It is part of the payroll-event replay guard, so it must repeat for the same
    student; a UUIDv5 of the key does, and fits the audit trail's 64 characters.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def incident_is_open(incident: PayrollIncident, *, now_utc=None) -> bool:
    return ensure_utc(now_utc or utc_now()) < incident.expires_at


def _elapsed_seconds(ctx, intervals, reference_time_utc) -> int:
    if not intervals:
        return 0
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="elapsed_duration",
        reference_time_utc=reference_time_utc,
        intervals=intervals,
    ).elapsed_seconds


def _replayed_paid_seconds(ctx, rows, *, since_utc, run_at_utc) -> int:
    """What the earlier rule computed for a run at ``run_at_utc``, reproduced exactly.

    It kept only rows at or after the seat's previous payroll, restarted on every
    ``active`` row, and extended a still-open session to the run.
    """
    intervals = []
    active_start = None
    for row in rows:
        ts = ensure_utc(row.timestamp)
        if ts > run_at_utc:
            break
        if since_utc is not None and ts < since_utc:
            continue
        if row.status == "active":
            active_start = ts
        elif row.status == "inactive" and active_start is not None:
            intervals.append((active_start, min(ts, _day_end_utc(ctx, active_start))))
            active_start = None
    if active_start is not None:
        intervals.append((active_start, min(run_at_utc, _day_end_utc(ctx, active_start))))
    return _elapsed_seconds(ctx, intervals, run_at_utc)


def _worked_seconds_in_window(ctx, rows, *, since_utc, run_at_utc) -> int:
    """Time actually worked inside ``(since_utc, run_at_utc]``.

    Sessions are paired by the current rule (a repeated ``active`` continues the
    session; a session ends at the end of its class day) and clipped to the window.
    """
    closed, in_progress = _split_sessions(rows, ctx=ctx, as_of_utc=run_at_utc)
    sessions = closed + ([in_progress] if in_progress else [])
    intervals = []
    for start, end in sessions:
        if since_utc is not None and start < since_utc:
            start = since_utc
        if end > start:
            intervals.append((start, end))
    return _elapsed_seconds(ctx, intervals, run_at_utc)


def _is_legacy(event: PayrollEvent) -> bool:
    return (event.summary_json or {}).get("settlement_rule") != CLOSED_SESSION_SETTLEMENT_RULE


def _student_name(seat: Seat) -> str:
    profile = getattr(seat, "identity_profile", None)
    return (profile.full_name if profile else None) or f"Seat {seat.id}"


def build_class_correction_proposal(
    class_id: str, *, incident: PayrollIncident = PROD_PAY_001
) -> ClassCorrectionProposal:
    """Propose each student's correction for one class. Pure read."""
    if not class_id:
        raise ValueError("build_class_correction_proposal requires class_id.")
    # Class-scoped temporal context only; this read acts for no one.
    ctx = SimpleNamespace(class_id=class_id)

    seats = (
        Seat.query.filter(
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
        )
        .order_by(Seat.id.asc())
        .all()
    )
    rows: list[SeatCorrection] = []
    for seat in seats:
        existing = PayrollEvent.query.filter_by(
            class_id=class_id,
            target_seat_id=seat.id,
            payroll_event_type="manual_credit",
            idempotency_key=correction_key(incident, class_id, seat.id),
        ).first()
        events = (
            PayrollEvent.query.filter_by(
                class_id=class_id, target_seat_id=seat.id, payroll_event_type="payroll"
            )
            .order_by(PayrollEvent.recorded_at.asc(), PayrollEvent.id.asc())
            .all()
        )
        if existing is not None:
            summary = existing.summary_json or {}
            rows.append(SeatCorrection(
                seat_id=seat.id,
                student_name=_student_name(seat),
                unpaid_seconds=int(summary.get("unpaid_seconds", 0)),
                amount=Decimal(str(summary.get("amount", "0.00"))),
                status=CORRECTED,
                corrected_event_ids=tuple(summary.get("corrected_payroll_event_ids", ())),
                corrected_at=ensure_utc(existing.recorded_at),
            ))
            continue
        if not any(_is_legacy(event) for event in events):
            continue

        attendance = (
            AttendanceSession.query.filter(
                AttendanceSession.target_seat_id == seat.id,
                AttendanceSession.class_id == class_id,
            )
            .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
            .all()
        )
        unpaid_seconds = 0
        amount = Decimal("0.00")
        corrected: list[int] = []
        consistent = True
        previous_at = None
        for event in events:
            run_at = ensure_utc(event.recorded_at)
            if _is_legacy(event):
                # The earlier rule priced a run at the setting in force when it
                # ran, so that setting reproduces what it paid.
                rate = pay_rate_per_second(payroll_setting_governing_work(class_id, run_at))
                paid_seconds = _replayed_paid_seconds(
                    ctx, attendance, since_utc=previous_at, run_at_utc=run_at
                )
                worked_seconds = _worked_seconds_in_window(
                    ctx, attendance, since_utc=previous_at, run_at_utc=run_at
                )
                paid_amount = (Decimal(paid_seconds) * rate).quantize(CENT)
                ledger = Transaction.query.filter_by(
                    class_id=class_id,
                    seat_id=seat.id,
                    type="payroll",
                    idempotency_key=event.idempotency_key,
                ).first()
                ledger_amount = (
                    Decimal(str(ledger.amount)).quantize(CENT) if ledger else Decimal("0.00")
                )
                # The replay must reproduce what was actually paid. A mismatch
                # (a changed rate, a backdated row) means the proposal cannot be
                # trusted, so the student is left for the teacher to review.
                if ledger_amount != paid_amount:
                    consistent = False
                owed = (Decimal(worked_seconds) * rate).quantize(CENT) - paid_amount
                if worked_seconds > paid_seconds and owed > 0:
                    unpaid_seconds += worked_seconds - paid_seconds
                    amount += owed
                    corrected.append(event.id)
            previous_at = run_at

        if not consistent:
            rows.append(SeatCorrection(
                seat_id=seat.id,
                student_name=_student_name(seat),
                unpaid_seconds=unpaid_seconds,
                amount=amount,
                status=NEEDS_REVIEW,
                corrected_event_ids=tuple(corrected),
            ))
        elif amount > 0:
            rows.append(SeatCorrection(
                seat_id=seat.id,
                student_name=_student_name(seat),
                unpaid_seconds=unpaid_seconds,
                amount=amount,
                status=PROPOSED,
                corrected_event_ids=tuple(corrected),
            ))

    return ClassCorrectionProposal(incident=incident, class_id=class_id, rows=tuple(rows))


# The banner check replays the whole proposal, which is too costly to repeat on
# every dashboard and payroll view. Its inputs are frozen (earlier-rule events,
# their ledger rows, append-only attendance) except the corrections themselves, so
# the result is cached under the class's correction count: an approval changes the
# count and every worker recomputes. The TTL bounds anything else, such as a
# changed pay rate.
_PENDING_TTL_SECONDS = 300
_pending_cache: dict[tuple[str, str, int], tuple[float, bool]] = {}


def class_has_pending_correction(class_id: str, *, incident: PayrollIncident = PROD_PAY_001) -> bool:
    """Whether the class still has a correction awaiting its teacher. Pure read."""
    if not class_id or not incident_is_open(incident):
        return False
    legacy_exists = any(
        _is_legacy(event)
        for event in PayrollEvent.query.with_entities(PayrollEvent.summary_json).filter_by(
            class_id=class_id, payroll_event_type="payroll"
        ).all()
    )
    if not legacy_exists:
        return False
    corrections = PayrollEvent.query.filter(
        PayrollEvent.class_id == class_id,
        PayrollEvent.payroll_event_type == "manual_credit",
        PayrollEvent.idempotency_key.like(f"payroll-correction:{incident.incident_id}:{class_id}:%"),
    ).count()
    key = (incident.incident_id, class_id, corrections)
    now = time.monotonic()
    cached = _pending_cache.get(key)
    if cached is not None and now - cached[0] < _PENDING_TTL_SECONDS:
        return cached[1]
    pending = bool(build_class_correction_proposal(class_id, incident=incident).proposed)
    _pending_cache[key] = (now, pending)
    return pending


@dataclass(frozen=True)
class CorrectionPosting:
    """One approved correction, ready for FEAT-PROD-003 to post as a manual credit."""

    seat_id: int
    amount: Decimal
    idempotency_key: str
    correlation_id: str
    policy_uuid: str | None
    summary_json: dict


def plan_class_corrections(
    *,
    ctx: CanonicalContext,
    seat_ids: set[int],
    incident: PayrollIncident = PROD_PAY_001,
) -> list[CorrectionPosting]:
    """The corrections to post for the teacher's approval. Pure read.

    Recomputes the proposal; only seats it still proposes are included, at the
    amount it computes now. The caller posts each through FEAT-PROD-003; this
    service never writes (INV-ARC-021: services do not invoke FEATs).
    """
    if not incident_is_open(incident):
        raise ValueError(f"Incident {incident.incident_id} is closed.")
    class_id = ctx.class_id
    proposal = build_class_correction_proposal(class_id, incident=incident)
    corrected_run_times = {
        event.id: ensure_utc(event.recorded_at)
        for event in PayrollEvent.query.filter_by(class_id=class_id, payroll_event_type="payroll").all()
    }
    postings: list[CorrectionPosting] = []
    for row in proposal.proposed:
        if row.seat_id not in seat_ids:
            continue
        key = correction_key(incident, class_id, row.seat_id)
        latest_run = max(
            (corrected_run_times[event_id] for event_id in row.corrected_event_ids if event_id in corrected_run_times),
            default=None,
        )
        setting = payroll_setting_governing_work(class_id, latest_run) if latest_run else None
        postings.append(CorrectionPosting(
            seat_id=row.seat_id,
            amount=row.amount,
            idempotency_key=key,
            correlation_id=correction_correlation_id(key),
            policy_uuid=setting.policy_uuid if setting else None,
            summary_json={
                "source": "payroll_correction",
                "incident": incident.incident_id,
                "description": incident.ledger_description,
                "unpaid_seconds": row.unpaid_seconds,
                "amount": str(row.amount),
                "corrected_payroll_event_ids": list(row.corrected_event_ids),
                "approved_by_seat_id": ctx.seat_id,
            },
        ))
    return postings
