from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.feats.base import requires_feat_context, get_correlation_id, audit_protected
from app.models import (
    AttendanceReasonCode,
    AttendanceSession,
    ClassEconomy,
    HallPassLog,
    HallPassSettings,
    PayrollEvent,
    Seat,
    Transaction,
)
from app.services.attendance_service import (CLOSED_SESSION_SETTLEMENT_RULE, lock_attendance_seat, close_due_attendance_intervals)
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import (
    consume_hall_pass,
    get_available_hall_pass_grant,
    get_hall_pass_balance,
)
from app.services.ledger_posting_service import create_pending_transaction
from app.services.payroll.pricing import SUMMARY_PRICING_KEY, price_payable_attendance
from app.services.payroll.settings import payroll_setting_by_uuid
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


@dataclass(frozen=True)
class AttendanceSessionResult:
    session: AttendanceSession


@dataclass(frozen=True)
class HallPassLogResult:
    hall_pass_log: HallPassLog


@dataclass(frozen=True)
class PayrollEventResult:
    payroll_event: PayrollEvent
    ledger_transaction: Transaction | None


def _require_context(ctx: CanonicalContext | None) -> CanonicalContext:
    if ctx is None:
        raise ValueError("CanonicalContext is required.")
    if not getattr(ctx, "class_id", None) or not getattr(ctx, "seat_id", None):
        raise ValueError("CanonicalContext must include class_id and seat_id.")
    return ctx


def _resolve_class_economy(class_id: str) -> ClassEconomy:
    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    if not economy:
        raise LookupError(f"No class economy found for class_id={class_id!r}.")
    return economy


def _latest_hall_pass_attendance_state(log: HallPassLog) -> str:
    rows = (
        AttendanceSession.query.filter_by(
            class_id=log.class_id,
            target_seat_id=log.requested_by_seat_id,
            hall_pass_id=log.hall_pass_id,
        )
        .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
        .all()
    )
    left_seen = False
    for row in rows:
        if row.status == "inactive" and row.reason_code == AttendanceReasonCode.HALL_PASS.value:
            left_seen = True
        elif left_seen and row.status == "active":
            return "returned"
    return "left" if left_seen else "approved"


def _enforce_hall_pass_settings(
    *,
    ctx: CanonicalContext,
    destination: str,
    reference_time_utc,
) -> str:
    settings = (
        HallPassSettings.query
        .filter(
            HallPassSettings.class_id == ctx.class_id,
            HallPassSettings.effective_date <= reference_time_utc,
        )
        .order_by(HallPassSettings.effective_date.desc(), HallPassSettings.id.desc())
        .first()
    )
    pass_types = settings.get_pass_types() if settings else HallPassSettings.get_default_pass_types()
    normalized_destination = (destination or "").strip().lower()
    pass_type = next(
        (
            item for item in pass_types
            if (item.get("pass_name") or "").strip().lower() == normalized_destination
        ),
        None,
    )
    if pass_type is not None and not pass_type.get("enabled", True):
        raise ValueError("Hall-pass destination is disabled.")

    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=reference_time_utc,
    )
    todays_logs = (
        HallPassLog.query.filter(
            HallPassLog.class_id == ctx.class_id,
            HallPassLog.timestamp >= day_bounds.boundary_start_utc,
            HallPassLog.timestamp < day_bounds.boundary_end_utc,
        )
        .order_by(HallPassLog.timestamp.asc(), HallPassLog.id.asc())
        .all()
    )
    currently_out = [
        log for log in todays_logs
        if _latest_hall_pass_attendance_state(log) == "left"
    ]

    queue_limit = min(settings.max_queue_limit, sum(item.get("max_queue", 0) for item in pass_types)) if settings else None
    if queue_limit is not None and len(currently_out) >= int(queue_limit):
        raise ValueError("Hall-pass queue limit reached.")

    simultaneous_limit = pass_type.get("max_queue") if pass_type else None
    if simultaneous_limit is not None:
        destination_out = [
            log for log in currently_out
            if (log.destination or "").strip().lower() == normalized_destination
        ]
        if len(destination_out) >= int(simultaneous_limit):
            raise ValueError("Hall-pass destination limit reached.")
    return settings.policy_uuid if settings else "default"


