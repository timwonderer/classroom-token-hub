from functools import wraps

from app.extensions import db
from app.models import TapEvent, Student, Transaction, PayrollSettings
from datetime import datetime, timezone
from app.utils.time import ensure_utc
from app.attendance import calculate_unpaid_attendance_seconds, get_last_payroll_time
from app.utils.attendance_helpers import get_join_code_for_student_period
from flask import has_request_context, session
from decimal import Decimal


DEFAULT_PAY_RATE_PER_MINUTE = 0.25
DEFAULT_PAY_RATE_PER_SECOND = DEFAULT_PAY_RATE_PER_MINUTE / 60.0


def with_teacher_id_fallback(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        teacher_id = kwargs.get("teacher_id")
        if teacher_id is None and has_request_context():
            teacher_id = session.get("admin_id")
            kwargs["teacher_id"] = teacher_id
        return func(*args, **kwargs)

    return wrapper


@with_teacher_id_fallback
def get_pay_rate_for_block(block, teacher_id=None):
    """
    Get the pay rate for a specific block from settings, falling back to global/default.

    CRITICAL: Scopes query by teacher_id to prevent multi-tenancy leaks.

    Args:
        block (str): The block/period identifier.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        Decimal: The pay rate per second as Decimal for precise financial calculations.
    """
    from decimal import Decimal
    
    # Can't lookup settings without a teacher_id - return default
    if teacher_id is None:
        return Decimal(str(DEFAULT_PAY_RATE_PER_SECOND))

    # Try block-specific settings first
    if block:
        setting = PayrollSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block,
            is_active=True
        ).first()
        if setting and setting.pay_rate:
            # Convert per-minute to per-second using Decimal arithmetic
            return setting.pay_rate / Decimal('60')

    # Fall back to global settings for this teacher
    global_setting = PayrollSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None,
        is_active=True
    ).first()
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / Decimal('60')

    # Ultimate fallback to hardcoded default
    return Decimal(str(DEFAULT_PAY_RATE_PER_SECOND))


