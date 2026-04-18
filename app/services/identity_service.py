from __future__ import annotations

from app.extensions import db
from app.models import StudentBlock


def add_hall_passes(student, quantity: int) -> int:
    """Identity-owned mutation for hall-pass counters."""
    current_total = max(0, int(student.hall_passes or 0))
    student.hall_passes = current_total + int(quantity)
    db.session.add(student)
    return student.hall_passes


def reconcile_rent_hall_pass_top_off(
    *,
    student,
    join_code: str,
    current_block: str,
    target_rent_passes: int,
):
    """
    Identity-owned mutation for rent-provided hall passes.

    Returns (passes_awarded, passes_revoked, state_changed).
    """
    if not student or not join_code or not current_block:
        return 0, 0, False

    current_block = current_block.strip().upper()
    student_block = StudentBlock.query.filter(
        StudentBlock.student_id == student.id,
        StudentBlock.period == current_block,
        StudentBlock.join_code == join_code,
    ).first()

    state_changed = False
    target_rent_passes = max(0, int(target_rent_passes or 0))

    if not student_block and target_rent_passes > 0:
        student_block = StudentBlock(
            student_id=student.id,
            period=current_block,
            join_code=join_code,
            rent_hall_passes=0,
        )
        db.session.add(student_block)
        state_changed = True

    current_total_passes = max(0, int(student.hall_passes or 0))
    current_rent_passes = max(0, int(student_block.rent_hall_passes or 0)) if student_block else 0
    effective_rent_passes = min(current_rent_passes, current_total_passes)
    delta = target_rent_passes - effective_rent_passes
    passes_awarded = max(0, delta)
    passes_revoked = max(0, -delta)

    if delta != 0:
        student.hall_passes = current_total_passes + delta
        db.session.add(student)
        state_changed = True

    if student_block and student_block.rent_hall_passes != target_rent_passes:
        student_block.rent_hall_passes = target_rent_passes
        state_changed = True

    return passes_awarded, passes_revoked, state_changed