def _record_attendance_session_impl(
    *,
    ctx: CanonicalContext,
    status: str,
    target_seat_id: int | None = None,
    actor_seat_id: int | None = None,
    mechanism: str = "self",
    reason: str | None = None,
    reason_code: AttendanceReasonCode | None = None,
    hall_pass_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> AttendanceSessionResult:
    """Productivity DOMAIN command: record one attendance session row.

    Runs within the CALLING FEAT's single context — not a FEAT executor
    (INV-ARC-006, INV-ARC-021 §V.2). ``record_attendance_session`` is the thin
    FEAT-PROD-001 boundary for a top-level (route) ingress; a caller that
    already owns a context — the daily-limit enforcement job, which closes many
    seats under one envelope — composes this command directly.
    """
    ctx = _require_context(ctx)
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    event_time = evaluation.canonical_now_utc

    if status not in {"active", "inactive"}:
        raise ValueError("Attendance status must be 'active' or 'inactive'.")

    # Resolve reason_code for inactive status
    if status == "inactive" and reason_code is None and reason:
        normalized_reason = reason.strip().lower().replace(" ", "_")
        if normalized_reason == "hall_pass":
            reason_code = AttendanceReasonCode.HALL_PASS
        elif normalized_reason == "done_for_day":
            reason_code = AttendanceReasonCode.DONE_FOR_DAY
    if status == "inactive" and reason_code is None:
        raise ValueError("Inactive attendance sessions require a reason_code.")
    if status == "inactive" and reason_code == AttendanceReasonCode.HALL_PASS and not hall_pass_id:
        raise ValueError("Hall-pass attendance sessions require hall_pass_id.")

    resolved_actor_seat_id = actor_seat_id or ctx.seat_id
    resolved_target_seat_id = target_seat_id or ctx.seat_id
    if mechanism not in {"self", "teacher", "system"}:
        raise ValueError("Attendance mechanism must be 'self', 'teacher', or 'system'.")

    target_seat = lock_attendance_seat(resolved_target_seat_id, ctx.class_id)
    if target_seat is None or target_seat.class_id != ctx.class_id:
        raise ValueError("Attendance target seat must belong to the canonical class.")
    # Attendance is paid time, so recording it against an unclaimed seat is what
    # made that seat payroll-eligible. An unclaimed seat has no activated runtime
    # participation to record (DOM-IDEN-005 §VII).
    if target_seat.claimed_at is None or target_seat.user_id is None:
        raise ValueError("Attendance target seat must be claimed.")
    if resolved_actor_seat_id:
        actor_seat = db.session.get(Seat, resolved_actor_seat_id)
        if actor_seat is None or actor_seat.class_id != ctx.class_id:
            raise ValueError("Attendance actor seat must belong to the canonical class.")

    if status == "active":
        day_bounds = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,
            primitive="evaluation_day_boundaries",
            reference_time_utc=event_time,
        )

        # Reject if student already has done_for_day for this class today
        done_today = AttendanceSession.query.filter(
            AttendanceSession.target_seat_id == resolved_target_seat_id,
            AttendanceSession.class_id == ctx.class_id,
            AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
            AttendanceSession.timestamp >= day_bounds.boundary_start_utc,
            AttendanceSession.timestamp < day_bounds.boundary_end_utc,
        ).first()
        if done_today:
            raise ValueError("Student is done for the day and cannot start work again until the next canonical day.")

        # Close any existing active session with done_for_day
        existing_active = AttendanceSession.query.filter(
            AttendanceSession.target_seat_id == resolved_target_seat_id,
            AttendanceSession.class_id == ctx.class_id,
        ).order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc()).first()
        if existing_active is not None and existing_active.status == "active":
            # DOM-PROD-001 §312: the auto-close `inactive` entry must be dated to
            # the SAME canonical day as the originating `active` entry. If the new
            # tap-in is on a later day, the prior day's open session terminates at
            # that prior day's end-of-day boundary — never carried to today.
            existing_day_bounds = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="evaluation_day_boundaries",
                reference_time_utc=existing_active.timestamp,
            )
            closing_timestamp = min(event_time, existing_day_bounds.boundary_end_utc)
            closing_row = AttendanceSession(
                target_seat_id=existing_active.target_seat_id,
                actor_seat_id=resolved_actor_seat_id,
                class_id=existing_active.class_id,
                status="inactive",
                reason_code=AttendanceReasonCode.DONE_FOR_DAY.value,
                timestamp=closing_timestamp,
                mechanism=mechanism,
                hall_pass_id=None,
            )
            db.session.add(closing_row)
            db.session.flush()

        elif (
            existing_active is not None
            and existing_active.status == "inactive"
            and existing_active.reason_code == AttendanceReasonCode.HALL_PASS.value
        ):
            # A "hanging hall pass" (DOM-PROD-001 §318): the seat's latest event
            # is inactive/hall_pass, meaning the student is out of the room with
            # no return recorded yet. Nothing distinguishes that from an ordinary
            # break using only the seat's latest event, so a plain start_work call
            # — one that names no hall_pass_id — was silently accepted here and
            # overwrote the open-pass state with an unrelated active session. That
            # desynchronized the hall-pass log's issued/out classification from
            # ground truth: the teacher's page stopped showing the student as out,
            # even though they still were, and there was no longer a "Return"
            # control anywhere for either side to recover with — two extra
            # teacher actions (re-mark left, then return) were needed to walk the
            # state back to something coherent. Reproduced live on 2026-09-21.
            #
            # The legitimate return path IS a status="active" call while this
            # branch is true — checkin_hall_pass and the teacher's "return" action
            # both are — so the two are distinguished by whether the caller names
            # the SAME pass it is returning from, not by status alone.
            hall_pass_day_bounds = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="evaluation_day_boundaries",
                reference_time_utc=existing_active.timestamp,
            )
            same_day_hanging_pass = (
                hall_pass_day_bounds.boundary_start_utc
                <= event_time
                < hall_pass_day_bounds.boundary_end_utc
            )
            returning_from_this_pass = (
                hall_pass_id is not None
                and hall_pass_id == existing_active.hall_pass_id
            )
            if same_day_hanging_pass and not returning_from_this_pass:
                raise ValueError(
                    "Student is currently out on a hall pass and must check in "
                    "before a new work session can start."
                )

    resolved_reason_code = (
        reason_code.value if reason_code else AttendanceReasonCode.START_WORK.value
    ) if status == "active" else (
        reason_code.value if reason_code else None
    )

    session = AttendanceSession(
        target_seat_id=resolved_target_seat_id,
        actor_seat_id=resolved_actor_seat_id,
        class_id=ctx.class_id,
        status=status,
        reason_code=resolved_reason_code,
        timestamp=event_time,
        mechanism=mechanism,
        hall_pass_id=hall_pass_id,
    )
    db.session.add(session)
    db.session.flush()
    return AttendanceSessionResult(session=session)


