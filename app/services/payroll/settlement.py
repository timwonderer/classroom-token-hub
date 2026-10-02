"""Class-wide payroll-cycle settlement (DOM-PROD-001 §XV, slice 8.3b).

Owns exactly one thing: given a ``class_id``, a ``payroll_cycle_id``, and a lawful
resolved cycle boundary, settle the entire eligible class — each session priced by the payroll setting
in force when it closed (DOM-PROD-001 §XV.3) — stamping the same
``payroll_cycle_id`` and the run's mechanism on every payroll event produced.

    enumerate eligible seats (attendance-derived, PROD doctrine)
        -> derive each seat's pay window/facts (the per-seat primitive)
        -> invoke record_payroll_event (payroll_event_type="payroll")
        -> stamp the shared payroll_cycle_id on every event
        -> NO COMMIT

It is deliberately ignorant of ITR, CLASS policy activation, and the
completion/replay anchor — those are composed by the FEAT-PROD-004 orchestrator in
a later slice. It emits only ``payroll`` events; it never manufactures
``manual_credit`` or ``reversal`` events, so teacher credits and reversals never
become cycle-boundary events. It ``add``/``flush``es within the caller's FEAT
transaction and never commits, so a single per-seat failure lets the caller roll
the entire transaction back.
"""

from __future__ import annotations

from typing import NamedTuple

from app.extensions import db
from app.feats.base import get_correlation_id
from app.feats.prod import _record_payroll_event_impl as record_payroll_event_command
from app.models import (
    AttendanceSession,
    ClassEconomy,
    PayrollEvent,
    Seat,
)
from app.services.attendance_service import calculate_payable_attendance_seconds
from app.services.context_resolver import CanonicalContext
from app.services.identity_service import resolve_teacher_seat_for_class
from app.services.payroll.schedule import SCHEDULED_OCCURRENCE_KEY
from app.services.payroll.settings import class_has_payroll_settings
from app.utils.canonical_temporal_resolver import ensure_utc

# FEAT-PROD-004 §II.1: which path started the run. SYSTEM is the automatic
# schedule, TEACHER the teacher's own run. Only SYSTEM runs anchor the next
# payroll date (DOM-PROD-001 §XV.5), so the caller must say which it is.
RUN_MECHANISMS = frozenset({"TEACHER", "SYSTEM"})


class ClassSettlementError(Exception):
    """Raised when class-wide settlement cannot proceed lawfully (e.g. no active
    payroll policy, or no resolvable teacher actor for the class)."""


class NoPayableAttendanceError(ClassSettlementError):
    """Raised when no seat in the class has a closed, unpaid session.

    A payroll run settles closed work only (DOM-PROD-001 §VI.3), so a run with
    nothing closed and unpaid has nothing to settle and is refused rather than
    recorded as an empty cycle. Students still working are paid by the first run
    after they clock out.
    """


class ClassSettlementResult(NamedTuple):
    payroll_cycle_id: str
    settled_seat_ids: list[int]      # seats that received a fresh payroll event this call
    skipped_seat_ids: list[int]      # seats already settled for this cycle (idempotent)
    events: list[PayrollEvent]


def _build_teacher_context(class_id: str) -> CanonicalContext:
    class_row = db.session.get(ClassEconomy, class_id)
    if class_row is None or not class_row.teacher_user_id:
        raise ClassSettlementError(f"Class {class_id} has no resolvable teacher actor.")
    try:
        teacher_seat = resolve_teacher_seat_for_class(class_id)
    except ValueError as exc:
        raise ClassSettlementError(str(exc)) from exc
    return CanonicalContext(
        user_id=class_row.teacher_user_id,
        class_id=class_id,
        seat_id=teacher_seat.id,
        actor_role="teacher",
    )


