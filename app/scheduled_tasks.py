"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
from datetime import datetime, timezone
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

        scheduler.start()
        logger.info("Scheduled tasks initialized: auto tap-out (hourly), database maintenance (2 AM UTC daily)")
    else:
        logger.info("Scheduler already running")
