"""
Payroll Domain View Model Builders — Phase 1 Remediation

Converts raw payroll data and ledger records into immutable, presentation-ready
view models per SPEC-UI-001 and INV-ARC-022.

All payroll calculations and currency formatting is pre-computed here.
Templates receive only formatted display values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import PayrollSettings, Transaction, Seat, IdentityProfile


@dataclass(frozen=True)
class StudentPayrollStatusView:
    """
    Pre-computed payroll status snapshot for one student.

    Eliminates all template-level payroll calculations and currency formatting.
    Includes student identification fields for Manual Payment tab display.
    """
    seat_id: int  # Seat ID (used for balance lookups in templates)
    student_name: str
    display_earnings_this_period: str  # Pre-formatted as "$X.XX"
    display_taxes_this_period: str  # Pre-formatted as "$X.XX"
    display_net_pay_this_period: str  # Pre-formatted as "$X.XX"
    display_total_earnings_all_time: str  # Pre-formatted as "$X.XX"
    display_total_taxes_all_time: str  # Pre-formatted as "$X.XX"
    display_total_net_pay_all_time: str  # Pre-formatted as "$X.XX"

    earnings_raw: Decimal  # Raw for calculations
    taxes_raw: Decimal  # Raw for calculations
    net_raw: Decimal  # Raw for calculations

    # Derived state
    has_current_period_earnings: bool
    status_label: str  # "Paid", "Pending", "No earnings", etc.

    # Student identification fields (for Manual Payment tab template display)
    public_id: str = ""  # Public student ID for form submission
    full_name: str = ""  # Display name (duplicate of student_name for template compatibility)
    class_id: str = ""  # Class identifier
    class_label: str = ""  # Display label for class

    # Account balances (pre-formatted for template display without filters)
    display_checking_balance: str = "$0.00"  # Pre-formatted checking account balance
    display_savings_balance: str = "$0.00"  # Pre-formatted savings account balance


@dataclass(frozen=True)
class PayrollConfigurationView:
    """
    Pre-computed payroll configuration for admin dashboard.

    Eliminates template-level payroll settings display and calculations.
    """
    class_id: str
    settings_mode: str  # 'simple' or 'advanced'
    pay_schedule_type: str  # 'daily', 'weekly', 'biweekly', 'monthly', 'custom'
    display_pay_rate: str  # Pre-formatted as "$X.XX per {time_unit}"
    display_next_payroll_date: str | None  # Pre-formatted date or "Not scheduled"
    overtime_enabled: bool
    display_overtime_multiplier: str | None  # Pre-formatted as "X.Xx" multiplier if enabled
    rounding_mode: str  # 'up' or 'down'

    # Student summary
    total_students: int
    students_with_current_earnings: int
    students_pending_payment: int
    display_total_payroll_amount: str  # Pre-formatted as "$X.XX"

    # Detailed student statuses (list of StudentPayrollStatusView)
    student_statuses: list[StudentPayrollStatusView] = field(default_factory=list)


def build_student_payroll_status_view(
    seat_id: int,
    class_id: str,
    student_name: str,
    earnings_this_period: Decimal | float | int = 0,
    taxes_this_period: Decimal | float | int = 0,
    total_earnings_all_time: Decimal | float | int = 0,
    total_taxes_all_time: Decimal | float | int = 0,
    public_id: str = "",
    full_name: str = "",
    class_label: str = "",
    checking_balance: Decimal | float | int = 0,
    savings_balance: Decimal | float | int = 0,
) -> StudentPayrollStatusView:
    """
    Build pre-computed payroll status for one student.

    Pre-formats all currency amounts to eliminate template-level Jinja filters
    (audit violations: admin_payroll.html extensive numeric formatting).

    Args:
        seat_id: The student's seat ID
        class_id: Class scope
        student_name: Display name
        earnings_this_period: Raw earnings for current period
        taxes_this_period: Raw taxes for current period
        total_earnings_all_time: Raw total earnings across all periods
        total_taxes_all_time: Raw total taxes across all periods

    Returns:
        Frozen StudentPayrollStatusView with pre-formatted display strings
    """
    # Convert to Decimal for precision
    earnings = Decimal(str(earnings_this_period))
    taxes = Decimal(str(taxes_this_period))
    net = earnings - taxes

    total_earnings = Decimal(str(total_earnings_all_time))
    total_taxes = Decimal(str(total_taxes_all_time))
    total_net = total_earnings - total_taxes

    # Pre-format all display strings (no Jinja filters in template)
    display_earnings = f"${earnings:.2f}"
    display_taxes = f"${taxes:.2f}"
    display_net = f"${net:.2f}"
    display_total_earnings = f"${total_earnings:.2f}"
    display_total_taxes = f"${total_taxes:.2f}"
    display_total_net = f"${total_net:.2f}"

    # Pre-format account balances
    checking = Decimal(str(checking_balance))
    savings = Decimal(str(savings_balance))
    display_checking = f"${checking:.2f}"
    display_savings = f"${savings:.2f}"

    # Derive status label
    if earnings > 0:
        status_label = "Earning"
    elif total_earnings > 0:
        status_label = "Pending Payment"
    else:
        status_label = "No Earnings"

    return StudentPayrollStatusView(
        seat_id=seat_id,
        student_name=student_name,
        display_earnings_this_period=display_earnings,
        display_taxes_this_period=display_taxes,
        display_net_pay_this_period=display_net,
        display_total_earnings_all_time=display_total_earnings,
        display_total_taxes_all_time=display_total_taxes,
        display_total_net_pay_all_time=display_total_net,
        earnings_raw=earnings,
        taxes_raw=taxes,
        net_raw=net,
        has_current_period_earnings=earnings > 0,
        status_label=status_label,
        # Student identification for template display
        public_id=public_id,
        full_name=full_name or student_name,  # Fallback to student_name if not provided
        class_id=class_id,
        class_label=class_label,
        # Account balances (pre-formatted for template)
        display_checking_balance=display_checking,
        display_savings_balance=display_savings,
    )


def build_payroll_configuration_view(
    class_id: str,
    settings: PayrollSettings | None = None,
    student_statuses: list[StudentPayrollStatusView] | None = None,
    next_payroll_date=None,
) -> PayrollConfigurationView:
    """
    Build pre-computed payroll configuration for admin dashboard.

    Eliminates all template-level payroll settings display (audit violations:
    admin_payroll.html 74 vars, 151 tags - extensive configuration display).

    Args:
        class_id: Class scope
        settings: PayrollSettings model (if None, uses defaults)
        student_statuses: Pre-built list of StudentPayrollStatusView
        next_payroll_date: the derived next payroll date (DOM-PROD-001 §XV.5);
            it is not stored on the setting

    Returns:
        Frozen PayrollConfigurationView with pre-formatted configuration display
    """
    if not student_statuses:
        student_statuses = []

    # Set defaults if no settings provided
    pay_rate = Decimal('0.25')
    settings_mode = 'simple'
    pay_schedule_type = 'biweekly'
    overtime_enabled = False
    rounding_mode = 'down'
    time_unit = 'minute'

    if settings:
        pay_rate = Decimal(str(settings.pay_rate))
        settings_mode = infer_settings_form_mode(settings)
        pay_schedule_type = settings.pay_schedule_type or 'biweekly'
        overtime_enabled = settings.overtime_threshold is not None
        rounding_mode = settings.rounding_mode or 'down'

    # Pre-format display strings
    display_pay_rate = f"${pay_rate:.2f} per {time_unit}"

    display_next_payroll = "Not scheduled"
    if next_payroll_date:
        display_next_payroll = next_payroll_date.strftime("%b %d, %Y")

    # No overtime multiplier is a legal payroll setting (DOM-POL-001A §V.F).
    display_overtime_multiplier = None

    # Compute student summary statistics
    total_students = len(student_statuses)
    students_with_earnings = sum(
        1 for s in student_statuses if s.has_current_period_earnings
    )
    students_pending = sum(
        1 for s in student_statuses if s.status_label == "Pending Payment"
    )

    # Compute total payroll amount
    total_payroll = sum(s.net_raw for s in student_statuses)
    display_total_payroll = f"${total_payroll:.2f}"

    return PayrollConfigurationView(
        class_id=class_id,
        settings_mode=settings_mode,
        pay_schedule_type=pay_schedule_type,
        display_pay_rate=display_pay_rate,
        display_next_payroll_date=display_next_payroll,
        overtime_enabled=overtime_enabled,
        display_overtime_multiplier=display_overtime_multiplier,
        rounding_mode=rounding_mode,
        total_students=total_students,
        students_with_current_earnings=students_with_earnings,
        students_pending_payment=students_pending,
        display_total_payroll_amount=display_total_payroll,
        student_statuses=student_statuses,
    )


#: Seconds in one of each selectable time unit.
#:
#: ``PayrollSettings.pay_rate`` is canonically dollars **per minute**, while the
#: Advanced form asks the teacher for dollars per *their* chosen unit. The two
#: conversions below are exact inverses and are kept in one place because they
#: were previously written only at the save end: the display rendered the raw
#: per-minute number against the chosen unit, so a class configured at
#: $1.50/hour showed "$0.03" in the form — and because that value pre-populates
#: the input, each re-save divided the real rate by 60.
#:
#: Expressed in seconds rather than minutes so every factor is an exact integer
#: ratio; a `Decimal('1')/Decimal('60')` intermediate does not round-trip.
SECONDS_PER_TIME_UNIT = {
    'seconds': 1,
    'minutes': 60,
    'hours': 3600,
    'days': 86400,
}

_SECONDS_PER_MINUTE = Decimal('60')


def _unit_seconds(time_unit: str) -> Decimal:
    return Decimal(SECONDS_PER_TIME_UNIT.get((time_unit or '').strip(), 60))


def rate_per_minute_to_unit(rate_per_minute, time_unit: str) -> Decimal:
    """Convert the canonical per-minute rate into the teacher's chosen unit."""
    return Decimal(str(rate_per_minute)) * _unit_seconds(time_unit) / _SECONDS_PER_MINUTE


