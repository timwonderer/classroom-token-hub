from app.extensions import db
from app.models import Transaction, TransactionStatus, PayrollSettings
from app.utils.canonical_temporal_resolver import ensure_utc
from app.attendance import (
    get_batch_attendance_events,
    calculate_seconds_in_memory
)
from flask import has_request_context, session
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


DEFAULT_PAY_RATE_PER_MINUTE = Decimal('0.25')
DEFAULT_PAY_RATE_PER_SECOND_DECIMAL = DEFAULT_PAY_RATE_PER_MINUTE / Decimal('60')
# Public default constant kept as Decimal to match helper return types.
DEFAULT_PAY_RATE_PER_SECOND = DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


def _fetch_active_setting(*, class_id: str):
    """Return the class's single active payroll policy, or None.

    ``class_id`` is the whole scope. `block` is display metadata and is never a
    scoping key (INV-ARC-014 §V, which forbids execution depending on sections or
    periods; INV-ARC-019; DOM-CLASS-001). The partial unique index
    ``uq_payroll_settings_active_scope`` is on ``class_id`` alone WHERE
    ``availability_state = 'IN_USE'``, so at most one row can match.

    That index is what makes the multiplicity check below an integrity assertion
    rather than a tie-break: if it ever returns two rows the index is missing or
    disabled, and picking the "newest" would quietly paper over that. Raising
    keeps a schema failure from presenting as a pay rate.

    Raises:
        ValueError: when class scope is missing, or when the active-scope index
            is not holding.
    """
    if not class_id:
        raise ValueError("PayrollSettings lookup requires class_id.")
    rows = (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id == class_id,
            PayrollSettings.availability_state == 'IN_USE',
        )
        .order_by(PayrollSettings.updated_at.desc(), PayrollSettings.id.desc())
        .limit(2)
        .all()
    )
    if len(rows) > 1:
        raise ValueError(
            f"Multiple IN_USE PayrollSettings rows for class_id={class_id}; "
            "uq_payroll_settings_active_scope is not holding."
        )
    return rows[0] if rows else None


def get_pay_rate_for_class(*, class_id: str):
    """
    Get the per-second pay rate for a class, falling back to the default.

    Args:
        class_id (str): Canonical class scope.

    Returns:
        Decimal: The pay rate per second as Decimal for precise financial calculations.
    """
    setting = _fetch_active_setting(class_id=class_id)
    if setting and setting.pay_rate:
        return setting.pay_rate / Decimal('60')

    return DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