def _eligible_seat_ids(class_id: str) -> list[int]:
    """Claimed student seats with attendance activity (current PROD doctrine).

    Payroll pays each seat's sessions that closed after its last payroll event.
    Attendance rows alone do NOT establish eligibility: unclaim preserves the seat's productivity facts (DOM-IDEN-005 §Explicit Unclaim, INV-ARC-019),
    so a seat that attended and was later unclaimed keeps that history while
    holding no principal — and only a bound seat participates lawfully
    (DOM-IDEN-005 §VII-VIII). Claim state is therefore filtered explicitly here,
    never inferred from attendance. Returned ascending for determinism.
    """
    attended = {
        seat_id
        for (seat_id,) in (
            db.session.query(AttendanceSession.target_seat_id)
            .filter(AttendanceSession.class_id == class_id)
            .distinct()
            .all()
        )
        if seat_id is not None
    }
    if not attended:
        return []
    rows = (
        Seat.query.with_entities(Seat.id)
        .filter(
            Seat.id.in_(attended),
            Seat.role == "student",
            Seat.class_id == class_id,
            Seat.claimed_at.isnot(None),
        )
        .order_by(Seat.id.asc())
        .all()
    )
    return [row.id for row in rows]


def _already_settled(class_id: str, seat_id: int, payroll_cycle_id: str) -> bool:
    return (
        PayrollEvent.query
        .filter_by(
            class_id=class_id,
            target_seat_id=seat_id,
            payroll_cycle_id=payroll_cycle_id,
            payroll_event_type="payroll",
        )
        .first()
        is not None
    )


def settle_class_payroll_cycle(
    *,
    class_id: str,
    payroll_cycle_id: str,
    boundary_utc,
    run_mechanism: str,
    scheduled_occurrence=None,
    actor_ctx: CanonicalContext | None = None,
) -> ClassSettlementResult:
    """Settle the eligible class for one payroll cycle. NO COMMIT (§8.3b).

    Must run inside the caller's FEAT transaction: it reads the active correlation
    id and reuses it for every seat, so all events settle under one transaction and
    one correlation (the per-seat primitive re-enters FEAT-PROD-003 as a no-op
    rather than committing per seat). Re-invoking with the same ``payroll_cycle_id``
    inside the same transaction is idempotent — already-settled seats are skipped,
    so no duplicate payroll rows are manufactured.
    """
    if not class_id or not payroll_cycle_id:
        raise ValueError("class_id and payroll_cycle_id are required for settlement")
    if run_mechanism not in RUN_MECHANISMS:
        raise ValueError(f"run_mechanism must be one of {sorted(RUN_MECHANISMS)}")
    if run_mechanism == "SYSTEM" and scheduled_occurrence is None:
        raise ValueError("A SYSTEM payroll run must name the scheduled occurrence it settles.")
    if not class_has_payroll_settings(class_id):
        raise ClassSettlementError(
            f"Class {class_id} has no payroll settings; cannot settle a payroll cycle."
        )
    ctx = actor_ctx or _build_teacher_context(class_id)
    correlation_id = get_correlation_id()
    summary = {
        "source": "class_payroll_settlement",
        "description": "Payroll based on attendance",
    }
    if scheduled_occurrence is not None:
        # The occurrence, not the run's wall-clock time, anchors the next
        # payroll date, so a late run does not move later paydays (§XV.5).
        summary[SCHEDULED_OCCURRENCE_KEY] = ensure_utc(scheduled_occurrence).isoformat()

    settled: list[int] = []
    skipped: list[int] = []
    events: list[PayrollEvent] = []

    for seat_id in _eligible_seat_ids(class_id):
        if _already_settled(class_id, seat_id, payroll_cycle_id):
            skipped.append(seat_id)
            continue
        # A seat with no closed, unpaid session has nothing to settle and gets no
        # payroll event: an open session is paid once it closes.
        if calculate_payable_attendance_seconds(
            seat_id, class_id, ctx=ctx, as_of_utc=boundary_utc
        ) <= 0:
            continue
        result = record_payroll_event_command(
            ctx=ctx,
            target_seat_id=seat_id,
            payroll_event_type="payroll",
            correlation_id=correlation_id,
            idempotency_key=f"payroll-cycle:{payroll_cycle_id}:seat:{seat_id}",
            mechanism=run_mechanism,
            summary_json=dict(summary),
            reference_time_utc=boundary_utc,
            payroll_cycle_id=payroll_cycle_id,
        )
        settled.append(seat_id)
        events.append(result.payroll_event)

    if not settled and not skipped:
        raise NoPayableAttendanceError(
            f"No seat in class {class_id} has closed, unpaid attendance to settle."
        )

    return ClassSettlementResult(
        payroll_cycle_id=payroll_cycle_id,
        settled_seat_ids=settled,
        skipped_seat_ids=skipped,
        events=events,
    )
