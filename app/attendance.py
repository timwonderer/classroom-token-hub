from datetime import datetime, timezone, timedelta
from app.utils.time import utc_now, ensure_utc, normalize_for_db, day_bounds_utc, class_date
from sqlalchemy import func
from flask import current_app
from app.extensions import db
import pytz
# Import from shared utilities to avoid circular dependency with payroll.py
from app.utils.attendance_helpers import get_join_code_for_student_period
from app.utils.seat_scope import get_seat_ids_for_student_join, get_seat_id_for_class
from app.services.attendance_service import (
    calculate_unpaid_attendance_seconds as _calculate_unpaid_attendance_seconds,
    get_all_block_statuses as _get_all_block_statuses,
)
from app.services.ledger_service import get_last_payroll_time as _get_last_payroll_time
from app.models import ClassEconomy, Transaction

def get_last_payroll_time(student_id=None, join_code=None):
    """Compatibility wrapper around the ledger-owned payroll anchor query."""
    class_id = None
    seat_id = None
    if join_code:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = class_row.class_id if class_row else None
        if class_id is None:
            legacy_filters = [
                Transaction.join_code == join_code,
                Transaction.type.in_(["payroll", "manual_payment"]),
            ]
            if student_id is not None:
                legacy_filters.append(Transaction.student_id == student_id)
            tx = Transaction.query.filter(*legacy_filters).order_by(Transaction.timestamp.desc()).first()
            return ensure_utc(tx.timestamp) if tx else None
    if student_id and class_id:
        seat_id = get_seat_id_for_class(student_id, class_id)
    if student_id and not class_id:
        tx = (
            Transaction.query
            .filter(
                Transaction.student_id == student_id,
                Transaction.type.in_(["payroll", "manual_payment"]),
            )
            .order_by(Transaction.timestamp.desc())
            .first()
        )
        return ensure_utc(tx.timestamp) if tx else None
    return _get_last_payroll_time(seat_id=seat_id, class_id=class_id)



def calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=None):
    """Compatibility wrapper around the attendance-owned time calculation."""
    class_id = None
    seat_id = None
    if join_code:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = class_row.class_id if class_row else None
    if student_id and class_id:
        seat_id = get_seat_id_for_class(student_id, class_id)
    if not seat_id or not class_id:
        from app.models import TapEvent
        base_query = TapEvent.query.filter(
            TapEvent.student_id == student_id,
            TapEvent.period == period,
            TapEvent.is_deleted == False,
        )
        if join_code:
            base_query = base_query.filter(TapEvent.join_code == join_code)
        events = base_query.order_by(TapEvent.timestamp.asc()).all()

        if not events:
            return 0

        last_payroll_time = ensure_utc(last_payroll_time)
        if not last_payroll_time:
            total_seconds = 0
            in_time = None
            for event in events:
                event_time = ensure_utc(event.timestamp)
                if event.status == "active":
                    in_time = event_time
                elif event.status == "inactive" and in_time:
                    total_seconds += (event_time - in_time).total_seconds()
                    in_time = None
            return int(total_seconds)

        last_event_before_payroll = (
            base_query
            .filter(TapEvent.timestamp <= last_payroll_time)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        if last_event_before_payroll and last_event_before_payroll.status == "active":
            synthetic_event = type("SyntheticEvent", (), {})()
            synthetic_event.timestamp = last_payroll_time
            synthetic_event.status = "active"
            post_events = base_query.filter(TapEvent.timestamp > last_payroll_time).order_by(TapEvent.timestamp.asc()).all()
            events = [synthetic_event] + post_events
        else:
            events = base_query.filter(TapEvent.timestamp > last_payroll_time).order_by(TapEvent.timestamp.asc()).all()

        total_seconds = 0
        in_time = None
        for event in events:
            event_time = ensure_utc(event.timestamp)
            if event.status == "active":
                in_time = event_time
            elif event.status == "inactive" and in_time:
                total_seconds += (event_time - in_time).total_seconds()
                in_time = None
        return int(total_seconds)
    return _calculate_unpaid_attendance_seconds(
        seat_id,
        class_id,
        period,
        last_payroll_time,
    )


def calculate_period_attendance(student_or_seat_id, period_or_class_id, date_or_period, date=None):
    """
    Calculates total attendance seconds for a student in a specific period
    on a specific date. Used for daily attendance reporting.
    NOTE: This uses UTC day boundaries.
    For class-timezone daily limits, use calculate_period_attendance_utc_range instead.
    """
    from app.models import TapEvent

    # Backward-compatible argument parsing:
    # - New: (seat_id, class_id, period, date)
    # - Legacy: (student_id, period, date)
    student_id = None
    if date is None:
        student_id = student_or_seat_id
        period = period_or_class_id
        date = date_or_period
        join_code = get_join_code_for_student_period(student_id, period)
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first() if join_code else None
        class_id = class_row.class_id if class_row else None
        seat_id = get_seat_id_for_class(student_id, class_id) if class_id else None
    else:
        seat_id = student_or_seat_id
        class_id = period_or_class_id
        period = date_or_period

    # Build UTC range for the specified date
    start_utc = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    if not seat_id or not class_id:
        if not student_id:
            return 0
        events = TapEvent.query.filter(
            TapEvent.student_id == student_id,
            TapEvent.period == period,
            TapEvent.timestamp >= start_db,
            TapEvent.timestamp < end_db,
            TapEvent.is_deleted == False,
        ).order_by(TapEvent.timestamp.asc()).all()
        total_seconds = 0
        in_time = None
        for event in events:
            event_time = ensure_utc(event.timestamp)
            if event.status == "active":
                in_time = event_time
            elif event.status == "inactive" and in_time:
                total_seconds += (event_time - in_time).total_seconds()
                in_time = None
        return int(total_seconds)

    # Get all events for this seat/period on the specified date
    events = TapEvent.query.filter(
        TapEvent.seat_id == seat_id,
        TapEvent.class_id == class_id,
        TapEvent.period == period,
        TapEvent.timestamp >= start_db,
        TapEvent.timestamp < end_db,
        TapEvent.is_deleted == False  # Exclude deleted events
    ).order_by(TapEvent.timestamp.asc()).all()

    total_seconds = 0
    in_time = None

    for event in events:
        event_time = ensure_utc(event.timestamp)
        if event.status == "active":
            in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    return int(total_seconds)


def calculate_period_attendance_utc_range(student_or_seat_id, period_or_class_id, start_or_period, end_or_start_utc, end_utc=None):
    """
    Calculates total attendance seconds for a student in a specific period
    within a UTC datetime range. Use this for timezone-aware daily limits.

    Args:
        seat_id: The seat's ID
        class_id: The class's ID
        period: The block/period identifier
        start_utc: Start of period (UTC datetime, inclusive)
        end_utc: End of period (UTC datetime, exclusive)

    Returns:
        int: Total seconds of attendance in the range
    """
    from app.models import TapEvent

    # Backward-compatible argument parsing:
    # - New: (seat_id, class_id, period, start_utc, end_utc)
    # - Legacy: (student_id, period, start_utc, end_utc)
    student_id = None
    if end_utc is None:
        student_id = student_or_seat_id
        period = period_or_class_id
        start_utc = start_or_period
        end_utc = end_or_start_utc
        join_code = get_join_code_for_student_period(student_id, period)
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first() if join_code else None
        class_id = class_row.class_id if class_row else None
        seat_id = get_seat_id_for_class(student_id, class_id) if class_id else None
    else:
        seat_id = student_or_seat_id
        class_id = period_or_class_id
        period = start_or_period
        start_utc = end_or_start_utc

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    if not seat_id or not class_id:
        if not student_id:
            return 0
        events = TapEvent.query.filter(
            TapEvent.student_id == student_id,
            TapEvent.period == period,
            TapEvent.timestamp >= start_db,
            TapEvent.timestamp < end_db,
            TapEvent.is_deleted == False,
        ).order_by(TapEvent.timestamp.asc()).all()
        total_seconds = 0
        in_time = None
        for event in events:
            event_time = ensure_utc(event.timestamp)
            if event.status == "active":
                in_time = event_time
            elif event.status == "inactive" and in_time:
                total_seconds += (event_time - in_time).total_seconds()
                in_time = None
        return int(total_seconds)

    # Get all events in the UTC range
    events = TapEvent.query.filter(
        TapEvent.seat_id == seat_id,
        TapEvent.class_id == class_id,
        TapEvent.period == period,
        TapEvent.timestamp >= start_db,
        TapEvent.timestamp < end_db,
        TapEvent.is_deleted == False  # Exclude deleted events
    ).order_by(TapEvent.timestamp.asc()).all()

    total_seconds = 0
    in_time = None

    for event in events:
        event_time = ensure_utc(event.timestamp)
        if event.status == "active":
            in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    return int(total_seconds)


def get_session_status(student_id, period):
    """
    Gets the current session status for a student in a specific period.
    Returns a tuple of (is_active, done, duration).
    """
    from app.models import TapEvent
    from datetime import datetime, timezone

    today_start_utc, today_end_utc = day_bounds_utc()
    today_start_db = normalize_for_db(today_start_utc)
    today_end_db = normalize_for_db(today_end_utc)
    join_code = get_join_code_for_student_period(student_id, period)

    # Check if student is currently active
    latest_event_query = TapEvent.query.filter_by(period=period, is_deleted=False)
    if join_code:
        seat_ids = get_seat_ids_for_student_join(student_id, join_code)
        if seat_ids:
            latest_event_query = latest_event_query.filter(TapEvent.seat_id.in_(seat_ids))
        else:
            latest_event_query = latest_event_query.filter(TapEvent.student_id == student_id)
        latest_event_query = latest_event_query.filter(TapEvent.join_code == join_code)
    else:
        latest_event_query = latest_event_query.filter(TapEvent.student_id == student_id)
    latest_event = latest_event_query.order_by(TapEvent.timestamp.desc()).first()
    is_active = latest_event.status == "active" if latest_event else False

    # Check if marked as done today
    done_query = TapEvent.query.filter(
        TapEvent.period == period,
        TapEvent.timestamp >= today_start_db,
        TapEvent.timestamp < today_end_db,
        TapEvent.reason != None,
        TapEvent.is_deleted == False  # Exclude deleted events
    )
    if join_code:
        seat_ids = get_seat_ids_for_student_join(student_id, join_code)
        if seat_ids:
            done_query = done_query.filter(TapEvent.seat_id.in_(seat_ids))
        else:
            done_query = done_query.filter(TapEvent.student_id == student_id)
        done_query = done_query.filter(TapEvent.join_code == join_code)
    else:
        done_query = done_query.filter(TapEvent.student_id == student_id)
    done = done_query.filter(
        func.lower(TapEvent.reason).in_(['done', 'done for the day'])
    ).first() is not None

    # Calculate unpaid duration
    last_payroll_time = get_last_payroll_time(student_id=student_id, join_code=join_code)
    duration = calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=join_code)

    return is_active, done, duration


