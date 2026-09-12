"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
import secrets
from typing import Callable, NamedTuple
from app.feats.base import FEATContextError, requires_feat_context
from app.services.insurance_policy_service import delete_due_policy_lineages
# TODO (Phase 4): insurance_billing deleted; move to Obligations domain
# from app.utils.insurance_billing import get_insurance_billing_snapshot


@requires_feat_context("FEAT-PROD-001")
def enforce_daily_limits_job():
    """
    Scheduled job that checks active seats and records an inactive PROD event
    when the class daily limit has been reached.

    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    # Compose the Productivity domain command, not the FEAT-PROD-001 entry —
    # this job already owns the envelope and exactly one FEAT executes per
    # invocation (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).
    from app.feats.prod import _record_attendance_session_impl
    from app.extensions import db
    from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, Seat
    from app.payroll import get_daily_limit_seconds
    from app.services.context_resolver import CanonicalContext
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
    )

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled daily-limit enforcement job")

    try:
        events = (
            AttendanceSession.query
            .order_by(
                AttendanceSession.class_id.asc(),
                AttendanceSession.target_seat_id.asc(),
                AttendanceSession.timestamp.asc(),
                AttendanceSession.id.asc(),
            )
            .all()
        )
        rows_by_class_id = {}
        rows_by_scope = {}
        for event in events:
            rows_by_class_id.setdefault(event.class_id, []).append(event)
            rows_by_scope.setdefault((event.class_id, event.target_seat_id), []).append(event)

        checked_count = 0
        closed_count = 0

        def _active_intervals_for_day(rows, *, day_start_utc, horizon_utc):
            """Paid intervals inside ONE canonical class day, bounded by ``horizon_utc``.

            ``horizon_utc`` is the end of that day, or the canonical now when the
            day is still running. Clamping the interval END — not just the start —
            is what stops a session that outlived its own day from being re-read as
            a session that began at the following midnight (DOM-PROD-001 §312).
            """
            intervals = []
            active_start = None
            for row in rows:
                if row.timestamp > horizon_utc:
                    break
                if row.status == "active":
                    active_start = row.timestamp
                    continue
                if row.status == "inactive" and active_start is not None:
                    interval_start = max(active_start, day_start_utc)
                    interval_end = min(row.timestamp, horizon_utc)
                    if interval_end >= interval_start:
                        intervals.append((interval_start, interval_end))
                    active_start = None
            if active_start is not None:
                interval_start = max(active_start, day_start_utc)
                if horizon_utc >= interval_start:
                    intervals.append((interval_start, horizon_utc))
            return intervals

        for class_id, class_events in rows_by_class_id.items():
            class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
            if class_row is None:
                continue

            # Previously guarded on `class_row.section`, so a class with no
            # section label never had its configured daily limit enforced here
            # at all. The limit is class-scoped policy; the label is not a
            # precondition for it (INV-ARC-014 §V).
            #
            # A missing limit is no longer a reason to skip the class. The
            # end-of-day termination in DOM-PROD-001 §312 is unconditional — it
            # is not contingent on a daily limit being configured — so only the
            # §314 limit arithmetic below is skipped when `daily_limit` is None.
            daily_limit = get_daily_limit_seconds(class_id=class_id)

            actor_seat_id = resolve_teacher_seat_for_class(class_id).id
            ctx = CanonicalContext(
                user_id=class_row.teacher_user_id,
                class_id=class_id,
                seat_id=actor_seat_id,
                actor_role="teacher",
            )
            now_evaluation = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            )
            now_utc = now_evaluation.canonical_now_utc

            active_latest_events = {}
            for event in class_events:
                active_latest_events[event.target_seat_id] = event

            for seat_id, latest_event in active_latest_events.items():
                if latest_event.status != "active":
                    continue
                try:
                    with db.session.begin_nested():
                        checked_count += 1

                        seat = Seat.query.filter_by(
                            id=seat_id,
                            class_id=class_id,
                            role="student",
                        ).first()
                        if seat is None:
                            continue

                        # The open session is evaluated in the canonical day of
                        # its OWN `active` row, never in today's. Anchoring on
                        # today is what let a session survive a server outage
                        # across midnight and be re-read as one that began at
                        # today's 00:00 — which both lost the prior day's
                        # end-of-day row and dated the closing row to today,
                        # locking the student out of working (the `done_today`
                        # gate in app/feats/prod.py).
                        day_bounds = canonical_temporal_resolver(
                            CLASS_LEVEL_EVALUATION,
                            canonical_execution_context=ctx,
                            primitive="evaluation_day_boundaries",
                            reference_time_utc=latest_event.timestamp,
                        )
                        day_end_utc = day_bounds.boundary_end_utc
                        # No session accrues past the end of its own day (§312),
                        # and none accrues into the future.
                        day_is_over = day_end_utc <= now_utc
                        horizon_utc = day_end_utc if day_is_over else now_utc

                        intervals = _active_intervals_for_day(
                            rows_by_scope[(class_id, seat_id)],
                            day_start_utc=day_bounds.boundary_start_utc,
                            horizon_utc=horizon_utc,
                        )
                        if not intervals:
                            continue

                        close_at_utc = None
                        reason = None

                        if daily_limit:
                            total_evaluation = canonical_temporal_resolver(
                                CLASS_LEVEL_EVALUATION,
                                canonical_execution_context=ctx,
                                primitive="elapsed_duration",
                                reference_time_utc=now_utc,
                                intervals=intervals,
                            )
                            if total_evaluation.elapsed_seconds >= daily_limit:
                                # DOM-PROD-001 §314: correct the closing timestamp
                                # so the accumulated time equals the limit exactly.
                                accumulated_before_active = 0
                                active_start, _active_end = intervals[-1]
                                if len(intervals) > 1:
                                    prior_evaluation = canonical_temporal_resolver(
                                        CLASS_LEVEL_EVALUATION,
                                        canonical_execution_context=ctx,
                                        primitive="elapsed_duration",
                                        reference_time_utc=now_utc,
                                        intervals=intervals[:-1],
                                    )
                                    accumulated_before_active = prior_evaluation.elapsed_seconds

                                remaining_seconds = int(daily_limit) - int(accumulated_before_active)
                                close_at_utc = active_start
                                if remaining_seconds > 0:
                                    close_evaluation = canonical_temporal_resolver(
                                        CLASS_LEVEL_EVALUATION,
                                        canonical_execution_context=ctx,
                                        primitive="shift_timestamp",
                                        reference_time_utc=now_utc,
                                        timestamp=active_start,
                                        elapsed_seconds=remaining_seconds,
                                    )
                                    close_at_utc = close_evaluation.shifted_timestamp_utc
                                reason = f"Daily limit reached ({daily_limit / 3600:.1f}h)"

                        if close_at_utc is None and day_is_over:
                            # DOM-PROD-001 §312: terminate at end of day in the
                            # canonical class timezone, dated to the same day as
                            # the originating `active` entry. Unconditional — it
                            # does not require a configured daily limit.
                            close_at_utc = day_end_utc
                            reason = "Automatically closed at end of day"

                        if close_at_utc is None:
                            # Still inside its own day and under the limit.
                            continue

                        reached_at_or_before_now = canonical_temporal_resolver(
                            CLASS_LEVEL_EVALUATION,
                            canonical_execution_context=ctx,
                            primitive="later_than",
                            reference_time_utc=now_utc,
                            candidate=now_utc,
                            reference=close_at_utc,
                        )
                        if not reached_at_or_before_now.is_later and now_utc != close_at_utc:
                            continue

                        _record_attendance_session_impl(
                            ctx=ctx,
                            target_seat_id=seat_id,
                            actor_seat_id=actor_seat_id,
                            mechanism="system",
                            status="inactive",
                            reason=reason,
                            reason_code=AttendanceReasonCode.DONE_FOR_DAY,
                            idempotency_key=f"daily_limit:{class_id}:{seat_id}:{secrets.token_hex(12)}",
                            reference_time_utc=close_at_utc,
                        )

                        closed_count += 1
                        logger.info(
                            "Closed attendance session for seat %s in class %s at %s (%s)",
                            seat_id,
                            class_id,
                            close_at_utc,
                            reason,
                        )
                except FEATContextError:
                    # A constitutional violation is never per-seat noise. Swallowing
                    # it here is how this job reported success while closing zero
                    # sessions for eight weeks; let it abort the run and surface.
                    raise
                except Exception as e:
                    logger.error(
                        "Error checking daily limit for seat %s in class %s: %s",
                        seat_id,
                        class_id,
                        e,
                        exc_info=True,
                    )
                    continue
        logger.info(
            "Daily-limit enforcement job completed. Checked %s active seats, closed %s sessions",
            checked_count,
            closed_count,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Daily-limit enforcement job failed: {e}", exc_info=True)


@requires_feat_context("FEAT-OPS-001")
def database_maintenance_job():
    """
    Scheduled job that performs nightly database maintenance tasks.
    Runs at 2 AM UTC to clean up orphaned entries and maintain data integrity.
    """
    # Import here to avoid circular imports
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly database maintenance job")

    total_cleaned = 0

    try:
        # Task 1: StoreItemBlock orphan cleanup REMOVED.
        # store_item_blocks table dropped (migration 7c3d4e5f6a7b) — unauthorized per DOM-STORE-001.
        # Canonical replacement: store_item_visibility (seat_id scoped, no block/period key).
        # TODO: Implement store_item_visibility orphan cleanup if needed.
        logger.info("StoreItemBlock cleanup skipped — table dropped (migration 7c3d4e5f6a7b)")

        logger.info(
            "Skipping legacy join_code backfill in nightly maintenance; "
            "records are expected to already be class-scoped."
        )
        logger.info(f"Database maintenance completed. Total orphaned entries cleaned: {total_cleaned}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database maintenance job failed: {e}", exc_info=True)

def run_rent_reconciliation_job():
    """Materialize the recurring rent lifecycle for every rent-enabled class.

    Canonical single mechanism (FEAT-OBL-002): for each class this creates the
    initial cycle + assessments on first run, advances successor cycles once a
    cycle's ``next_assessment_at`` has been reached, and expires the prior
    cycle's PERK hall passes at the rent boundary. The whole thing is idempotent,
    so re-running produces no duplicate cycles, assessments, or expiry events.

    Each class is reconciled under its OWN top-level FEAT transaction so a
    failure in one class cannot roll back or block another. This function is
    therefore a plain loop — it must NOT itself hold a FEAT context, which would
    force every class into a single shared correlation/transaction.
    """
    from app.extensions import db
    from app.models import ClassEconomy
    from app.services.class_configuration_query_service import is_feature_enabled
    from app.feats.reconcile_rent_feat import execute_reconcile_rent

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled rent reconciliation job")

    reconciled = 0
    skipped = 0
    failed = 0
    try:
        class_ids = [row.class_id for row in ClassEconomy.query.order_by(ClassEconomy.class_id.asc()).all()]
    except Exception:
        db.session.rollback()
        logger.exception("Rent reconciliation job could not enumerate classes")
        return

    for class_id in class_ids:
        # Class-level rent gate short-circuit (execute_reconcile_rent also guards,
        # but skipping here avoids opening a FEAT transaction for disabled classes).
        try:
            if not is_feature_enabled(class_id, "rent"):
                skipped += 1
                continue
            result = execute_reconcile_rent(class_id)
            reconciled += 1
            if result.cycles_created or result.perks_expired:
                logger.info(
                    "Rent reconciliation for class %s: reason=%s cycles=%s assessments=%s perks_expired=%s",
                    class_id,
                    result.reason,
                    result.cycles_created,
                    result.assessments_created,
                    result.perks_expired,
                )
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception("Rent reconciliation failed for class %s", class_id)
            continue

    logger.info(
        "Rent reconciliation job completed. Reconciled %s class(es), skipped %s, failed %s",
        reconciled,
        skipped,
        failed,
    )


def run_automatic_payroll_job():
    """Automatic payroll: fire the canonical completion FEAT for every due class.

    Automatic payroll is merely a second *initiation mechanism* for the same
    economic-cycle completion as manual payroll (DOM-PROD-001 §XV). This job owns
    exactly one question — "is this class due for automatic payroll now?" — and
    then becomes just another caller of ``complete_payroll_cycle``. It contains no
    payroll, interpretation, or activation logic of its own.

    A class is due when its active ``PayrollSettings`` carries a
    ``next_payroll_date`` at or before now. The **scheduled occurrence** (that
    ``next_payroll_date``) is the deterministic command identity: every retry of
    the same occurrence derives the same idempotency key, while the next intended
    occurrence — after ``next_payroll_date`` advances — derives a different one. So
    the ``payroll_cycle_completion`` anchor makes scheduler retries idempotent
    without any bespoke job-run substrate. Each class runs under its OWN top-level
    FEAT transaction (a plain loop, no shared FEAT context), so one class's failure
    cannot roll back or block another; the ``next_payroll_date`` advance commits
    atomically with the cycle so a failed run stays due under the same key.
    """
    from datetime import timedelta

    from app.extensions import db
    from app.feats.base import FEATContext
    from app.feats.complete_payroll_cycle import complete_payroll_cycle
    from app.models import ClassEconomy, PayrollSettings
    from app.services.class_configuration_query_service import is_feature_enabled
    from app.services.context_resolver import CanonicalContext
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.services.payroll.cycle_completion import get_completed_cycle_window
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
        ensure_utc,
        utc_now,
    )

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled automatic-payroll job")

    now = utc_now()
    try:
        due_settings = (
            PayrollSettings.query
            .filter(
                PayrollSettings.availability_state == 'IN_USE',
                PayrollSettings.next_payroll_date.isnot(None),
                PayrollSettings.next_payroll_date <= now,
            )
            .order_by(PayrollSettings.class_id.asc())
            .all()
        )
    except Exception:
        db.session.rollback()
        logger.exception("Automatic-payroll job could not enumerate due classes")
        return

    ran = 0
    skipped = 0
    failed = 0
    for settings in due_settings:
        class_id = settings.class_id
        scheduled_occurrence = ensure_utc(settings.next_payroll_date)
        try:
            if not is_feature_enabled(class_id, "payroll"):
                skipped += 1
                continue
            class_row = db.session.get(ClassEconomy, class_id)
            if class_row is None or not class_row.teacher_user_id:
                skipped += 1
                continue

            ctx = CanonicalContext(
                user_id=class_row.teacher_user_id,
                class_id=class_id,
                seat_id=resolve_teacher_seat_for_class(class_id).id,
                actor_role="teacher",
            )
            boundary_utc = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            ).canonical_now_utc
            cycle_started_at, cycle_completed_at = get_completed_cycle_window(
                class_id, boundary_utc=boundary_utc
            )

            idempotency_key = f"auto-payroll:{class_id}:{scheduled_occurrence.isoformat()}"
            frequency_days = settings.payroll_frequency_days or 14
            with FEATContext("FEAT-PROD-004", idempotency_key=idempotency_key):
                complete_payroll_cycle(
                    ctx=ctx,
                    idempotency_key=idempotency_key,
                    cycle_started_at=cycle_started_at,
                    cycle_completed_at=cycle_completed_at,
                )
                # Scheduling bookkeeping (the scheduler's own concern), committed
                # atomically with the cycle so a failure leaves the class due.
                settings.next_payroll_date = scheduled_occurrence + timedelta(days=frequency_days)
            ran += 1
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception("Automatic payroll failed for class %s", class_id)
            continue

    logger.info(
        "Automatic-payroll job completed. Ran %s class(es), skipped %s, failed %s",
        ran, skipped, failed,
    )


def run_audit_invariant_check_job():
    """Nightly audit chain integrity verification.

    Walks all active class chains and the system chain, recomputing HMAC
    signatures and verifying hash continuity. The result is consumed by the
    Operations status-signal pipeline.
    """
    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly audit invariant check")
    try:
        from app.utils.audit_verifier import run_full_invariant_check, record_integrity_verification
        results = run_full_invariant_check()
        record_integrity_verification(results)

        passing = all(r.state == "VERIFIED" for r in results)
        if passing:
            logger.info(
                "Audit invariant check passed: %d chain(s) verified", len(results)
            )
        else:
            failed = [r for r in results if r.state != "VERIFIED"]
            logger.error(
                "Audit invariant check FAILED: %d/%d chain(s) invalid — %s",
                len(failed),
                len(results),
                [{"scope": r.chain_scope, "type": r.failure_type} for r in failed],
            )
    except Exception:
        logger.exception("Audit invariant check job encountered an unhandled error")


def run_insurance_expiry_job():
    """Daily insurance boundary expiry: EXPIRE coverage whose cycle boundary passed.

    The canonical terminal disposition for purchased insurance is EXPIRED at the
    coverage boundary — never REVOKED or refunded (FEAT-STOR-002 §IX.C, DOM-STORE-001
    §1). Coverage stops renewing when its recurring premium lineage is terminated
    (a terminal ``bill_cycles`` row with ``next_assessment_at IS NULL`` — via
    FEAT-OBL-005 cancellation, teacher offering-cancel, or nonpayment non-renewal;
    DOM-OBL-001 §160/§241). This job is the Store-owned boundary trigger: it reads
    the bill-cycle table directly for terminal insurance lineages whose
    ``cycle_boundary_at`` has been reached and writes EXPIRED for the matching
    coverage through the FEAT-STOR-002 domain command.

    The work-list is the table itself — terminal rows past boundary — so there is no
    per-entitlement enumeration and no lag: a lineage becomes due the day its
    boundary arrives. Each expiry runs under its OWN top-level FEAT-STOR-002 context
    (isolated failure), and ``expire_entitlement`` is idempotent (an already-EXPIRED
    lineage is a no-op), so re-runs are safe.
    """
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import BillCycle, ObligationAssessment
    from app.services import entitlement_service
    from app.services.entitlement_read_service import get_active_insurance_grant
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.utils.canonical_temporal_resolver import ensure_utc, utc_now

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled insurance boundary-expiry job")

    now = utc_now()
    try:
        terminal_cycles = (
            BillCycle.query
            .filter(
                BillCycle.next_assessment_at.is_(None),   # terminal — recurrence stopped
                BillCycle.cycle_boundary_at <= now,       # coverage boundary reached
            )
            .order_by(BillCycle.class_id.asc(), BillCycle.id.asc())
            .all()
        )
    except Exception:
        db.session.rollback()
        logger.exception("Insurance expiry job could not enumerate terminal cycles")
        return

    expired = 0
    skipped = 0
    failed = 0
    for cycle in terminal_cycles:
        try:
            # Resolve the seat/policy binding, which lives on the INSURANCE_PREMIUM
            # assessment the cycle drives (bill cycles are seat-blind). A cycle with
            # no insurance assessment is some other lineage (e.g. rent) — skip.
            assessment = (
                ObligationAssessment.query
                .filter_by(
                    internal_ref=cycle.internal_ref,
                    obligation_type="INSURANCE_PREMIUM",
                )
                .first()
            )
            if assessment is None:
                skipped += 1
                continue

            grant = get_active_insurance_grant(
                assessment.seat_id, assessment.class_id, assessment.policy_uuid
            )
            if grant is None:
                # Already expired (or no active coverage for this lineage).
                skipped += 1
                continue

            boundary = ensure_utc(cycle.cycle_boundary_at)
            idempotency_key = (
                f"insurance-expiry:{grant.entitlement_id}:{boundary.isoformat()}"
            )
            with FEATContext("FEAT-STOR-002", idempotency_key=idempotency_key):
                entitlement_service.expire_entitlement(
                    entitlement_id=grant.entitlement_id,
                    class_id=assessment.class_id,
                    target_seat_id=assessment.seat_id,
                    actor_seat_id=resolve_teacher_seat_for_class(assessment.class_id).id,
                    product_id=grant.product_id,
                    entitlement_type="INSURANCE",
                    acquisition_type=grant.acquisition_type,
                    correlation_id=idempotency_key,
                    payload={
                        "source": "run_insurance_expiry_job",
                        "policy_uuid": assessment.policy_uuid,
                    },
                )
            expired += 1
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception(
                "Insurance expiry failed for lineage %s", cycle.internal_ref
            )
            continue

    logger.info(
        "Insurance boundary-expiry job completed. Expired %s, skipped %s, failed %s",
        expired, skipped, failed,
    )


def run_collective_goal_expiry_job():
    """Sweep lapsed collective goals: EXPIRE the unmet ones and refund their buy-ins.

    DOM-STORE-001 §5 requires a collective-goal entitlement to "record EXPIRED
    when the goal is not reached by the deadline and coordinate a lawful refund."
    The purchase-time gate already stops a lapsed goal from selling; this job is
    the other half — without it, students who bought into a goal that never
    happened keep an unexercisable entitlement and stay charged for it.

    Only **unmet** goals are swept. A goal that reached its target before the
    deadline stays GRANTED: the reward is owed and the teacher fulfils it by
    hand, so expiring it would refund the students who actually won.

    The work-list is the product table itself — live goal products whose
    deadline has passed — so there is no per-entitlement enumeration. Each goal
    runs under its OWN top-level FEAT-STOR-002 context (isolated failure), and
    the command skips lineages that already terminated, so re-runs are safe.
    """
    from app.extensions import db
    from app.feats.collective_goal_expiry_feat import expire_lapsed_collective_goal
    from app.models import StoreProduct
    from app.services import store_service
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.services.store import collective_goals
    from app.utils.canonical_temporal_resolver import utc_now

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled collective-goal expiry job")

    now = utc_now()
    try:
        lapsed_products = (
            StoreProduct.query
            .filter(
                StoreProduct.item_type == 'collective',
                StoreProduct.availability_state == store_service.IN_USE,
                StoreProduct.collective_goal_expires_at.isnot(None),
                StoreProduct.collective_goal_expires_at <= now,
            )
            .order_by(StoreProduct.class_id.asc(), StoreProduct.product_lineage_uuid.asc())
            .all()
        )
    except Exception:
        db.session.rollback()
        logger.exception("Collective-goal expiry job could not enumerate lapsed goals")
        return

    expired = 0
    refunded = 0
    skipped = 0
    failed = 0
    unresolved = 0
    for product in lapsed_products:
        class_id = product.class_id
        lineage = product.product_lineage_uuid
        try:
            # Whether the goal was met is read through the shared authority, so
            # this decision matches the progress bar both the student and the
            # teacher were shown.
            class_size = collective_goals.count_class_size(class_id)
            target = collective_goals.resolve_goal_target(product, class_size)
            participants = collective_goals.count_goal_participants(
                class_id, [lineage]
            ).get(lineage, 0)

            if collective_goals.is_goal_met(participants, target):
                # Met before the deadline — the reward stands, fulfilment is manual.
                skipped += 1
                continue

            # The FEAT entry owns its own envelope, so this job must not open
            # one — exactly one FEAT executes per invocation (INV-ARC-000
            # §VIII.2), and nesting is refused.
            result = expire_lapsed_collective_goal(
                product=product,
                class_id=class_id,
                actor_seat_id=resolve_teacher_seat_for_class(class_id).id,
                idempotency_key=f"goal-expiry:{class_id}:{lineage}",
            )
            expired += result.entitlements_expired
            refunded += result.purchases_refunded
            unresolved += len(result.unresolved_correlations)
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception(
                "Collective-goal expiry failed for lineage %s in class %s",
                lineage, class_id,
            )
            continue

    logger.info(
        "Collective-goal expiry job completed. Expired %s entitlement(s) across "
        "%s refunded purchase(s); skipped %s met goal(s), %s unresolved "
        "purchase(s) left for review, %s goal(s) failed",
        expired, refunded, skipped, unresolved, failed,
    )


def run_economy_rebalance_activation_job():
    """Activate due queued economy policy transitions for every teacher.

    FEAT-CLASS-005 is HIGH blast radius, so its envelope requires an
    idempotency_key. ``requires_feat_context`` reads that key from keyword
    arguments only, and this job is invoked by the scheduler with none, so a
    decorator-owned envelope refuses before the body runs. Each teacher
    therefore gets its own context with a derived key, which also keeps one
    teacher's failure from rolling back the activations already committed for
    the teachers before it.
    """
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import ClassEconomy
    from app.utils.canonical_temporal_resolver import utc_now
    from app.utils.economy_rebalance import activate_due_rebalances

    logger = logging.getLogger('scheduled_tasks')
    teacher_ids = [
        row[0]
        for row in db.session.query(ClassEconomy.teacher_user_id)
        .filter(ClassEconomy.teacher_user_id.isnot(None))
        .distinct()
        .all()
    ]
    activated = 0
    failed = 0
    run_key = utc_now().strftime("%Y-%m-%dT%H")
    for teacher_id in teacher_ids:
        try:
            with FEATContext(
                "FEAT-CLASS-005",
                idempotency_key=f"economy-rebalance-job:{teacher_id}:{run_key}",
            ):
                count, _labels = activate_due_rebalances(teacher_id)
                activated += count
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception(
                "Economy rebalance activation failed for teacher %s", teacher_id
            )
    logger.info(
        "Economy rebalance activation completed; activated %s transition(s), "
        "failed %s teacher(s)",
        activated, failed,
    )


def run_ledger_settlement_job():
    """Settle every seat context carrying unsettled ledger activity.

    ``create_pending_transaction`` is the only ledger write boundary and it
    creates every effect PENDING, so settlement is what admits money to posted
    history: it assigns ``posting_sequence`` and advances
    ``LedgerBalanceSnapshot``. Nothing else in the application calls it, which
    means without this job no transaction ever posts, every snapshot stays
    absent, and every posted-balance read answers zero forever.
    """
    from app.services.ledger_settlement_service import settle_pending_transaction_contexts

    logger = logging.getLogger('scheduled_tasks')
    summary = settle_pending_transaction_contexts()
    logger.info(
        "Ledger settlement sweep completed; settled %s context(s), failed %s context(s)",
        summary["settled_contexts"], summary["failed_contexts"],
    )
    return summary


def run_savings_interest_job():
    """Post the current savings-interest payout for eligible class seats."""
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import Seat
    from app.services.ledger_interest_service import apply_monthly_savings_interest
    from app.utils.canonical_temporal_resolver import utc_now

    # Interest accrues on posted balances only (SPEC-ECON-001 §9.2), so an
    # unsettled ledger presents a zero base and this job underpays silently
    # rather than failing. Two independent interval jobs have no ordering
    # guarantee between them, so the dependency is discharged here instead of
    # being left to registration order.
    run_ledger_settlement_job()

    logger = logging.getLogger('scheduled_tasks')
    class_ids = [row[0] for row in db.session.query(Seat.class_id).distinct().all()]
    posted = 0
    failed = 0
    period_key = utc_now().strftime("%Y-%m")
    for class_id in class_ids:
        seats = Seat.query.filter(Seat.class_id == class_id).order_by(Seat.id.asc()).all()
        try:
            with FEATContext(
                "FEAT-LED-001",
                idempotency_key=f"savings-interest-job:{class_id}:{period_key}",
            ):
                for seat in seats:
                    if apply_monthly_savings_interest(seat) is not None:
                        posted += 1
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception("Savings-interest payout failed for class %s", class_id)
    logger.info(
        "Savings-interest job completed; posted %s payout(s), failed %s class(es)",
        posted, failed,
    )


SCHEDULED_JOB_MAX_INSTANCES = 1


class ScheduledJobSpec(NamedTuple):
    """One scheduled job's registration, declared apart from the scheduler.

    The jobs used to be registered by ten inline ``scheduler.add_job`` calls
    inside ``init_scheduled_tasks``, which is skipped under TESTING and only
    reachable by starting a real BackgroundScheduler. That made "is this job
    registered at all?" untestable — and a settlement sweep that existed as a
    function nobody scheduled is exactly the defect that shipped. Declaring the
    set here lets a test assert membership and ordering without a scheduler.
    """

    id: str
    name: str
    func: Callable[[], object]
    trigger: str
    trigger_kwargs: dict


# Ordering is meaningful where one job depends on another having run: ledger
# settlement precedes savings interest because interest accrues on posted
# balances only. Registration order alone does not enforce that at runtime —
# run_savings_interest_job discharges the dependency itself — but declaring it
# here keeps the relationship visible and assertable.
SCHEDULED_JOB_SPECS: tuple[ScheduledJobSpec, ...] = (
    ScheduledJobSpec(
        id='enforce_daily_limits',
        name='Enforce daily attendance limits',
        func=enforce_daily_limits_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    ScheduledJobSpec(
        id='database_maintenance',
        name='Nightly database maintenance',
        func=database_maintenance_job,
        trigger='cron',
        trigger_kwargs={'hour': 2, 'minute': 0},
    ),
    ScheduledJobSpec(
        id='audit_invariant_check',
        name='Nightly audit chain integrity verification',
        func=run_audit_invariant_check_job,
        trigger='cron',
        trigger_kwargs={'hour': 3, 'minute': 0},
    ),
    # Hourly so cycle boundaries and rent-boundary PERK expiry are materialized
    # promptly across timezones, even when no student visits the rent page.
    # Idempotent per class.
    ScheduledJobSpec(
        id='rent_reconciliation',
        name='Rent lifecycle reconciliation',
        func=run_rent_reconciliation_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    # Fires the canonical completion FEAT only for classes whose
    # next_payroll_date is due; idempotent per scheduled occurrence, so an
    # hourly cadence never double-runs a cycle.
    ScheduledJobSpec(
        id='automatic_payroll',
        name='Automatic payroll (due classes)',
        func=run_automatic_payroll_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    # Reads the bill-cycle table for terminal insurance lineages whose coverage
    # boundary has passed and writes EXPIRED via FEAT-STOR-002. Idempotent per
    # entitlement/boundary, so a daily cadence never double-expires.
    ScheduledJobSpec(
        id='insurance_expiry',
        name='Insurance boundary expiry',
        func=run_insurance_expiry_job,
        trigger='cron',
        trigger_kwargs={'hour': 4, 'minute': 0},
    ),
    # Hourly, because a goal deadline is a wall-clock instant the teacher chose
    # rather than a daily boundary, and students can see the deadline pass.
    # Skips goals already met and lineages already terminated.
    ScheduledJobSpec(
        id='collective_goal_expiry',
        name='Collective goal expiry and refund',
        func=run_collective_goal_expiry_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    ScheduledJobSpec(
        id='economy_rebalance_activation',
        name='Activate due economy rebalances',
        func=run_economy_rebalance_activation_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    ScheduledJobSpec(
        id='ledger_settlement',
        name='Ledger settlement sweep',
        func=run_ledger_settlement_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
    ScheduledJobSpec(
        id='savings_interest_payout',
        name='Savings interest payout',
        func=run_savings_interest_job,
        trigger='interval',
        trigger_kwargs={'hours': 1},
    ),
)


def init_scheduled_tasks(app):
    """
    Initialize and start scheduled tasks.

    Args:
        app: Flask application instance
    """
    from app.extensions import scheduler

    logger = logging.getLogger('scheduled_tasks')

    if scheduler.running:
        logger.info("Scheduler already running")
        return

    def in_app_context(job_func):
        def run():
            with app.app_context():
                job_func()
        run.__name__ = job_func.__name__
        return run

    for spec in SCHEDULED_JOB_SPECS:
        scheduler.add_job(
            func=in_app_context(spec.func),
            trigger=spec.trigger,
            id=spec.id,
            name=spec.name,
            replace_existing=True,
            max_instances=SCHEDULED_JOB_MAX_INSTANCES,
            **spec.trigger_kwargs,
        )

    scheduler.start()
    logger.info(
        "Scheduled tasks initialized: %s",
        ", ".join(spec.id for spec in SCHEDULED_JOB_SPECS),
    )