def get_daily_limit_seconds(*, class_id: str):
    """
    Get the daily time limit in seconds for a class.

    Args:
        class_id (str): Canonical class scope.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    setting = _fetch_active_setting(class_id=class_id)
    if setting:
        # Simple mode: daily_limit_hours
        if setting.settings_mode == 'simple' and setting.daily_limit_hours:
            return int(setting.daily_limit_hours * 3600)  # Convert hours to seconds
        # Advanced mode: max_time_per_day
        if setting.settings_mode == 'advanced' and setting.max_time_per_day:
            unit_to_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400
            }
            multiplier = unit_to_seconds.get(setting.max_time_per_day_unit, 3600)
            return int(setting.max_time_per_day * multiplier)

    # No limit set
    return None


def calculate_payroll_breakdown(class_id, seat_ids, last_payroll_time):
    """
    Calculates payroll for a given list of seat_ids since the last payroll run.
    Optimized to use batch queries and avoid N+1 performance issues.
    """
    summary = {}
    if not seat_ids or not class_id:
        return summary

    from app.models import Seat
    seats = Seat.query.filter(Seat.id.in_(seat_ids), Seat.class_id == class_id).all()
    if not seats:
        return summary

    # --- 1. Determine class scope and fetch class-scoped payroll anchors ---
    allowed_class_ids = [class_id]
    scoped_seat_ids = [s.id for s in seats]
    pay_rates = _get_batch_pay_rates(allowed_class_ids)
    payroll_settings = _get_batch_payroll_settings(allowed_class_ids)
    student_last_payrolls = _get_batch_last_payroll_times(
        scoped_seat_ids,
        allowed_class_ids=allowed_class_ids,
    )

    # --- 2. Batch Fetch Attendance Events ---
    normalized_global_last_payroll = ensure_utc(last_payroll_time)
    valid_times = [t for t in student_last_payrolls.values() if t]
    if normalized_global_last_payroll:
        valid_times.append(normalized_global_last_payroll)

    min_anchor = min(valid_times) if valid_times else None
    events_map = get_batch_attendance_events(scoped_seat_ids, min_anchor, allowed_class_ids=allowed_class_ids)

    # --- 3. In-Memory Calculation ---
    for seat in seats:
        # Rate is a property of the class, not of any section/period label
        # (INV-ARC-014 §V). Every seat in the class prices identically.
        rate_per_second = pay_rates.get(class_id, DEFAULT_PAY_RATE_PER_SECOND_DECIMAL)

        payroll_anchor = student_last_payrolls.get((seat.id, class_id))
        if payroll_anchor is None:
            payroll_anchor = normalized_global_last_payroll

        # Attendance events are grouped by canonical seat/class scope only.
        events = events_map.get((seat.id, class_id), [])
        total_seconds = calculate_seconds_in_memory(events, payroll_anchor)

        setting = payroll_settings.get(class_id)
        billable_seconds = _round_billable_seconds(total_seconds, setting)

        if billable_seconds > 0:
            amount = (Decimal(billable_seconds) * rate_per_second).quantize(Decimal('0.01'))
            if amount > 0:
                summary.setdefault(seat.id, Decimal('0.00'))
                summary[seat.id] += amount

    return summary


def _round_billable_seconds(total_seconds: int, setting) -> int:
    """Apply advanced-mode time-increment rounding to elapsed attendance."""
    if total_seconds <= 0 or not setting or setting.settings_mode != 'advanced':
        return max(0, total_seconds)
    increment = {
        'seconds': 1,
        'minutes': 60,
        'hours': 3600,
        'days': 86400,
    }.get((setting.time_unit or 'minutes').lower(), 60)
    units = Decimal(total_seconds) / Decimal(increment)
    mode = (setting.rounding_mode or 'down').lower()
    rounding = {
        'up': ROUND_CEILING,
        'nearest': ROUND_HALF_UP,
        'down': ROUND_FLOOR,
    }.get(mode, ROUND_FLOOR)
    return int(units.quantize(Decimal('1'), rounding=rounding)) * increment

def _get_batch_pay_rates(class_ids):
    """Batch fetch per-second pay rates keyed by canonical class_id.

    One rate per class: ``uq_payroll_settings_active_scope`` permits a single
    IN_USE row per ``class_id``, and `block` is not a scoping key
    (INV-ARC-014 §V). Ordering makes the load deterministic even if that index
    is not holding, so a batch run cannot disagree with the single-class reader
    in ``_fetch_active_setting``.
    """
    if not class_ids:
        return {}
    settings = (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id.in_(class_ids),
            PayrollSettings.availability_state == 'IN_USE',
        )
        .order_by(PayrollSettings.updated_at.asc(), PayrollSettings.id.asc())
        .all()
    )
    rates = {}
    for s in settings:
        if s.pay_rate and s.class_id:
            rates[s.class_id] = s.pay_rate / Decimal('60')

    return rates


def _get_batch_payroll_settings(class_ids):
    if not class_ids:
        return {}
    settings = (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id.in_(class_ids),
            PayrollSettings.availability_state == 'IN_USE',
        )
        .order_by(PayrollSettings.updated_at.asc(), PayrollSettings.id.asc())
        .all()
    )
    return {setting.class_id: setting for setting in settings}



def _get_batch_last_payroll_times(seat_ids, allowed_class_ids):
    """
    Batch find the last payroll/manual-payment anchor for each (seat_id, class_id).
    """
    from sqlalchemy import func

    if not seat_ids or not allowed_class_ids:
        return {}

    query = db.session.query(
        Transaction.seat_id,
        Transaction.class_id,
        func.max(Transaction.timestamp)
    ).filter(
        Transaction.seat_id.in_(seat_ids),
        Transaction.class_id.in_(allowed_class_ids),
        Transaction.type.in_(["payroll", "manual_payment"]),
        Transaction.status != TransactionStatus.VOID,
    )

    results = query.group_by(Transaction.seat_id, Transaction.class_id).all()

    return {(seat_id, class_id): ensure_utc(ts) for seat_id, class_id, ts in results}




from app.utils.canonical_temporal_resolver import utc_now