def rate_unit_to_per_minute(rate_in_unit, time_unit: str) -> Decimal:
    """Convert a rate expressed per `time_unit` back to the canonical per minute."""
    return Decimal(str(rate_in_unit)) * _SECONDS_PER_MINUTE / _unit_seconds(time_unit)


#: The order units are tried in when a rate is shown or pre-filled.
_DISPLAY_UNIT_PREFERENCE = ('minutes', 'hours', 'days', 'seconds')
_SINGULAR = {'seconds': 'second', 'minutes': 'minute', 'hours': 'hour', 'days': 'day'}
_CENT = Decimal('0.01')
# pay_rate is NUMERIC(18,8) (DOM-CORE-002 §11).
_STORED = Decimal('0.00000001')


def exact_rate_unit(rate_per_minute) -> tuple[str, Decimal]:
    """A unit in which the stored rate is a whole number of cents, and that amount.

    The unit a teacher typed the rate in is not stored (DOM-POL-001A §V.F), but
    the form must still pre-fill a value that saves back to the same rate: a
    $1.50/hour rate is $0.025/minute, and showing it per minute to the cent
    ("0.03") would store $1.80/hour on the next save. So the first unit — minute,
    hour, day, second — whose amount is exact to the cent is used. A rate exact
    in none keeps full precision per minute rather than being rounded.
    """
    rate = Decimal(str(rate_per_minute)).quantize(_STORED)
    for unit in _DISPLAY_UNIT_PREFERENCE:
        amount = rate_per_minute_to_unit(rate, unit).quantize(_CENT)
        # Exact means the cent amount saves back to the stored rate: $5/hour is
        # stored as 0.08333333/minute, which is 4.9999998/hour, yet 5.00/hour
        # saves back to the same 0.08333333.
        if rate_unit_to_per_minute(amount, unit).quantize(_STORED) == rate:
            return unit, amount
    return 'minutes', rate.normalize()


