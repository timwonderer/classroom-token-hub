"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
from datetime import datetime, timezone, timedelta
from app.utils.time import utc_now


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


def _derive_cycle_length_days(settings) -> int:
    """Resolve cycle length in days from rent settings."""
    configured = int(getattr(settings, "cycle_length_days", 0) or 0)
    if configured > 0:
        return configured

    frequency = (getattr(settings, "frequency_type", "monthly") or "monthly").lower()
    if frequency == "daily":
        return 1
    if frequency == "weekly":
        return 7
    if frequency == "custom":
        unit = (getattr(settings, "custom_frequency_unit", "days") or "days").lower()
        value = int(getattr(settings, "custom_frequency_value", 1) or 1)
        if unit.startswith("week"):
            return max(1, value * 7)
        if unit.startswith("month"):
            return max(1, value * 30)
        return max(1, value)
    return 30


def _normalize_cycle_start(execution_time, rent_effective_at, cycle_length_days: int):
    """
    Normalize execution time to the deterministic class cycle boundary.

    This guarantees one idempotency key and one coverage window per cycle
    even if scheduler invocations drift within the same cycle.
    """
    if execution_time <= rent_effective_at:
        return rent_effective_at

    cycle_seconds = max(1, int(cycle_length_days)) * 86400
    elapsed_seconds = (execution_time - rent_effective_at).total_seconds()
    cycle_index = int(elapsed_seconds // cycle_seconds)
    return rent_effective_at + timedelta(seconds=cycle_index * cycle_seconds)


def run_rent_cycle_for_class(class_id: str, execution_time):
    """
    Execute one rent cycle for one class.

    Actor model: seat_id + class_id only.
    """
    from app.extensions import db
    from app.models import RentSettings, RentPayment, Seat
    from app.feats.rent_cycle_feat import execute_scheduled_rent_charge

    execution_time = execution_time or utc_now()

    settings = (
        RentSettings.query
        .filter_by(class_id=class_id, is_enabled=True)
        .order_by(RentSettings.updated_at.desc())
        .first()
    )
    if not settings:
        return {"status": "skipped", "reason": "rent_disabled_or_missing", "class_id": class_id}

    cycle_length_days = _derive_cycle_length_days(settings)
    settings.cycle_length_days = cycle_length_days

    rent_configured_at = settings.rent_configured_at or settings.updated_at or utc_now()
    if not settings.rent_effective_at:
        settings.rent_effective_at = rent_configured_at + timedelta(days=cycle_length_days)
        db.session.flush()

    rent_effective_at = settings.rent_effective_at
    if execution_time < rent_effective_at:
        return {"status": "skipped", "reason": "before_effective_at", "class_id": class_id}

    # Freeze cycle boundary for the full class execution.
    cycle_start = _normalize_cycle_start(execution_time, rent_effective_at, cycle_length_days)

    claimed_seats = Seat.query.filter(
        Seat.class_id == class_id,
        Seat.claimed_at.is_not(None),
    ).all()

    charged = 0
    exempted = 0
    skipped_existing = 0

    for seat in claimed_seats:
        if (
            seat.claimed_at
            and seat.claimed_at >= rent_configured_at
            and not seat.has_received_rent_exemption
        ):
            seat.has_received_rent_exemption = True
            exempted += 1
            continue

        idem_key = f"rent_cycle:{class_id}:{seat.id}:{cycle_start.isoformat()}"
        existing = RentPayment.query.filter_by(
            class_id=class_id,
            seat_id=seat.id,
            cycle_idempotency_key=idem_key,
        ).first()
        if existing:
            skipped_existing += 1
            continue

        execute_scheduled_rent_charge(
            seat=seat,
            settings=settings,
            class_id=class_id,
            execution_time=cycle_start,
            idempotency_key=idem_key,
        )
        charged += 1

    db.session.commit()
    return {
        "status": "ok",
        "class_id": class_id,
        "charged": charged,
        "exempted": exempted,
        "skipped_existing": skipped_existing,
    }


def run_rent_cycle_scheduler(execution_time=None):
    """
    Iterate all rent-enabled classes and execute one rent cycle per class.
    """
    from app.models import RentSettings

    execution_time = execution_time or utc_now()
    class_ids = [
        class_id for (class_id,) in
        RentSettings.query.filter(
            RentSettings.is_enabled.is_(True),
            RentSettings.class_id.is_not(None),
        ).with_entities(RentSettings.class_id).distinct().all()
    ]

    outcomes = []
    for class_id in class_ids:
        outcomes.append(run_rent_cycle_for_class(class_id, execution_time))
    return outcomes


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

    # Wrapper function that runs the database_maintenance_job with Flask app context
    def run_database_maintenance():
        with app.app_context():
            database_maintenance_job()

    def run_scheduled_rent_cycles():
        with app.app_context():
            run_rent_cycle_scheduler()

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
            func=run_scheduled_rent_cycles,
            trigger='cron',
            hour='*',
            minute=5,
            id='run_rent_cycles',
            name='Run class-scoped rent cycles',
            replace_existing=True,
            max_instances=1
        )

        scheduler.start()
        logger.info("Scheduled tasks initialized: auto tap-out (hourly), database maintenance (2 AM UTC daily), rent cycles (hourly)")
    else:
        logger.info("Scheduler already running")