@requires_feat_context("FEAT-PROD-001")
def record_attendance_session(
    *,
    ctx: CanonicalContext,
    status: str,
    target_seat_id: int | None = None,
    actor_seat_id: int | None = None,
    mechanism: str = "self",
    reason: str | None = None,
    reason_code: AttendanceReasonCode | None = None,
    hall_pass_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> AttendanceSessionResult:
    """FEAT-PROD-001 boundary for a top-level (route) attendance ingress.
    Delegates to the Productivity domain command; a caller that already owns a
    context composes ``_record_attendance_session_impl`` directly instead.
    """
    return _record_attendance_session_impl(
        ctx=ctx,
        status=status,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        mechanism=mechanism,
        reason=reason,
        reason_code=reason_code,
        hall_pass_id=hall_pass_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        reference_time_utc=reference_time_utc,
    )


def _record_hall_pass_log_impl(
    *,
    ctx: CanonicalContext,
    requested_by_seat_id: int,
    approved_by_seat_id: int,
    destination: str,
    reason: str,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> HallPassLogResult:
    """Productivity DOMAIN command: consume a hall-pass entitlement and record the
    HallPassLog. Runs within the CALLING FEAT's single context — not a FEAT
    executor (INV-ARC-006, INV-ARC-021 §V.2). ``record_hall_pass_log`` is the thin
    FEAT-PROD-002 boundary for a top-level (route) ingress.
    """
    ctx = _require_context(ctx)
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    now = evaluation.canonical_now_utc
    policy_uuid = _enforce_hall_pass_settings(
        ctx=ctx,
        destination=destination,
        reference_time_utc=now,
    )

    settings = (
        HallPassSettings.query
        .filter(
            HallPassSettings.class_id == ctx.class_id,
            HallPassSettings.effective_date <= now,
        )
        .order_by(HallPassSettings.effective_date.desc(), HallPassSettings.id.desc())
        .first()
    )
    pass_types = settings.get_pass_types() if settings else HallPassSettings.get_default_pass_types()
    pass_type = next(
        (
            item for item in pass_types
            if (item.get("pass_name") or "").strip().lower()
            == (destination or "").strip().lower()
        ),
        None,
    )
    consume_pass = pass_type.get("consume_pass", True) if pass_type else True

    if not requested_by_seat_id or not ctx.class_id:
        raise ValueError("Hall-pass consumption requires requested_by_seat_id and class_id")
    consume_event = None
    hall_pass_grant = get_available_hall_pass_grant(requested_by_seat_id, ctx.class_id)
    if consume_pass and hall_pass_grant is None:
        raise ValueError("No available hall-pass entitlement grant")
    if consume_pass:
        consume_event, _balance = consume_hall_pass(
            requested_by_seat_id,
            ctx.class_id,
            trigger_id=idempotency_key or f"hall_pass_log:{ctx.class_id}:{requested_by_seat_id}:{now.isoformat()}",
        )
        if not consume_event.correlation_id:
            raise ValueError("Hall-pass entitlement consumption missing correlation_id")
        if not consume_event.entitlement_id:
            raise ValueError("Hall-pass entitlement consumption missing entitlement_id")

    # A non-consuming destination has no entitlement lifecycle to reference, and
    # HallPassLog.hall_pass_id is documented as the *consumed* pass. Naming an
    # unconsumed grant there made two claims that are not true: the grant stayed
    # available, so a later consuming approval could consume and record the same
    # entitlement_id (the column is indexed but not unique, so two logs would
    # carry it while only one consumed a pass), and the copied correlation_id was
    # the grant's own, which identifies the purchase rather than this approval.
    fallback_correlation_id = (
        idempotency_key
        or f"hall_pass_log:{ctx.class_id}:{requested_by_seat_id}:{now.isoformat()}"
    )
    log = HallPassLog(
        requested_by_seat_id=requested_by_seat_id,
        approved_by_seat_id=approved_by_seat_id,
        class_id=ctx.class_id,
        timestamp=now,
        hall_pass_id=consume_event.entitlement_id if consume_event else None,
        correlation_id=(
            consume_event.correlation_id if consume_event else fallback_correlation_id
        ),
        policy_uuid=policy_uuid,
        destination=destination,
    )
    db.session.add(log)
    db.session.flush()

    return HallPassLogResult(hall_pass_log=log)


@requires_feat_context("FEAT-PROD-002")
def record_hall_pass_log(
    *,
    ctx: CanonicalContext,
    requested_by_seat_id: int,
    approved_by_seat_id: int,
    destination: str,
    reason: str,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> HallPassLogResult:
    """FEAT-PROD-002 boundary for a top-level (route) hall-pass log ingress.
    Delegates to the Productivity domain command; a FEAT that already owns a
    context composes ``_record_hall_pass_log_impl`` directly instead of this.
    """
    return _record_hall_pass_log_impl(
        ctx=ctx,
        requested_by_seat_id=requested_by_seat_id,
        approved_by_seat_id=approved_by_seat_id,
        destination=destination,
        reason=reason,
        idempotency_key=idempotency_key,
        reference_time_utc=reference_time_utc,
    )


def _record_payroll_event_impl(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    payroll_event_type: str,
    correlation_id: str,
    idempotency_key: str,
    mechanism: str,
    policy_uuid: str | None = None,
    summary_json: dict | None = None,
    reference_time_utc=None,
    amount: Decimal | None = None,
    payroll_cycle_id: str | None = None,
) -> PayrollEventResult:
    ctx = _require_context(ctx)
    # The initiating caller states the mechanism (FEAT-PROD-004 §II.1); it is
    # never inferred, because a SYSTEM payroll event anchors the next payroll
    # date (DOM-PROD-001 §XV.5).
    mechanism = (mechanism or "").strip().upper()
    if mechanism not in {"TEACHER", "SYSTEM"}:
        raise ValueError("FEAT-PROD-003 mechanism must be TEACHER or SYSTEM.")
    # DOM-PROD-001 §VIII: attendance-derived payroll records the payroll setting
    # that priced it, and resolves that setting itself while pricing — a caller
    # cannot name one. A manual credit is teacher intent, not a policy
    # computation, so it needs no payroll configuration; one that posts another
    # domain's calculation carries the setting that calculation used.
    if payroll_event_type == "payroll" and policy_uuid is not None:
        raise ValueError(
            "FEAT-PROD-003 prices payroll events by the settings in force; "
            "a caller-supplied policy_uuid is refused."
        )
    if policy_uuid is not None and payroll_setting_by_uuid(ctx.class_id, policy_uuid) is None:
        raise ValueError("FEAT-PROD-003 requires a payroll setting owned by the current class.")
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    recorded_at = evaluation.canonical_now_utc
    # Asserted for existence only: a payroll event must not be written against a
    # class that has no economy. The class's `section` is deliberately NOT read
    # here — pay rate is resolved from `class_id` alone (INV-ARC-014 §V).
    _resolve_class_economy(ctx.class_id)

    if payroll_event_type == "payroll":
        if amount is not None:
            raise ValueError("FEAT-PROD-003 derives a payroll event's amount; it cannot be supplied.")
        # Only closed, unpaid sessions are payable; an open session is settled
        # in full by the run after it closes (DOM-PROD-001 §VI.3). Each is priced
        # by the setting in force when it closed, never by the one in force now
        # (DOM-PROD-001 §XV.3), and the pricing inputs are recorded so the
        # amount is reproducible without storing it (INV-CORE-000 §III.3).
        close_due_attendance_intervals(ctx=ctx, seat_id=target_seat_id, as_of_utc=recorded_at)
        priced = price_payable_attendance(
            target_seat_id, ctx.class_id, ctx=ctx, as_of_utc=recorded_at
        )
        amount = priced.amount
        policy_uuid = priced.policy_uuid
        if policy_uuid is None:
            raise ValueError("FEAT-PROD-003 found no payable attendance to price for this payroll event.")
        summary_json = {
            **(summary_json or {}),
            "settlement_rule": CLOSED_SESSION_SETTLEMENT_RULE,
            "allocation_version": 1,
            SUMMARY_PRICING_KEY: priced.summary(),
        }
    elif payroll_event_type == "manual_credit" and amount is None:
        raise ValueError("manual_credit payroll events require an amount.")
    elif payroll_event_type == "reversal":
        original = (
            PayrollEvent.query.filter(
                PayrollEvent.class_id == ctx.class_id,
                PayrollEvent.target_seat_id == target_seat_id,
                PayrollEvent.correlation_id == correlation_id,
            )
            .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
            .first()
        )
        if original is None:
            raise LookupError("Unable to establish original payroll event for reversal.")
        if policy_uuid is None and original.policy_uuid is not None:
            # A reversal carries the provenance of the event it compensates.
            policy_uuid = original.policy_uuid
        if amount is None:
            active_correlation_id = get_correlation_id()
            linked = (
                Transaction.query.filter(
                    Transaction.class_id == ctx.class_id,
                    Transaction.target_seat_id == target_seat_id,
                    Transaction.correlation_id.in_([correlation_id, active_correlation_id]),
                )
                .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
                .first()
            )
            if linked is None:
                raise LookupError("Unable to establish original ledger transaction for reversal.")
            amount = -(Decimal(linked.amount or Decimal("0.00")))

    # Validate the target seat within the class boundary.
    target_seat = Seat.query.filter_by(id=target_seat_id, class_id=ctx.class_id).first()
    if target_seat is None:
        raise LookupError(f"Seat {target_seat_id} not found.")
    # Roster provisioning creates a participation opportunity and "SHALL NOT
    # activate runtime participation"; participation becomes lawful only on
    # Seat-to-User binding (DOM-IDEN-005 §VII-VIII). An unclaimed seat is a
    # teacher-provisioned placeholder (INV-CORE-000 §Constraints), so it can
    # receive no payroll or manual credit. Enforced at the single chokepoint
    # every payroll effect passes through, rather than trusting each caller's
    # roster query to have filtered correctly.
    if target_seat.claimed_at is None or target_seat.user_id is None:
        raise ValueError("A payroll event target seat must be claimed.")

    lock_attendance_seat(target_seat_id, ctx.class_id)
    ClassEconomy.query.filter_by(class_id=ctx.class_id).with_for_update().one()
    event = PayrollEvent(
        class_id=ctx.class_id,
        actor_seat_id=ctx.seat_id,
        target_seat_id=target_seat_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_uuid=policy_uuid,
        mechanism=mechanism,
        payroll_event_type=payroll_event_type,
        recorded_at=recorded_at,
        payroll_cycle_id=payroll_cycle_id,
        summary_json=summary_json or {},
    )
    db.session.add(event)
    db.session.flush()
    from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE
    audit_protected('payroll_event', event, 'INSERT', PROTECTED_FIELDS_BY_TABLE['payroll_event'])

    if amount is not None and amount != Decimal("0.00"):
        tx = create_pending_transaction(
            seat_id=target_seat_id,
            class_id=ctx.class_id,
            target_seat_id=target_seat_id,
            actor_seat_id=ctx.seat_id,
            mechanism=mechanism.lower(),
            amount=amount,
            account_type="checking",
            type="payroll" if payroll_event_type != "manual_credit" else "manual_payment",
            description=(summary_json or {}).get("description", "Payroll event"),
            idempotency_key=idempotency_key,
        )
    else:
        tx = None

    return PayrollEventResult(payroll_event=event, ledger_transaction=tx)


@requires_feat_context("FEAT-PROD-003")
def record_payroll_event(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    payroll_event_type: str,
    correlation_id: str,
    idempotency_key: str,
    mechanism: str,
    policy_uuid: str | None = None,
    summary_json: dict | None = None,
    reference_time_utc=None,
    amount: Decimal | None = None,
    payroll_cycle_id: str | None = None,
) -> PayrollEventResult:
    return _record_payroll_event_impl(
        ctx=ctx,
        target_seat_id=target_seat_id,
        payroll_event_type=payroll_event_type,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_uuid=policy_uuid,
        mechanism=mechanism,
        summary_json=summary_json,
        reference_time_utc=reference_time_utc,
        amount=amount,
        payroll_cycle_id=payroll_cycle_id,
    )


@requires_feat_context("FEAT-PROD-003")
def record_payroll_reversal(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    correlation_id: str,
    idempotency_key: str,
    mechanism: str,
    policy_uuid: str | None = None,
    summary_json: dict | None = None,
    reference_time_utc=None,
) -> PayrollEventResult:
    return _record_payroll_event_impl(
        ctx=ctx,
        target_seat_id=target_seat_id,
        payroll_event_type="reversal",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_uuid=policy_uuid,
        mechanism=mechanism,
        summary_json=summary_json,
        reference_time_utc=reference_time_utc,
    )