def infer_settings_form_mode(settings: PayrollSettings | None) -> str:
    """Which form a stored setting reads best in: ``simple`` or ``advanced``.

    The simple/advanced switch is data-entry presentation, not a payroll
    setting, so it is not stored (DOM-POL-001A §V.F). A row opens in the advanced
    form when it uses anything the simple form cannot express.
    """
    if settings is None:
        return 'simple'
    if (
        settings.overtime_threshold is not None
        or (settings.rounding_mode or 'down') != 'down'
        or (settings.max_time_per_day and settings.max_time_per_day_unit not in ('hours', 'minutes'))
    ):
        return 'advanced'
    return 'simple'


def build_payroll_settings_form(settings: PayrollSettings | None) -> dict:
    """Pre-population for the payroll settings form, from a stored setting.

    The form converts entries into the legal columns and stores nothing else, so
    the entry unit of the rate is not remembered: the advanced form shows the
    rate in a unit that saves back exactly (:func:`exact_rate_unit`), the simple
    form the hourly one.
    """
    if settings is None:
        return {
            'configured': False,
            'settings_mode': 'simple',
            'time_unit': 'minutes',
            'per_unit_rate_value': '',
            'hourly_rate_value': '',
            'pay_schedule_type': 'biweekly',
            'daily_limit_hours': None,
            'overtime_enabled': False,
            'overtime_threshold': None,
            'overtime_threshold_unit': 'hours',
            'max_time_per_day': None,
            'max_time_per_day_unit': 'hours',
            'rounding_mode': 'down',
        }
    rate = Decimal(str(settings.pay_rate))
    rate_unit, per_unit_amount = exact_rate_unit(rate)
    daily_limit_hours = None
    if settings.max_time_per_day:
        seconds = Decimal(str(settings.max_time_per_day)) * _unit_seconds(settings.max_time_per_day_unit or 'hours')
        daily_limit_hours = float(seconds / Decimal(3600))
    return {
        'configured': True,
        'settings_mode': infer_settings_form_mode(settings),
        'time_unit': rate_unit,
        'per_unit_rate_value': f"{per_unit_amount}",
        'hourly_rate_value': f"{rate * 60:.2f}",
        'pay_schedule_type': settings.pay_schedule_type,
        'daily_limit_hours': daily_limit_hours,
        'overtime_enabled': settings.overtime_threshold is not None,
        'overtime_threshold': settings.overtime_threshold,
        'overtime_threshold_unit': settings.overtime_threshold_unit or 'hours',
        'max_time_per_day': settings.max_time_per_day,
        'max_time_per_day_unit': settings.max_time_per_day_unit or 'hours',
        'rounding_mode': settings.rounding_mode or 'down',
    }


