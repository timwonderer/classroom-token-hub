from app.extensions import db
from app.models import ClassEconomy, ClassMembership, Seat, TeacherBlock


def create_class_scope(
    *,
    teacher,
    join_code,
    student=None,
    block="A",
    display_name=None,
    class_status="active",
    create_teacher_membership=True,
    create_student_membership=True,
    create_claimed_teacher_block=False,
    teacher_block_teacher=None,
    teacher_block_student=None,
    teacher_block_claimed=False,
    create_seat=True,
):
    """Create canonical class scope for tests under the v2 join-code model."""
    class_row = ClassEconomy(
        class_id=join_code,
        join_code=join_code,
        teacher_id=teacher.id,
        display_name=display_name,
        status=class_status,
        created_by_admin_id=teacher.id,
    )
    db.session.add(class_row)
    db.session.flush()

    if create_teacher_membership:
        db.session.add(ClassMembership(
            class_id=class_row.class_id,
            join_code=join_code,
            admin_id=teacher.id,
            role="admin",
        ))

    if student is not None and create_student_membership:
        db.session.add(ClassMembership(
            class_id=class_row.class_id,
            join_code=join_code,
            student_id=student.id,
            role="student",
        ))

    if create_claimed_teacher_block or teacher_block_teacher is not None:
        roster_teacher = teacher_block_teacher or teacher
        roster_student = teacher_block_student or student
        db.session.add(TeacherBlock(
            teacher_id=roster_teacher.id,
            class_id=class_row.class_id,
            block=block,
            join_code=join_code,
            is_claimed=teacher_block_claimed,
            student_id=roster_student.id if roster_student is not None else None,
            first_name=(roster_student.first_name if roster_student is not None else "Legacy"),
            last_initial=(roster_student.last_initial if roster_student is not None else "X"),
            last_name_hash_by_part=[],
            dob_sum_hash=None,
            salt=b"salt",
            first_half_hash="hash",
        ))

    if student is not None and create_seat:
        db.session.add(Seat(
            student_id=student.id,
            class_id=class_row.class_id,
            join_code=join_code,
            block=block,
            block_identifier=block,
            role="student",
        ))

    return class_row