@with_teacher_id_fallback
def get_daily_limit_seconds(block, teacher_id=None):
    """
    Get the daily time limit in seconds for a specific block from settings.

    CRITICAL: Scopes query by teacher_id to prevent multi-tenancy leaks.

    Args:
        block (str): The block/period identifier.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    # Can't lookup settings without a teacher_id - return no limit
    if teacher_id is None:
        return None

    # Try block-specific settings first
    if block:
        setting = PayrollSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block,
            is_active=True
        ).first()
        if setting:
            # Simple mode: daily_limit_hours
            if setting.settings_mode == 'simple' and setting.daily_limit_hours:
                return int(setting.daily_limit_hours * 3600)  # Convert hours to seconds
            # Advanced mode: max_time_per_day
            elif setting.settings_mode == 'advanced' and setting.max_time_per_day:
                unit_to_seconds = {
                    'seconds': 1,
                    'minutes': 60,
                    'hours': 3600,
                    'days': 86400
                }
                multiplier = unit_to_seconds.get(setting.max_time_per_day_unit, 3600)
                return int(setting.max_time_per_day * multiplier)

    # Fall back to global settings for this teacher
    global_setting = PayrollSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None,
        is_active=True
    ).first()
    if global_setting:
        if global_setting.settings_mode == 'simple' and global_setting.daily_limit_hours:
            return int(global_setting.daily_limit_hours * 3600)
        elif global_setting.settings_mode == 'advanced' and global_setting.max_time_per_day:
            unit_to_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400
            }
            multiplier = unit_to_seconds.get(global_setting.max_time_per_day_unit, 3600)
            return int(global_setting.max_time_per_day * multiplier)

    # No limit set
    return None


@with_teacher_id_fallback
def calculate_payroll_breakdown(students, last_payroll_time, teacher_id=None):
    """
    Calculates payroll for a given list of students since the last payroll run,
    broken down by student AND class (join_code).

    Optimized to use batch queries and avoid N+1 performance issues.
    """
    summary = {}
    if not students:
        return summary

    student_ids = [s.id for s in students]

    # --- 1. Batch Fetch Payroll Settings ---
    # map: block (str/None) -> rate_per_second (Decimal)
    pay_rates = _get_batch_pay_rates(teacher_id)

    # --- 2. Batch Fetch Join Codes ---
    # map: (student_id, block) -> join_code
    student_join_codes = _get_batch_join_codes(teacher_id, student_ids)

    # --- 3. Batch Fetch Last Payroll Times ---
    # map: student_id -> last_payroll_timestamp
    student_last_payrolls = _get_batch_last_payroll_times(student_ids)

    # --- 4. Batch Fetch Attendance Events ---
    # Determine the global anchor to limit event fetching
    # We must go back at least to the earliest relevant payroll time
    normalized_global_last_payroll = ensure_utc(last_payroll_time)
    
    # Filter valid times to find the minimum anchor
    valid_times = [t for t in student_last_payrolls.values() if t]
    if normalized_global_last_payroll:
        valid_times.append(normalized_global_last_payroll)
    
    # If we have any history, start fetching from the earliest point
    # If no history at all, we technically fetch everything (min_anchor=None)
    min_anchor = min(valid_times) if valid_times else None

    # map: (student_id, period) -> list of valid events (sorted)
    # Also handles the "initial state" (was active at anchor) logic internally
    events_map = _get_batch_attendance_events(student_ids, min_anchor)

    # --- 5. In-Memory Calculation ---
    for student in students:
        # Keep original block names for settings lookup
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        
        # Determine specific anchor for this student
        student_last_pay = student_last_payrolls.get(student.id)
        possible_anchors = [t for t in [normalized_global_last_payroll, student_last_pay] if t]
        payroll_anchor = max(possible_anchors) if possible_anchors else None

        for block_original in student_blocks:
            block_upper = block_original.upper()

            # lookup rate
            rate_per_second = pay_rates.get(block_original, pay_rates.get(None, Decimal(str(DEFAULT_PAY_RATE_PER_SECOND))))

            # lookup join code
            join_code = student_join_codes.get((student.id, block_original))
            
            if not join_code:
                continue

            # Calculate seconds using batched events
            # We only care about events >= payroll_anchor
            # The batch loader naturally gives us a relevant stream
            # but we must double-check the anchor for this specific student-block logic
            
            events = events_map.get((student.id, block_upper), [])
            total_seconds = _calculate_seconds_in_memory(events, payroll_anchor)

            if total_seconds > 0:
                amount = round(total_seconds * rate_per_second, 2)
                if amount > 0:
                    summary.setdefault((student.id, join_code), 0)
                    summary[(student.id, join_code)] += amount

    return summary

def _get_batch_pay_rates(teacher_id):
    """Batch fetch pay rates for a teacher."""
    from decimal import Decimal
    settings = PayrollSettings.query.filter_by(teacher_id=teacher_id, is_active=True).all()
    rates = {}
    
    # Populate specific blocks and global (key=None)
    for s in settings:
        if s.pay_rate:
            rate_sec = s.pay_rate / Decimal('60')
            key = s.block if s.block else None
            rates[key] = rate_sec
            
    return rates

def _get_batch_join_codes(teacher_id, student_ids):
    """Batch fetch join codes for students in a teacher's classes."""
    from app.models import TeacherBlock
    
    query = TeacherBlock.query.filter(
        TeacherBlock.student_id.in_(student_ids),
        TeacherBlock.is_claimed == True
    )
    
    if teacher_id:
        query = query.filter(TeacherBlock.teacher_id == teacher_id)
        
    seats = query.all()
    
    # Map (student_id, block) -> join_code
    return {(seat.student_id, seat.block): seat.join_code for seat in seats}

