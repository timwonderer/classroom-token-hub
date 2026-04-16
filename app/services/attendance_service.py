from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytz
from flask import current_app
from sqlalchemy import func, and_

from app.extensions import db
from app.models import HallPassLog, StudentTeacher, TapEvent, TeacherBlock
from app.utils.attendance_helpers import get_join_code_for_student_period
from app.utils.seat_scope import get_seat_ids_for_student_join, seat_scoped_filter
from app.utils.time import ensure_utc, normalize_for_db, utc_now


def calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=None):
    """Calculate unpaid attendance from a caller-supplied payroll anchor."""
    last_payroll_time = ensure_utc(last_payroll_time)
    seat_ids = get_seat_ids_for_student_join(student_id, join_code) if join_code else []
    tap_scope = seat_scoped_filter(TapEvent, student_id, seat_ids)

    base_query = TapEvent.query.filter(
        tap_scope,
        TapEvent.period == period,
        TapEvent.is_deleted == False,
    )

    if join_code:
        base_query = base_query.filter(TapEvent.join_code == join_code)

    base_query = base_query.order_by(TapEvent.timestamp.asc())

    if not last_payroll_time:
        events = base_query.all()
        in_time = None
        total_seconds = 0
        for event in events:
            event_time = ensure_utc(event.timestamp)
            if event.status == "active":
                in_time = event_time
            elif event.status == "inactive" and in_time:
                total_seconds += (event_time - in_time).total_seconds()
                in_time = None
        if in_time:
            total_seconds += (utc_now() - in_time).total_seconds()
        return int(total_seconds)

    last_event_before_payroll = TapEvent.query.filter(
        tap_scope,
        TapEvent.period == period,
        TapEvent.timestamp <= last_payroll_time,
        TapEvent.is_deleted == False,
    ).order_by(TapEvent.timestamp.desc()).first()

    events_after_payroll = base_query.filter(TapEvent.timestamp > last_payroll_time).all()

    total_seconds = 0
    in_time = last_payroll_time if last_event_before_payroll and last_event_before_payroll.status == "active" else None

    for event in events_after_payroll:
        event_time = ensure_utc(event.timestamp)
        if event.status == "active":
            if in_time is None:
                in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    if in_time:
        total_seconds += (utc_now() - in_time).total_seconds()
    return int(total_seconds)


def get_all_block_statuses(student, join_code=None, payroll_anchor_by_join_code=None):
    """Return attendance facts only for the student's active blocks."""
    pacific = pytz.timezone("America/Los_Angeles")
    now_pacific = utc_now().astimezone(pacific)
    today_pacific = now_pacific.date()
    today_start_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
    today_start_utc = today_start_pacific.astimezone(timezone.utc)
    today_end_utc = (today_start_pacific + timedelta(days=1)).astimezone(timezone.utc)

    if join_code:
        claimed_seats = TeacherBlock.query.filter_by(
            student_id=student.id,
            join_code=join_code,
            is_claimed=True,
        ).all()
        student_blocks = [seat.block.strip() for seat in claimed_seats if seat.block]
        join_scope_seat_ids = get_seat_ids_for_student_join(student.id, join_code)
    else:
        student_blocks = [b.strip() for b in student.block.split(",") if b.strip()]
        join_scope_seat_ids = []

    period_states = {}
    payroll_anchor_by_join_code = payroll_anchor_by_join_code or {}

    for block_original in student_blocks:
        blk = block_original.upper()
        block_join_code = join_code or get_join_code_for_student_period(student.id, block_original)
        block_seat_ids = get_seat_ids_for_student_join(student.id, block_join_code) if block_join_code else []

        latest_event_query = TapEvent.query.filter_by(period=blk, is_deleted=False)
        if block_join_code:
            latest_event_query = latest_event_query.filter(
                seat_scoped_filter(TapEvent, student.id, block_seat_ids),
                TapEvent.join_code == block_join_code,
            )
        else:
            latest_event_query = latest_event_query.filter(TapEvent.student_id == student.id)

        latest_event = latest_event_query.order_by(TapEvent.timestamp.desc()).first()
        is_active = latest_event.status == "active" if latest_event else False

        done_query = TapEvent.query.filter(
            TapEvent.period == blk,
            TapEvent.timestamp >= today_start_utc,
            TapEvent.timestamp < today_end_utc,
            TapEvent.reason != None,
            TapEvent.is_deleted == False,
        )
        if block_join_code:
            done_query = done_query.filter(
                seat_scoped_filter(TapEvent, student.id, block_seat_ids),
                TapEvent.join_code == block_join_code,
            )
        else:
            done_query = done_query.filter(TapEvent.student_id == student.id)

        done = done_query.filter(func.lower(TapEvent.reason).in_(["done", "done for the day"])).first() is not None
        duration = calculate_unpaid_attendance_seconds(
            student.id,
            blk,
            payroll_anchor_by_join_code.get(block_join_code),
            join_code=block_join_code,
        )

        hall_pass = None
        active_pass_query = HallPassLog.query.filter_by(student_id=student.id, period=blk)
        if block_join_code:
            active_pass_query = active_pass_query.filter_by(join_code=block_join_code)

        active_pass = active_pass_query.filter(
            HallPassLog.status.in_(["pending", "approved", "left", "rejected"])
        ).order_by(HallPassLog.request_time.desc()).first()
        if active_pass:
            hall_pass = {"id": active_pass.id, "status": active_pass.status, "reason": active_pass.reason}

        period_states[blk] = {
            "active": is_active,
            "done": done,
            "duration": duration,
            "projected_pay": None,
            "hall_pass": hall_pass,
        }

    return period_states


