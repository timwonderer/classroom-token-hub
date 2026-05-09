from functools import wraps

from app.extensions import db
from app.models import TapEvent, Student, Transaction, PayrollSettings, ClassEconomy
from datetime import datetime, timezone
from app.utils.time import ensure_utc
from app.attendance import (
    calculate_unpaid_attendance_seconds,
    get_last_payroll_time,
    get_batch_attendance_events,
    calculate_seconds_in_memory
)
from app.utils.attendance_helpers import get_join_code_for_student_period
from flask import has_request_context, session
from decimal import Decimal


DEFAULT_PAY_RATE_PER_MINUTE = Decimal('0.25')
DEFAULT_PAY_RATE_PER_SECOND_DECIMAL = DEFAULT_PAY_RATE_PER_MINUTE / Decimal('60')
# Public default constant kept as Decimal to match helper return types.
DEFAULT_PAY_RATE_PER_SECOND = DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


def with_teacher_id_fallback(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        teacher_id = kwargs.get("teacher_id")
        if teacher_id is None and has_request_context():
            teacher_id = session.get("admin_id")
            kwargs["teacher_id"] = teacher_id
        return func(*args, **kwargs)

    return wrapper


def _resolve_class_id_for_scope(*, teacher_id=None, join_code=None):
    if not join_code:
        return None
    query = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(join_code=join_code)
    if teacher_id is not None:
        query = query.filter(ClassEconomy.teacher_id == teacher_id)
    row = query.first()
    return row[0] if row and row[0] else None


@with_teacher_id_fallback
def get_pay_rate_for_block(block, teacher_id=None, join_code=None):
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
    
    class_id = _resolve_class_id_for_scope(teacher_id=teacher_id, join_code=join_code)
    if not class_id:
        return DEFAULT_PAY_RATE_PER_SECOND_DECIMAL

    base_query = PayrollSettings.query.filter_by(class_id=class_id, is_active=True)

    # Try block-specific settings first
    if block:
        setting = base_query.filter_by(block=block).first()
        if setting and setting.pay_rate:
            # Convert per-minute to per-second using Decimal arithmetic
            return setting.pay_rate / Decimal('60')

    # Fall back to join-code-scoped/global settings for this teacher
    global_setting = base_query.filter_by(block=None).first()
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / Decimal('60')

    # Ultimate fallback to hardcoded default
    return DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


@with_teacher_id_fallback
def get_daily_limit_seconds(block, teacher_id=None, join_code=None):
    """
    Get the daily time limit in seconds for a specific block from settings.

    CRITICAL: Scopes query by teacher_id to prevent multi-tenancy leaks.

    Args:
        block (str): The block/period identifier.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    class_id = _resolve_class_id_for_scope(teacher_id=teacher_id, join_code=join_code)
    if not class_id:
        return None

    base_query = PayrollSettings.query.filter_by(class_id=class_id, is_active=True)

    # Try block-specific settings first
    if block:
        setting = base_query.filter_by(block=block).first()
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
    global_setting = base_query.filter_by(block=None).first()
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

    # --- 3. Determine class scope and fetch class-scoped payroll anchors ---
    teacher_join_codes = list({jc for jc in student_join_codes.values() if jc})
    student_last_payrolls = _get_batch_last_payroll_times(
        student_ids,
        allowed_join_codes=teacher_join_codes,
    )

    # --- 4. Batch Fetch Attendance Events ---
    # Determine the earliest relevant anchor across the scoped classes.
    normalized_global_last_payroll = ensure_utc(last_payroll_time)

    valid_times = [t for t in student_last_payrolls.values() if t]
    if normalized_global_last_payroll:
        valid_times.append(normalized_global_last_payroll)

    # If we have any history, start fetching from the earliest point
    # If no history at all, we technically fetch everything (min_anchor=None)
    min_anchor = min(valid_times) if valid_times else None

    # map: (student_id, period, join_code) -> list of valid events (sorted)
    # Also handles the "initial state" (was active at anchor) logic internally
    # Updated: Use shared function from app.attendance
    events_map = get_batch_attendance_events(student_ids, min_anchor, allowed_join_codes=teacher_join_codes)

    # --- 5. In-Memory Calculation ---
    for student in students:
        # Keep original block names for settings lookup and dedupe to avoid duplicate period entries
        # (e.g., "PERIOD 1, PERIOD 1") causing duplicate payroll calculations.
        student_blocks = []
        seen_blocks = set()
        for raw_block in (student.block or "").split(','):
            block = raw_block.strip()
            if not block:
                continue
            norm = block.upper()
            if norm in seen_blocks:
                continue
            seen_blocks.add(norm)
            student_blocks.append(block)
        
        for block_original in student_blocks:
            block_upper = block_original.upper()

            # lookup rate
            rate_per_second = pay_rates.get(block_upper, pay_rates.get(None, DEFAULT_PAY_RATE_PER_SECOND_DECIMAL))

            # lookup join code
            join_code = student_join_codes.get((student.id, block_upper))
            
            if not join_code:
                continue

            payroll_anchor = student_last_payrolls.get((student.id, join_code))
            if payroll_anchor is None:
                payroll_anchor = normalized_global_last_payroll

            # Calculate seconds using batched events
            # We only care about events >= payroll_anchor
            # The batch loader naturally gives us a relevant stream
            # but we must double-check the anchor for this specific student-block logic
            
            events = events_map.get((student.id, block_upper, join_code), [])
            # Updated: Use shared function from app.attendance
            total_seconds = calculate_seconds_in_memory(events, payroll_anchor)

            if total_seconds > 0:
                amount = (Decimal(total_seconds) * rate_per_second).quantize(Decimal('0.01'))
                if amount > 0:
                    summary.setdefault((student.id, join_code), Decimal('0.00'))
                    summary[(student.id, join_code)] += amount

    return summary

def _get_batch_pay_rates(teacher_id):
    """Batch fetch pay rates for a teacher."""
    from decimal import Decimal
    class_ids_subq = (
        db.session.query(ClassEconomy.class_id)
        .filter(ClassEconomy.teacher_id == teacher_id)
        .subquery()
    )
    settings = (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id.in_(class_ids_subq),
            PayrollSettings.is_active.is_(True),
        )
        .all()
    )
    rates = {}
    
    # Populate specific blocks and global (key=None)
    for s in settings:
        if s.pay_rate:
            rate_sec = s.pay_rate / Decimal('60')
            key = s.block.upper() if s.block else None
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
        
    seats = query.order_by(TeacherBlock.id.desc()).all()

    # Map (student_id, block_upper) -> latest join_code for that block context
    join_codes = {}
    for seat in seats:
        key = (seat.student_id, (seat.block or "").upper())
        if key not in join_codes:
            join_codes[key] = seat.join_code
    return join_codes

def _get_batch_last_payroll_times(student_ids, allowed_join_codes=None):
    """
    Batch find the last payroll/manual-payment anchor for each (student, join_code).
    """
    from app.models import Transaction
    from sqlalchemy import func
    
    query = db.session.query(
        Transaction.student_id,
        Transaction.join_code,
        func.max(Transaction.timestamp)
    ).filter(
        Transaction.student_id.in_(student_ids),
        Transaction.type.in_(["payroll", "manual_payment"]),
        Transaction.join_code.isnot(None),
    )
    if allowed_join_codes is not None:
        query = query.filter(Transaction.join_code.in_(allowed_join_codes))

    results = query.group_by(Transaction.student_id, Transaction.join_code).all()

    return {(student_id, join_code): ensure_utc(ts) for student_id, join_code, ts in results}


@with_teacher_id_fallback
def calculate_payroll(students, last_payroll_time, teacher_id=None):
    """
    Wrapper for backward compatibility. Returns simple student_id -> amount mapping.
    Aggregates amounts from different classes for the same student.
    """
    breakdown = calculate_payroll_breakdown(students, last_payroll_time, teacher_id=teacher_id)
    summary = {}
    for (student_id, _), amount in breakdown.items():
        summary.setdefault(student_id, Decimal('0.00'))
        summary[student_id] += amount
    return summary

def _resolve_payroll_cache_scope(students, teacher_id, join_code=None):
    """Return canonical (join_code, class_id) for a single-class payroll request."""
    if not teacher_id:
        return None, None

    if join_code:
        economy = ClassEconomy.query.filter_by(join_code=join_code, teacher_id=teacher_id).first()
        if not economy:
            return None, None
        return economy.join_code, economy.class_id

    student_ids = [s.id for s in students if getattr(s, "id", None)]
    if not student_ids:
        return None, None

    rows = (
        db.session.query(TeacherBlock.join_code, TeacherBlock.class_id)
        .filter(
            TeacherBlock.teacher_id == teacher_id,
            TeacherBlock.student_id.in_(student_ids),
            TeacherBlock.is_claimed == True,
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.class_id.isnot(None),
        )
        .distinct()
        .all()
    )

    if len(rows) != 1:
        return None, None

    return rows[0].join_code, rows[0].class_id


from app.feats.base import feat_shell

@feat_shell("FEAT-LED-004")
def get_cached_payroll_with_meta(*args, **kwargs):
    """FEAT-Shell for payroll calculation cache management."""
    res = _get_cached_payroll_with_meta_legacy(*args, **kwargs)
    db.session.flush()  # Preserve FEAT orchestrator transaction ownership.
    return res

def _get_cached_payroll_with_meta_legacy(students, last_payroll_time, teacher_id=None, join_code=None):
    """
    Cached version of calculate_payroll (LEGACY).
    Returns (summary, last_updated_datetime).
    """
    from app.models import PayrollCache, Student, TeacherBlock
    from app.extensions import db
    from app.utils.time import utc_now, ensure_utc
    from datetime import timedelta
    
    if teacher_id is None and has_request_context():
        teacher_id = session.get("admin_id")
        
    if not teacher_id:
        return calculate_payroll(students, last_payroll_time, teacher_id=teacher_id), None
 
    scoped_join_code, scoped_class_id = _resolve_payroll_cache_scope(students, teacher_id, join_code=join_code)
    if not scoped_join_code or not scoped_class_id:
        return calculate_payroll(students, last_payroll_time, teacher_id=teacher_id), None
 
    cache_entry = PayrollCache.query.filter_by(class_id=scoped_class_id).first()
    now = utc_now()
    cutoff = now - timedelta(hours=1)
 
    use_cache = False
    if cache_entry and cache_entry.last_calculated_at and ensure_utc(cache_entry.last_calculated_at) > cutoff:
        if cache_entry.cached_breakdown:
            use_cache = True
 
    summary = {}
    last_updated = now
 
    if use_cache:
        raw_data = cache_entry.cached_breakdown
        last_updated = ensure_utc(cache_entry.last_calculated_at)
 
        requested_ids = {s.id for s in students}
 
        for s_id_str, amount_raw in raw_data.items():
            s_id = int(s_id_str)
            if s_id in requested_ids:
                summary[s_id] = Decimal(str(amount_raw))
    else:
        all_creds = TeacherBlock.query.filter_by(
            teacher_id=teacher_id,
            join_code=scoped_join_code,
            class_id=scoped_class_id,
            is_claimed=True,
        ).all()
        all_student_ids = sorted({c.student_id for c in all_creds if c.student_id})
        all_students = Student.query.filter(Student.id.in_(all_student_ids)).all() if all_student_ids else []
 
        full_summary = calculate_payroll(all_students, last_payroll_time, teacher_id=teacher_id)
        cache_data = {str(k): str(v) for k, v in full_summary.items()}
 
        if not cache_entry:
            cache_entry = PayrollCache(
                teacher_id=teacher_id,
                join_code=scoped_join_code,
                class_id=scoped_class_id,
            )
            db.session.add(cache_entry)
        else:
            cache_entry.teacher_id = teacher_id
            cache_entry.join_code = scoped_join_code
            cache_entry.class_id = scoped_class_id
 
        cache_entry.cached_breakdown = cache_data
        cache_entry.last_calculated_at = now
        db.session.flush() # FEAT-LEGACY-WRAP: commit removed
 
        requested_ids = {s.id for s in students}
        summary = {k: v for k, v in full_summary.items() if k in requested_ids}
        last_updated = now
 
    return summary, last_updated