def _get_batch_last_payroll_times(student_ids):
    """
    Batch find the last payroll transaction timestamp for each student.
    Uses a window function technique or grouping to find MAX(timestamp).
    """
    from app.models import Transaction
    from sqlalchemy import func
    
    # Query: SELECT student_id, MAX(timestamp) FROM transaction WHERE ... GROUP BY student_id
    results = db.session.query(
        Transaction.student_id,
        func.max(Transaction.timestamp)
    ).filter(
        Transaction.student_id.in_(student_ids),
        Transaction.type.in_(["payroll", "manual_payment"])
    ).group_by(Transaction.student_id).all()
    
    return {row[0]: ensure_utc(row[1]) for row in results}

def _get_batch_attendance_events(student_ids, min_anchor):
    """
    Fetch all relevant tap events for the given students after min_anchor.
    Crucially, also determines if they were 'active' right before min_anchor.
    """
    # 1. Fetch all events > min_anchor (if min_anchor exists)
    query = TapEvent.query.filter(
        TapEvent.student_id.in_(student_ids),
        TapEvent.is_deleted == False
    )
    
    if min_anchor:
        query = query.filter(TapEvent.timestamp > min_anchor)
    
    events = query.order_by(TapEvent.timestamp.asc()).all()
    
    # Group by (student_id, period)
    grouped = {}
    for e in events:
        key = (e.student_id, e.period)
        grouped.setdefault(key, []).append(e)
        
    # 2. If min_anchor exists, we need the "initial state" for each student/period
    # We need the LAST event <= min_anchor for each student/period.
    if min_anchor:
        from sqlalchemy import func, and_
        
        # Subquery to find the latest timestamp for each student/period before anchor
        subquery = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            func.max(TapEvent.timestamp).label("max_ts")
        ).filter(
            TapEvent.student_id.in_(student_ids),
            TapEvent.timestamp <= min_anchor,
            TapEvent.is_deleted == False
        ).group_by(
            TapEvent.student_id,
            TapEvent.period
        ).subquery()
        
        # Join back to get the full event details (status)
        # We join on student_id, period, and timestamp
        initial_states = db.session.query(
            TapEvent.student_id,
            TapEvent.period,
            TapEvent.status,
            TapEvent.timestamp
        ).join(
            subquery,
            and_(
                TapEvent.student_id == subquery.c.student_id,
                TapEvent.period == subquery.c.period,
                TapEvent.timestamp == subquery.c.max_ts
            )
        ).filter(
            TapEvent.is_deleted == False
        ).all()
        
        # Prepend a virtual "start" event if they were active
        for row in initial_states:
            s_id, period, status, ts = row.student_id, row.period, row.status, row.timestamp
            if status == 'active':
                key = (s_id, period)
                
                # We inject the state into the list
                virtual_start_time = ensure_utc(min_anchor)
                
                # Mock object
                mock_event = TapEvent(
                    student_id=s_id,
                    period=period,
                    status='active',
                    timestamp=virtual_start_time
                )
                
                # Insert at index 0
                grouped.setdefault(key, []).insert(0, mock_event)

    return grouped

def _calculate_seconds_in_memory(events, anchor):
    """
    Calculate unpaid seconds from a sorted list of events, strictly after anchor.
    """
    total_seconds = 0
    in_time = None
    
    anchor = ensure_utc(anchor)
    
    for event in events:
        event_time = ensure_utc(event.timestamp)
        
        # Skip events before specific anchor (since batch might have fetched earlier ones for specific students)
        if anchor and event_time <= anchor:
            # Loop-hole: If this event is 'active' and is the one immediately preceding/at the valid range,
            # it effectively sets the in_time for the next period.
            # However, our batch logic prepended a "virtual active" event at min_anchor if needed.
            # If the student's *specific* anchor is later than min_anchor, we need to respect that.
            
            if event.status == 'active':
                 in_time = event_time # potential start, but might be cut off by anchor
            else:
                 in_time = None # reset
            continue

        # If we crossed the anchor boundary and in_time was set from a pre-anchor event,
        # we should clamp the start time to the anchor.
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
        # Clamp start to anchor if needed (edge case)
        if anchor and in_time < anchor:
            in_time = anchor
            
        from app.utils.time import utc_now
        now = utc_now()
        total_seconds += (now - in_time).total_seconds()
        
    return int(total_seconds)


