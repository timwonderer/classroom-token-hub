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
) -> PayrollConfigurationView:
    """
    Build pre-computed payroll configuration for admin dashboard.

    Eliminates all template-level payroll settings display (audit violations:
    admin_payroll.html 74 vars, 151 tags - extensive configuration display).

    Args:
        class_id: Class scope
        settings: PayrollSettings model (if None, uses defaults)
        student_statuses: Pre-built list of StudentPayrollStatusView

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
    overtime_multiplier = 1.0
    rounding_mode = 'down'
    next_payroll_date = None
    time_unit = 'minute'

    if settings:
        pay_rate = Decimal(str(settings.pay_rate))
        settings_mode = settings.settings_mode or 'simple'
        pay_schedule_type = settings.pay_schedule_type or 'biweekly'
        overtime_enabled = settings.overtime_enabled or False
        overtime_multiplier = float(settings.overtime_multiplier or 1.0)
        rounding_mode = settings.rounding_mode or 'down'
        next_payroll_date = settings.next_payroll_date
        time_unit = (settings.time_unit or 'minutes').rstrip('s')  # Remove plural

    # Pre-format display strings
    display_pay_rate = f"${pay_rate:.2f} per {time_unit}"

    display_next_payroll = "Not scheduled"
    if next_payroll_date:
        display_next_payroll = next_payroll_date.strftime("%b %d, %Y")

    display_overtime_multiplier = None
    if overtime_enabled:
        display_overtime_multiplier = f"{overtime_multiplier:.1f}x"

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


_SINGULAR_TIME_UNIT = {
    'seconds': 'second',
    'minutes': 'minute',
    'hours': 'hour',
    'days': 'day',
}

#: Seconds in one of each selectable time unit — the same integer map
#: ``app/payroll.py:_round_billable_seconds`` uses, so the two cannot disagree
#: about what an "hour" is.
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


def build_payroll_settings_display(settings: PayrollSettings | None) -> dict[str, str]:
    """
    Build pre-formatted pay rate display strings for a single PayrollSettings row.

    Eliminates template-level "%.2f"|format() currency formatting used for the
    Settings tab "Current Settings" summary and the simple/advanced pay rate
    input pre-population (audit violation: admin_payroll.html pay_rate formatting).

    Args:
        settings: PayrollSettings model instance, or None

    Returns:
        Dict with:
            display_pay_rate: "$X.XX" selected by settings_mode (hourly rate for
                'simple' mode, per-time-unit rate for 'advanced' mode)
            display_hourly_rate_value: plain "X.XX" hourly rate (no "$"), for the
                simple-mode pay rate input value attribute
            display_per_unit_rate_value: plain "X.XX" per-time-unit rate (no "$"),
                for the advanced-mode pay rate input value attribute
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
    display_hourly_value = f"{rate * 60:.2f}"
    # Expressed in the unit the teacher configured, not the storage unit. This
    # value also pre-populates the Advanced pay-rate input, so a mismatch here
    # is not cosmetic: it round-trips through the next save.
    display_per_unit_value = f"{rate_per_minute_to_unit(rate, settings.time_unit):.2f}"

    if settings.settings_mode == 'simple':
        display_pay_rate = f"${display_hourly_value}"
    else:
        display_pay_rate = f"${display_per_unit_value}"

    # `time_unit` is stored plural ('minutes', 'hours') because it names a
    # duration. A *rate* is per one of them, so rendering the stored value
    # directly produced "$1.50/minutes" on the settings summary. Singularised
    # here rather than in the template: the template renders what it is handed.
    unit = (settings.time_unit or '').strip()
    display_rate_unit = _SINGULAR_TIME_UNIT.get(unit, unit)

    if settings.settings_mode == 'simple':
        display_rate_with_unit = f"{display_pay_rate}/hour"
    elif display_rate_unit:
        display_rate_with_unit = f"{display_pay_rate}/{display_rate_unit}"
    else:
        display_rate_with_unit = display_pay_rate

    return {
        'display_pay_rate': display_pay_rate,
        'display_hourly_rate_value': display_hourly_value,
        'display_per_unit_rate_value': display_per_unit_value,
        'display_rate_unit': display_rate_unit,
        'display_rate_with_unit': display_rate_with_unit,
    }
