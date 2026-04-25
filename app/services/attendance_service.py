from __future__ import annotations

from sqlalchemy import func

from app.models import HallPassLog, StudentTeacher, TapEvent, TeacherBlock
from app.utils.attendance_helpers import get_join_code_for_student_period
from app.utils.seat_scope import get_seat_ids_for_student_join, seat_scoped_filter
from app.utils.time import day_bounds_utc, ensure_utc, normalize_for_db, utc_now


def calculate_unpaid_attendance_seconds(seat_id: int, class_id: str, period: str, last_payroll_time):
    """Calculate unpaid attendance from a caller-supplied payroll anchor."""
    last_payroll_time = ensure_utc(last_payroll_time)
    
    base_query = TapEvent.query.filter(
        TapEvent.seat_id == seat_id,
        TapEvent.class_id == class_id,
        TapEvent.period == period,
        TapEvent.is_deleted == False,
    )

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
        TapEvent.seat_id == seat_id,
        TapEvent.class_id == class_id,
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
    today_start_utc, today_end_utc = day_bounds_utc()
    today_start_db = normalize_for_db(today_start_utc)
    today_end_db = normalize_for_db(today_end_utc)

    from app.utils.attendance_helpers import get_join_code_for_student_period
    from app.utils.seat_scope import get_seat_id_for_class
    from app.models import ClassEconomy

    if join_code:
        economy = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = economy.class_id if economy else None
        claimed_seats = TeacherBlock.query.filter_by(
            student_id=student.id,
            class_id=class_id,
            is_claimed=True,
        ).all()
        student_blocks = [seat.block.strip() for seat in claimed_seats if seat.block]
    else:
        student_blocks = [b.strip() for b in student.block.split(",") if b.strip()]

    period_states = {}
    payroll_anchor_by_join_code = payroll_anchor_by_join_code or {}

    for block_original in student_blocks:
        blk = block_original.upper()
        block_join_code = join_code or get_join_code_for_student_period(student.id, block_original)
        
        if not block_join_code:
            continue

        economy = ClassEconomy.query.filter_by(join_code=block_join_code).first()
        if not economy:
            continue
        
        class_id = economy.class_id
        seat_id = get_seat_id_for_class(student.id, class_id)
        
        if not seat_id:
            continue

        latest_event = TapEvent.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            period=blk,
            is_deleted=False
        ).order_by(TapEvent.timestamp.desc()).first()
        
        is_active = latest_event.status == "active" if latest_event else False

        done = TapEvent.query.filter(
            TapEvent.seat_id == seat_id,
            TapEvent.class_id == class_id,
            TapEvent.period == blk,
            TapEvent.timestamp >= today_start_db,
            TapEvent.timestamp < today_end_db,
            TapEvent.reason != None,
            TapEvent.is_deleted == False,
            func.lower(TapEvent.reason).in_(["done", "done for the day"])
        ).first() is not None

        duration = calculate_unpaid_attendance_seconds(
            seat_id,
            class_id,
            blk,
            payroll_anchor_by_join_code.get(block_join_code),
        )

        active_pass = HallPassLog.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            period=blk
        ).filter(
            HallPassLog.status.in_(["pending", "approved", "left", "rejected"])
        ).order_by(HallPassLog.request_time.desc()).first()

        hall_pass = None
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