@with_teacher_id_fallback
def calculate_payroll(students, last_payroll_time, teacher_id=None):
    """
    Wrapper for backward compatibility. Returns simple student_id -> amount mapping.
    Aggregates amounts from different classes for the same student.
    """
    breakdown = calculate_payroll_breakdown(students, last_payroll_time, teacher_id=teacher_id)
    summary = {}
    for (student_id, _), amount in breakdown.items():
        summary.setdefault(student_id, 0)
        summary[student_id] += amount
    return summary
    return summary

def get_cached_payroll_with_meta(students, last_payroll_time, teacher_id=None):
    """
    Cached version of calculate_payroll.
    Returns (summary, last_updated_datetime).
    
    Cache Strategy:
    - Stores the FULL payroll summary for a teacher (all their students).
    - If valid (< 1 hour), returns cached data filtered by the requested 'students' list.
    - If invalid, recalculates for ALL teacher's students, updates cache, then filters.
    """
    from app.models import PayrollCache, Student, TeacherBlock
    from app.extensions import db
    from app.utils.time import utc_now, ensure_utc
    from datetime import timedelta
    
    if teacher_id is None and has_request_context():
        teacher_id = session.get("admin_id")
        
    if not teacher_id:
        # Cannot cache without teacher_id, fallback
        return calculate_payroll(students, last_payroll_time, teacher_id=teacher_id), None

    # 1. Check Cache
    cache_entry = PayrollCache.query.filter_by(teacher_id=teacher_id).first()
    now = utc_now()
    cutoff = now - timedelta(hours=1)
    
    use_cache = False
    if cache_entry and cache_entry.last_calculated_at and ensure_utc(cache_entry.last_calculated_at) > cutoff:
        if cache_entry.cached_breakdown:
            use_cache = True
            
    summary = {}
    last_updated = now
    
    if use_cache:
        # Optimize: Use cached data
        raw_data = cache_entry.cached_breakdown
        last_updated = ensure_utc(cache_entry.last_calculated_at)
        
        # Request scope IDs
        requested_ids = {s.id for s in students}
        
        # Convert JSON keys (str) back to int and values to Decimal
        for s_id_str, amount_float in raw_data.items():
            s_id = int(s_id_str)
            if s_id in requested_ids:
                summary[s_id] = Decimal(str(amount_float))
    else:
        # Cache Miss/Stale: Recalculate EVERYTHING for this teacher
        # We need to fetch ALL students for this teacher to build a complete cache
        # This prevents partial caches if calling with subset
        
        # Find all student IDs for this teacher
        all_creds = TeacherBlock.query.filter_by(teacher_id=teacher_id, is_claimed=True).all()
        all_student_ids = [c.student_id for c in all_creds]
        
        # We need Student objects for calculation (optimize fetch?)
        # calculate_payroll expects list of Student objects (mostly for .id and .block access)
        # We can just fetch the Students
        all_students = Student.query.filter(Student.id.in_(all_student_ids)).all()
        
        # Calculate full payroll
        full_summary = calculate_payroll(all_students, last_payroll_time, teacher_id=teacher_id)
        
        # Serialize for Cache (int key -> str, Decimal -> float)
        cache_data = {str(k): float(v) for k, v in full_summary.items()}
        
        # Update/Create Cache Record
        if not cache_entry:
            cache_entry = PayrollCache(teacher_id=teacher_id)
            db.session.add(cache_entry)
            
        cache_entry.cached_breakdown = cache_data
        cache_entry.last_calculated_at = now
        db.session.commit()
        
        # Filter for return
        requested_ids = {s.id for s in students}
        summary = {k: v for k, v in full_summary.items() if k in requested_ids}
        last_updated = now

    return summary, last_updated