def calculate_period_attendance(student_id, period, date):
    """
    Calculates total attendance seconds for a student in a specific period
    on a specific date. Used for daily attendance reporting.
    NOTE: This uses a UTC range; for Pacific timezone daily limits use
    calculate_period_attendance_utc_range instead.
    """
    start_utc = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return calculate_period_attendance_utc_range(student_id, period, start_utc, end_utc)


def calculate_period_attendance_utc_range(student_id, period, start_utc, end_utc):
    """
    Calculates total attendance seconds for a student in a specific period
    within a UTC datetime range. Use this for timezone-aware daily limits.
    """
    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

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


def get_session_status(student_id, period, *, last_payroll_time, join_code=None):
    """
    Return (is_active, done, duration) for a student/period.

    Callers must supply last_payroll_time so this function remains a pure
    attendance fact query with no internal ledger dependency.
    """
    today = utc_now().date()

    if join_code is None:
        join_code = get_join_code_for_student_period(student_id, period)

    latest_event_query = TapEvent.query.filter_by(period=period, is_deleted=False)
    if join_code:
        seat_ids = get_seat_ids_for_student_join(student_id, join_code)
        latest_event_query = latest_event_query.filter(
            seat_scoped_filter(TapEvent, student_id, seat_ids),
            TapEvent.join_code == join_code,
        )
    else:
        latest_event_query = latest_event_query.filter(TapEvent.student_id == student_id)
    latest_event = latest_event_query.order_by(TapEvent.timestamp.desc()).first()
    is_active = latest_event.status == "active" if latest_event else False

    done_query = TapEvent.query.filter(
        TapEvent.period == period,
        func.date(TapEvent.timestamp) == today,
        TapEvent.reason != None,
        TapEvent.is_deleted == False,
    )
    if join_code:
        seat_ids = get_seat_ids_for_student_join(student_id, join_code)
        done_query = done_query.filter(
            seat_scoped_filter(TapEvent, student_id, seat_ids),
            TapEvent.join_code == join_code,
        )
    else:
        done_query = done_query.filter(TapEvent.student_id == student_id)
    done = done_query.filter(
        func.lower(TapEvent.reason).in_(["done", "done for the day"])
    ).first() is not None

    duration = calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=join_code)
    return is_active, done, duration


def get_batch_attendance_events(student_ids, min_anchor, allowed_join_codes=None):
    """
    Fetch all relevant tap events for the given students after min_anchor.
    Also determines if they were 'active' right before min_anchor.
    Returns a dict: (student_id, period_upper, join_code) -> list of TapEvent

    SECURITY: Pass allowed_join_codes to restrict results to a specific tenant's
    class periods. Without this filter the query returns events from every class
    the students are enrolled in, including those owned by other teachers.
    """
    query = TapEvent.query.filter(
        TapEvent.student_id.in_(student_ids),
        TapEvent.is_deleted == False,
    )

    if allowed_join_codes is not None:
        query = query.filter(TapEvent.join_code.in_(allowed_join_codes))

    if min_anchor:
        query = query.filter(TapEvent.timestamp > min_anchor)

    events = query.order_by(TapEvent.timestamp.asc()).all()

    grouped = {}
    for e in events:
        key = (e.student_id, (e.period or "").upper(), e.join_code)
        grouped.setdefault(key, []).append(e)

    if min_anchor:
        pre_anchor_query = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
            func.max(TapEvent.timestamp).label("max_ts"),
        ).filter(
            TapEvent.student_id.in_(student_ids),
            TapEvent.timestamp <= min_anchor,
            TapEvent.is_deleted == False,
        )

        if allowed_join_codes is not None:
            pre_anchor_query = pre_anchor_query.filter(TapEvent.join_code.in_(allowed_join_codes))

        subquery = pre_anchor_query.group_by(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
        ).subquery()

        initial_states = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.join_code,
            TapEvent.status,
            TapEvent.timestamp,
        ).join(
            subquery,
            and_(
                TapEvent.student_id == subquery.c.student_id,
                TapEvent.period == subquery.c.period,
                TapEvent.join_code == subquery.c.join_code,
                TapEvent.timestamp == subquery.c.max_ts,
            ),
        ).filter(TapEvent.is_deleted == False).all()

        for row in initial_states:
            s_id, period, status, ts = row.student_id, row.period, row.status, row.timestamp
            jc = row.join_code
            if status == "active":
                key = (s_id, (period or "").upper(), jc)
                virtual_start_time = ensure_utc(min_anchor)
                mock_event = TapEvent(
                    student_id=s_id,
                    period=period,
                    join_code=jc,
                    status="active",
                    timestamp=virtual_start_time,
                )
                grouped.setdefault(key, []).insert(0, mock_event)

    return grouped