def build_payroll_settings_display(settings: PayrollSettings | None) -> dict[str, str]:
    """
    Build pre-formatted pay rate display strings for a single PayrollSettings row.

    Eliminates template-level "%.2f"|format() currency formatting used for the
    Settings tab summaries and pay rate input pre-population.

    ``pay_rate`` is stored per minute (DOM-CORE-002 §11). The rate is shown in the
    first unit in which it is exact to the cent (:func:`exact_rate_unit`), with
    its hourly equivalent when that unit is not the hour.

    Returns:
        Dict with:
            display_pay_rate: "$X.XX" in the display unit
            display_hourly_rate_value: plain "X.XX" hourly rate (no "$")
            display_per_unit_rate_value: plain "X.XX" in the display unit (no "$")
            display_rate_unit: the display unit, singular ("minute")
            display_rate_with_unit: "$X.XX/minute ($Y.YY/hour)" or "$Y.YY/hour"
    """
    if not settings:
        return {
            'display_pay_rate': "$0.00",
            'display_hourly_rate_value': "",
            'display_per_unit_rate_value': "",
            'display_rate_unit': "",
            'display_rate_with_unit': "$0.00",
        }

    rate = Decimal(str(settings.pay_rate))
    unit, amount = exact_rate_unit(rate)
    display_hourly_value = f"{rate * 60:.2f}"
    singular = _SINGULAR[unit]
    with_unit = f"${amount}/{singular}"
    if unit != 'hours':
        with_unit += f" (${display_hourly_value}/hour)"
    return {
        'display_pay_rate': f"${amount}",
        'display_hourly_rate_value': display_hourly_value,
        'display_per_unit_rate_value': f"{amount}",
        'display_rate_unit': singular,
        'display_rate_with_unit': with_unit,
    }
