"""
attendance.py – zero-logic compatibility shim.

All real implementation lives in app.services.attendance_service.
This module exists only as a backward-compatible import target so that
existing callers (routes, payroll, tests) can continue using the same
import path while we migrate them toward the service layer.

Rule: every function here must be a single-line pass-through.
"""
from app.utils.attendance_helpers import get_join_code_for_student_period  # re-export
from app.services import attendance_service as _svc
from app.services.ledger_service import get_last_payroll_time as _get_last_payroll_time


def get_last_payroll_time(student_id=None, join_code=None):
    """Compatibility wrapper – delegates to ledger_service."""
    return _get_last_payroll_time(student_id=student_id, join_code=join_code)


def calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=None):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time, join_code=join_code)


def calculate_period_attendance(student_id, period, date):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.calculate_period_attendance(student_id, period, date)


def calculate_period_attendance_utc_range(student_id, period, start_utc, end_utc):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.calculate_period_attendance_utc_range(student_id, period, start_utc, end_utc)


def get_session_status(student_id, period):
    """
    Coordination shim: resolves the ledger anchor then delegates fact
    collection to attendance_service.  Attendance service must not call
    get_last_payroll_time internally.
    """
    join_code = get_join_code_for_student_period(student_id, period)
    last_payroll_time = _get_last_payroll_time(student_id=student_id, join_code=join_code)
    return _svc.get_session_status(student_id, period, last_payroll_time=last_payroll_time, join_code=join_code)


def get_all_block_statuses(student, join_code=None):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.get_all_block_statuses(student, join_code=join_code)


def get_batch_attendance_events(student_ids, min_anchor, allowed_join_codes=None):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.get_batch_attendance_events(student_ids, min_anchor, allowed_join_codes=allowed_join_codes)


def calculate_seconds_in_memory(events, anchor):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.calculate_seconds_in_memory(events, anchor)


def batch_auto_tapout_students(admin_id):
    """Compatibility wrapper – delegates to attendance_service."""
    return _svc.batch_auto_tapout_students(admin_id)
