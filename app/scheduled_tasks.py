"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging

from app.utils.time import utc_now
from app.utils.insurance_billing import (
    INSURANCE_BILLING_LAUNCH_CUTOFF,
    insurance_next_payment_due,
    should_reset_legacy_billing_cycle,
)


def enforce_daily_limits_job():
    """
    Scheduled job that checks all active students and auto-taps them out if they've exceeded their daily limit.
    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    # Import here to avoid circular imports
    from app.models import Student, TapEvent
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled auto tap-out enforcement job")

    try:
        # Load all students into memory first to avoid named cursor issues
        # yield_per() creates a server-side cursor that gets invalidated by commit()
        students = Student.query.all()
        checked_count = 0
        tapped_out_count = 0

        for student in students:
            try:
                # Get the student's current active sessions
                student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
                has_active_session = False

                for period in student_blocks:
                    latest_event = (
                        TapEvent.query
                        .filter_by(student_id=student.id, period=period)
                        .order_by(TapEvent.timestamp.desc())
                        .first()
                    )

                    # If student is active, check their limit
                    if latest_event and latest_event.status == "active":
                        has_active_session = True
                        break

                if has_active_session:
                    checked_count += 1
                    # Get the latest event ID before running check
                    latest_before = TapEvent.query.filter_by(
                        student_id=student.id
                    ).order_by(TapEvent.timestamp.desc()).first()

                    check_and_auto_tapout_if_limit_reached(student, commit=False)

                    # Check if a new tap-out event was created
                    latest_after = TapEvent.query.filter_by(
                        student_id=student.id
                    ).order_by(TapEvent.timestamp.desc()).first()

                    if latest_after and (latest_before is None or latest_after.id != latest_before.id):
                        if latest_after.status == "inactive":
                            tapped_out_count += 1
                            logger.info(f"Auto-tapped out student {student.id} ({student.full_name})")

                # Commit after successfully processing this student so previous students' work is preserved
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error checking student {student.id}: {e}", exc_info=True)
                continue
        logger.info(f"Auto tap-out job completed. Checked {checked_count} active students, tapped out {tapped_out_count}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Auto tap-out job failed: {e}", exc_info=True)


def cleanup_expired_demo_sessions_job():
    """
    Scheduled job that cleans up expired demo student sessions.
    Runs every 5 minutes to remove demo sessions that have exceeded the 10-minute timeout.
    """
    # Import here to avoid circular imports
    from app.models import DemoStudent
    from app.extensions import db
    from app.utils.demo_sessions import cleanup_demo_student_data

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting demo session cleanup job")

    try:
        now = utc_now()

        # Find all active demo sessions that have expired
        expired_sessions = DemoStudent.query.filter(
            DemoStudent.is_active == True,
            DemoStudent.expires_at < now
        ).all()

        cleaned_count = 0
        for demo_session in expired_sessions:
            try:
                session_id = demo_session.session_id

                cleanup_demo_student_data(demo_session)

                db.session.commit()
                cleaned_count += 1
                logger.info(
                    "Cleaned up expired demo session %s (student_id=%s)",
                    session_id,
                    demo_session.student_id,
                )

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error cleaning up demo session {demo_session.session_id}: {e}", exc_info=True)
                continue

        if cleaned_count > 0:
            logger.info(f"Demo session cleanup completed. Cleaned up {cleaned_count} expired sessions")

    except Exception as e:
        logger.error(f"Demo session cleanup job failed: {e}", exc_info=True)


def database_maintenance_job():
    """
    Scheduled job that performs nightly database maintenance tasks.
    Runs at 2 AM UTC to clean up orphaned entries and maintain data integrity.
    """
    # Import here to avoid circular imports
    from sqlalchemy import and_, or_, tuple_
    from app.models import StoreItemBlock, TeacherBlock, StoreItem
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly database maintenance job")

    total_cleaned = 0

    try:
        # Task 1: Clean up orphaned StoreItemBlock entries
        # These are blocks that reference classes that no longer exist
        logger.info("Checking for orphaned StoreItemBlock entries...")
        
        orphaned_entries_subq = (
            db.session.query(
                StoreItemBlock.store_item_id.label("store_item_id"),
                StoreItemBlock.block.label("block"),
            )
            .outerjoin(StoreItem, StoreItem.id == StoreItemBlock.store_item_id)
            .outerjoin(
                TeacherBlock,
                and_(
                    TeacherBlock.teacher_id == StoreItem.teacher_id,
                    TeacherBlock.block == StoreItemBlock.block,
                ),
            )
            .filter(
                or_(
                    StoreItem.id.is_(None),
                    TeacherBlock.id.is_(None),
                )
            )
            .distinct()
            .subquery()
        )

        orphaned_count = db.session.query(orphaned_entries_subq).count()
        if orphaned_count:
            logger.info("Found %s orphaned StoreItemBlock entries", orphaned_count)
            total_cleaned = (
                StoreItemBlock.query
                .filter(
                    tuple_(StoreItemBlock.store_item_id, StoreItemBlock.block).in_(
                        db.session.query(
                            orphaned_entries_subq.c.store_item_id,
                            orphaned_entries_subq.c.block,
                        )
                    )
                )
                .delete(synchronize_session=False)
            )
            db.session.commit()
            logger.info("Cleaned up %s orphaned StoreItemBlock entries", total_cleaned)
        else:
            logger.info("No orphaned StoreItemBlock entries found")

        logger.info(
            "Skipping legacy join_code backfill in nightly maintenance; "
            "records are expected to already be join_code-scoped."
        )
        logger.info(f"Database maintenance completed. Total orphaned entries cleaned: {total_cleaned}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database maintenance job failed: {e}", exc_info=True)


def reset_insurance_billing_cycles(now=None):
    """Give pre-launch active enrollments one fresh billing cycle before enforcement begins."""
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload
    from app.extensions import db
    from app.models import StudentInsurance

    logger = logging.getLogger('scheduled_tasks')
    now = now or utc_now()

    active_enrollments = (
        StudentInsurance.query
        .options(joinedload(StudentInsurance.policy))
        .filter(
            StudentInsurance.status == 'active',
            StudentInsurance.purchase_date < INSURANCE_BILLING_LAUNCH_CUTOFF,
            or_(
                StudentInsurance.next_payment_due.is_(None),
                StudentInsurance.next_payment_due <= now,
            ),
        )
        .all()
    )

    reset_count = 0
    for enrollment in active_enrollments:
        if not should_reset_legacy_billing_cycle(enrollment, now):
            continue

        enrollment.last_payment_date = now
        enrollment.next_payment_due = insurance_next_payment_due(
            now,
            enrollment.policy.charge_frequency if enrollment.policy else None,
        )
        enrollment.payment_current = True
        enrollment.days_unpaid = 0
        reset_count += 1

    if reset_count:
        db.session.commit()
        logger.info("Reset %s active insurance enrollments to a fresh billing cycle", reset_count)
    else:
        logger.info("No legacy insurance enrollments required billing cycle reset")

    return reset_count


def _charge_insurance_enrollment(enrollment, now):
    """Create the recurring premium transaction and advance billing dates."""
    from app.extensions import db
    from app.models import Transaction, TransactionStatus

    premium_amount = enrollment.contract_premium
    if premium_amount is None:
        raise ValueError(f"Enrollment {enrollment.id} has no contract premium")

    teacher_id = enrollment.policy.teacher_id if enrollment.policy else None

    db.session.add(Transaction(
        student_id=enrollment.student_id,
        teacher_id=teacher_id,
        join_code=enrollment.join_code,
        amount=-premium_amount,
        account_type='checking',
        status=TransactionStatus.PENDING,
        type='insurance_premium',
        description=f"Insurance premium: {enrollment.contract_title}",
        policy_id=enrollment.policy_id,
    ))

    enrollment.last_payment_date = now
    enrollment.next_payment_due = insurance_next_payment_due(
        now,
        enrollment.policy.charge_frequency if enrollment.policy else None,
    )
    enrollment.payment_current = True
    enrollment.days_unpaid = 0


def process_insurance_billing_job(now=None):
    """Charge or mark due insurance enrollments once their premium date arrives."""
    from sqlalchemy.orm import joinedload
    from app.extensions import db
    from app.models import StudentInsurance

    logger = logging.getLogger('scheduled_tasks')
    now = now or utc_now()

    logger.info("Starting insurance billing job")

    try:
        reset_insurance_billing_cycles(now=now)

        due_enrollments = (
            StudentInsurance.query
            .options(
                joinedload(StudentInsurance.student),
                joinedload(StudentInsurance.policy),
            )
            .filter(
                StudentInsurance.status == 'active',
                StudentInsurance.next_payment_due.isnot(None),
                StudentInsurance.next_payment_due <= now,
            )
            .all()
        )

        charged_count = 0
        overdue_count = 0
        cancelled_count = 0

        for enrollment in due_enrollments:
            try:
                policy = enrollment.policy
                if not policy:
                    logger.warning("Skipping insurance enrollment %s with missing policy", enrollment.id)
                    continue

                if policy.autopay:
                    balance = enrollment.student.get_checking_balance(
                        teacher_id=policy.teacher_id,
                        join_code=enrollment.join_code,
                    )
                    premium_amount = enrollment.contract_premium
                    if premium_amount is not None and balance >= premium_amount:
                        _charge_insurance_enrollment(enrollment, now)
                        db.session.commit()
                        charged_count += 1
                        continue

                enrollment.days_unpaid = max(
                    0,
                    (now.date() - enrollment.next_payment_due.date()).days,
                )
                enrollment.payment_current = False
                overdue_count += 1

                cancel_threshold = policy.auto_cancel_nonpay_days or 0
                if cancel_threshold > 0 and enrollment.days_unpaid >= cancel_threshold:
                    enrollment.status = 'cancelled'
                    enrollment.cancel_date = now
                    cancelled_count += 1

                db.session.commit()
            except Exception as enroll_exc:
                db.session.rollback()
                logger.error(
                    "Error processing insurance enrollment %s: %s",
                    enrollment.id,
                    enroll_exc,
                    exc_info=True,
                )

        logger.info(
            "Insurance billing job completed. Charged %s enrollments, marked %s overdue, cancelled %s",
            charged_count,
            overdue_count,
            cancelled_count,
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Insurance billing job failed: {e}", exc_info=True)


def init_scheduled_tasks(app):
    """
    Initialize and start scheduled tasks.

    Args:
        app: Flask application instance
    """
    from app.extensions import scheduler

    logger = logging.getLogger('scheduled_tasks')

    # Wrapper function that runs the enforce_daily_limits_job with Flask app context
    def run_enforce_daily_limits():
        with app.app_context():
            enforce_daily_limits_job()

    # Wrapper function that runs the cleanup_expired_demo_sessions_job with Flask app context
    def run_cleanup_demo_sessions():
        with app.app_context():
            cleanup_expired_demo_sessions_job()

    # Wrapper function that runs the database_maintenance_job with Flask app context
    def run_database_maintenance():
        with app.app_context():
            database_maintenance_job()

    def run_insurance_billing():
        with app.app_context():
            process_insurance_billing_job()

    if not scheduler.running:
        # Add the auto tap-out enforcement job to run every hour
        scheduler.add_job(
            func=run_enforce_daily_limits,
            trigger='interval',
            hours=1,
            id='enforce_daily_limits',
            name='Enforce daily attendance limits',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        # Add the demo session cleanup job to run every 5 minutes
        scheduler.add_job(
            func=run_cleanup_demo_sessions,
            trigger='interval',
            minutes=5,
            id='cleanup_demo_sessions',
            name='Clean up expired demo sessions',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        # Add the database maintenance job to run nightly at 2 AM UTC
        scheduler.add_job(
            func=run_database_maintenance,
            trigger='cron',
            hour=2,
            minute=0,
            id='database_maintenance',
            name='Nightly database maintenance',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        scheduler.add_job(
            func=run_insurance_billing,
            trigger='cron',
            hour=0,
            minute=5,
            id='process_insurance_billing',
            name='Process insurance billing',
            replace_existing=True,
            max_instances=1
        )

        scheduler.start()
        logger.info(
            "Scheduled tasks initialized: auto tap-out (hourly), demo cleanup (5 min), "
            "insurance billing (12:05 AM UTC daily), database maintenance (2 AM UTC daily)"
        )
    else:
        logger.info("Scheduler already running")