def get_all_block_statuses(student, join_code=None):
    """Compatibility wrapper around the attendance-owned block status query."""
    return _get_all_block_statuses(student, join_code=join_code)

# -------------------------------------------------------------------
# BATCH OPTIMIZATION HELPERS
# -------------------------------------------------------------------

def get_batch_attendance_events(student_ids, min_anchor, allowed_join_codes=None):
    """
    Fetch all relevant tap events for the given students after min_anchor.
    Crucially, also determines if they were 'active' right before min_anchor.
    Returns a dict: (student_id, period_upper, join_code) -> list of TapEvent

    SECURITY: Pass allowed_join_codes to restrict results to a specific tenant's
    class periods. Without this filter the query returns events from every class
    the students are enrolled in, including those owned by other teachers.
    """
    from app.models import TapEvent
    from sqlalchemy import func, and_

    # 1. Fetch all events > min_anchor (if min_anchor exists)
    query = TapEvent.query.filter(
        TapEvent.student_id.in_(student_ids),
        TapEvent.is_deleted == False
    )

    if allowed_join_codes is not None:
        query = query.filter(TapEvent.join_code.in_(allowed_join_codes))

    if min_anchor:
        query = query.filter(TapEvent.timestamp > min_anchor)

    events = query.order_by(TapEvent.timestamp.asc()).all()

    # Group by (student_id, period, join_code)
    grouped = {}
    for e in events:
        key = (e.student_id, (e.period or "").upper(), e.join_code)
        grouped.setdefault(key, []).append(e)

    # 2. If min_anchor exists, we need the "initial state" for each student/period
    # We need the LAST event <= min_anchor for each student/period.
    if min_anchor:
        # Subquery to find the latest timestamp for each student/period/join_code before anchor
        pre_anchor_query = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
            func.max(TapEvent.timestamp).label("max_ts")
        ).filter(
            TapEvent.student_id.in_(student_ids),
            TapEvent.timestamp <= min_anchor,
            TapEvent.is_deleted == False
        )

        if allowed_join_codes is not None:
            pre_anchor_query = pre_anchor_query.filter(TapEvent.join_code.in_(allowed_join_codes))

        subquery = pre_anchor_query.group_by(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
        ).subquery()

        # Join back to get the full event details (status)
        initial_states = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
            TapEvent.status,
            TapEvent.timestamp
        ).join(
            subquery,
            and_(
                TapEvent.student_id == subquery.c.student_id,
                TapEvent.period == subquery.c.period,
                TapEvent.join_code == subquery.c.join_code,
                TapEvent.timestamp == subquery.c.max_ts
            )
        ).filter(
            TapEvent.is_deleted == False
        ).all()

        # Prepend a virtual "start" event if they were active
        for row in initial_states:
            s_id, period, status, ts = row.student_id, row.period, row.status, row.timestamp
            join_code = row.join_code
            if status == 'active':
                key = (s_id, (period or "").upper(), join_code)

                # Virtual start at min_anchor
                virtual_start_time = ensure_utc(min_anchor)

                # Mock object (or partial object)
                mock_event = TapEvent(
                    student_id=s_id,
                    period=period,
                    join_code=join_code,
                    status='active',
                    timestamp=virtual_start_time
                )

                grouped.setdefault(key, []).insert(0, mock_event)

    return grouped

