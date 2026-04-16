from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import func

from app.models import HallPassLog, StudentTeacher, TapEvent, TeacherBlock
from app.utils.attendance_helpers import get_join_code_for_student_period
from app.utils.seat_scope import get_seat_ids_for_student_join, seat_scoped_filter
from app.utils.time import ensure_utc, utc_now


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