def calculate_seconds_in_memory(events, anchor):
    """Calculate unpaid seconds from a sorted list of events, strictly after anchor."""
    total_seconds = 0
    in_time = None

    anchor = ensure_utc(anchor)

    for event in events:
        event_time = ensure_utc(event.timestamp)

        if anchor and event_time <= anchor:
            if event.status == "active":
                in_time = event_time
            else:
                in_time = None
            continue

        if in_time and in_time < anchor:
            in_time = anchor

        if event.status == "active":
            if in_time is None:
                in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    if in_time:
        if anchor and in_time < anchor:
            in_time = anchor
        now = utc_now()
        total_seconds += (now - in_time).total_seconds()

    return int(total_seconds)


def batch_auto_tapout_students(admin_id):
    """
    Optimized batch auto-tapout that processes all students for an admin.
    Returns the count of students tapped out.
    """
    from app.models import Student, TapEventReasonCode, StudentBlock, PayrollSettings, StudentTeacher, TeacherBlock

    student_ids = [
        row[0] for row in db.session.query(StudentTeacher.student_id)
        .filter(StudentTeacher.teacher_id == admin_id)
        .distinct()
        .all()
    ]

    if not student_ids:
        return 0

    admin_join_codes = [
        row[0] for row in db.session.query(TeacherBlock.join_code)
        .filter(
            TeacherBlock.teacher_id == admin_id,
            TeacherBlock.join_code.isnot(None),
        )
        .distinct()
        .all()
    ]

    if not admin_join_codes:
        return 0

    import pytz as _pytz
    pacific = _pytz.timezone("America/Los_Angeles")
    now_utc = utc_now()
    now_pacific = now_utc.astimezone(pacific)
    today_pacific = now_pacific.date()

    start_of_day_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
    start_of_day_utc = start_of_day_pacific.astimezone(timezone.utc)

    events_map = get_batch_attendance_events(student_ids, start_of_day_utc, allowed_join_codes=admin_join_codes)

    lookup = {}
    for (sid, per, jc), evts in events_map.items():
        lookup.setdefault(sid, {}).setdefault(per, []).append((jc, evts))

    payroll_settings = PayrollSettings.query.filter_by(teacher_id=admin_id, is_active=True).all()
    limits_map = {}

    def get_limit(setting):
        if not setting:
            return None
        if setting.settings_mode == "simple" and setting.daily_limit_hours:
            return int(setting.daily_limit_hours * 3600)
        elif setting.settings_mode == "advanced" and setting.max_time_per_day:
            multiplier = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}.get(
                setting.max_time_per_day_unit, 3600
            )
            return int(setting.max_time_per_day * multiplier)
        return None

    global_setting = next((s for s in payroll_settings if s.block is None), None)
    global_limit = get_limit(global_setting)

    for s in payroll_settings:
        if s.block:
            limit = get_limit(s)
            if limit is not None:
                limits_map[s.block.upper()] = limit

    students = Student.query.filter(Student.id.in_(student_ids)).all()
    student_blocks_lookup = {
        (sb.student_id, (sb.period or "").strip().upper()): sb
        for sb in StudentBlock.query.filter(StudentBlock.student_id.in_(student_ids)).all()
    }

    tapped_out_count = 0

    for student in students:
        student_blocks = [b.strip().upper() for b in (student.block or "").split(",") if b.strip()]

        for period in student_blocks:
            entries = lookup.get(student.id, {}).get(period, [])

            for join_code, events in entries:
                if not events:
                    continue

                last_event = events[-1]
                if last_event.status != "active":
                    continue

                duration = calculate_seconds_in_memory(events, start_of_day_utc)
                limit = limits_map.get(period, global_limit)

                if limit and duration >= limit:
                    hours_limit = limit / 3600.0
                    overage = duration - limit
                    tapout_ts = now_utc - timedelta(seconds=max(0, overage))
                    if tapout_ts > now_utc:
                        tapout_ts = now_utc

                    new_event = TapEvent(
                        student_id=student.id,
                        period=period,
                        status="inactive",
                        timestamp=tapout_ts,
                        reason=f"Daily limit ({hours_limit:.1f}h) reached",
                        reason_code=TapEventReasonCode.DAILY_LIMIT,
                        join_code=join_code,
                    )
                    db.session.add(new_event)
                    tapped_out_count += 1

                    sb = student_blocks_lookup.get((student.id, period))
                    if not sb:
                        sb = StudentBlock(
                            student_id=student.id,
                            period=period,
                            tap_enabled=True,
                            join_code=join_code,
                        )
                        db.session.add(sb)
                        student_blocks_lookup[(student.id, period)] = sb
                    sb.done_for_day_date = today_pacific

    if tapped_out_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing batch auto-tapout: {e}", exc_info=True)
            return 0

    return tapped_out_count