def calculate_seconds_in_memory(events, anchor):
    """
    Calculate unpaid seconds from a sorted list of events, strictly after anchor.
    """
    total_seconds = 0
    in_time = None

    anchor = ensure_utc(anchor)

    for event in events:
        event_time = ensure_utc(event.timestamp)

        # Skip events before specific anchor
        if anchor and event_time <= anchor:
            # If active, it effectively sets in_time for subsequent period
            if event.status == 'active':
                in_time = event_time
            else:
                in_time = None
            continue

        # If we crossed the anchor boundary and in_time was set from a pre-anchor event
        if in_time and in_time < anchor:
            in_time = anchor

        if event.status == 'active':
            if in_time is None:
                in_time = event_time
        elif event.status == 'inactive' and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    # If still active at "now"
    if in_time:
        if anchor and in_time < anchor:
            in_time = anchor

        now = utc_now()
        total_seconds += (now - in_time).total_seconds()

    return int(total_seconds)

def batch_auto_tapout_students(admin_id):
    """
    Optimized version of auto-tapout that processes all students for an admin in batch.
    Returns the count of students tapped out.
    """
    from app.models import Student, TapEvent, TapEventReasonCode, StudentBlock, PayrollSettings, StudentTeacher, TeacherBlock
    from app.extensions import db

    # 1. Get all students for this admin via StudentTeacher
    student_ids = [
        row[0] for row in db.session.query(StudentTeacher.student_id)
        .filter(StudentTeacher.teacher_id == admin_id)
        .distinct()
        .all()
    ]

    if not student_ids:
        return 0

    # 1b. SECURITY: Fetch only the join codes owned by this admin.
    # This prevents reading or writing attendance data for students' other
    # class periods that belong to different teachers.
    admin_join_codes = [
        row[0] for row in db.session.query(TeacherBlock.join_code)
        .filter(
            TeacherBlock.teacher_id == admin_id,
            TeacherBlock.join_code.isnot(None)
        )
        .distinct()
        .all()
    ]

    if not admin_join_codes:
        return 0

    now_utc = utc_now()
    start_of_day_utc, _ = day_bounds_utc(timestamp_utc=now_utc)
    today_local = class_date(timestamp_utc=now_utc)

    # 3. Batch fetch events for today, scoped to this admin's join codes only.
    # events_map: (student_id, period, join_code) -> list[TapEvent]
    events_map = get_batch_attendance_events(student_ids, start_of_day_utc, allowed_join_codes=admin_join_codes)

    # Restructure for faster lookup: student_id -> period -> list of (join_code, events)
    lookup = {}
    for (sid, per, jc), evts in events_map.items():
        lookup.setdefault(sid, {}).setdefault(per, []).append((jc, evts))

    # 4. Batch fetch PayrollSettings
    payroll_settings = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True).all()
    limits_map = {}

    def get_limit(setting):
        if not setting: return None
        if setting.settings_mode == 'simple' and setting.daily_limit_hours:
            return int(setting.daily_limit_hours * 3600)
        elif setting.settings_mode == 'advanced' and setting.max_time_per_day:
            multiplier = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}.get(setting.max_time_per_day_unit, 3600)
            return int(setting.max_time_per_day * multiplier)
        return None

    global_setting = next((s for s in payroll_settings if s.block is None), None)
    global_limit = get_limit(global_setting)

    for s in payroll_settings:
        if s.block:
            limit = get_limit(s)
            if limit is not None:
                limits_map[s.block.upper()] = limit

    # 5. Batch fetch Students to get their blocks
    students = Student.query.filter(Student.id.in_(student_ids)).all()
    student_blocks_lookup = {
        (sb.student_id, (sb.period or "").strip().upper()): sb
        for sb in StudentBlock.query.filter(StudentBlock.student_id.in_(student_ids)).all()
    }

    # 6. Iterate and check
    tapped_out_count = 0

    for student in students:
        student_blocks = [b.strip().upper() for b in (student.block or "").split(',') if b.strip()]

        for period in student_blocks:
            # Check if we have events for this period
            entries = lookup.get(student.id, {}).get(period, [])

            for join_code, events in entries:
                if not events:
                    continue

                last_event = events[-1]
                if last_event.status != 'active':
                    continue

                # Calculate duration today
                duration = calculate_seconds_in_memory(events, start_of_day_utc)

                # Get limit
                limit = limits_map.get(period, global_limit)

                if limit and duration >= limit:
                    # Limit reached. Tap out.
                    hours_limit = limit / 3600.0
                    overage = duration - limit
                    # Timestamp backdated to when limit was reached
                    tapout_ts = now_utc - timedelta(seconds=max(0, overage))
                    if tapout_ts > now_utc: tapout_ts = now_utc

                    # Create TapEvent
                    new_event = TapEvent(
                        student_id=student.id,
                        period=period,
                        status='inactive',
                        timestamp=tapout_ts,
                        reason=f"Daily limit ({hours_limit:.1f}h) reached",
                        reason_code=TapEventReasonCode.DAILY_LIMIT,
                        join_code=join_code
                    )
                    db.session.add(new_event)
                    tapped_out_count += 1

                    # Lock student
                    sb = student_blocks_lookup.get((student.id, period))
                    if not sb:
                        sb = StudentBlock(
                            student_id=student.id,
                            period=period,
                            tap_enabled=True,
                            join_code=join_code
                        )
                        db.session.add(sb)
                        student_blocks_lookup[(student.id, period)] = sb
                    sb.done_for_day_date = today_local

    if tapped_out_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing batch auto-tapout: {e}", exc_info=True)
            return 0

    return tapped_out_count
