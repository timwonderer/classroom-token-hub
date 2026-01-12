"""
Attendance Helper Utilities

Shared utilities for attendance and payroll calculations.
Created to break circular dependency between attendance.py and payroll.py.
"""

from sqlalchemy import func


def get_join_code_for_student_period(student_id, period, teacher_id=None):
    """
    Resolve the join_code for a student's specific period.

    Args:
        student_id (int): ID of the student.
        period (str): Period/block identifier (case-insensitive).
        teacher_id (int, optional): Restrict lookup to a specific teacher.

    Returns:
        str | None: join_code matching the student's seat for the requested period.
    """
    from app.models import TeacherBlock

    filters = [
        TeacherBlock.student_id == student_id,
        func.upper(TeacherBlock.block) == func.upper(period)
    ]

    if teacher_id:
        filters.append(TeacherBlock.teacher_id == teacher_id)

    seat = (
        TeacherBlock.query
        .filter(*filters, TeacherBlock.is_claimed.is_(True))
        .order_by(TeacherBlock.id.desc())
        .first()
    )

    return seat.join_code if seat else None
