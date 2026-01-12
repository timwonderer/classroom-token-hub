"""
PRE-MIGRATION VERIFICATION SCRIPT

WARNING: This script is designed to run BEFORE the migration that drops the teacher_id column.
After migration 1e07c37d3c7c is applied, the teacher_id field will no longer exist,
and this script will fail. Use only for pre-migration verification.

For post-migration verification, check StudentTeacher links only.
"""

from app import create_app
from app.models import Student, StudentTeacher, TeacherBlock

app = create_app()

with app.app_context():
    total_students = Student.query.count()

    # Students without any StudentTeacher links (The "Legacy" or "Orphan" ones)
    unlinked_students = Student.query.outerjoin(StudentTeacher).filter(StudentTeacher.id.is_(None)).count()

    # Students with TeacherBlock seats claim
    claimed_seats = TeacherBlock.query.filter_by(is_claimed=True).count()

    print(f"Total Students: {total_students}")
    print(f"Students with NO StudentTeacher links (Unmigrated/Orphans): {unlinked_students}")
    print(f"Total Claimed TeacherBlock Seats: {claimed_seats}")

    # Check for legacy teacher_id if column still exists
    try:
        legacy_teacher_id_count = Student.query.filter(Student.teacher_id.isnot(None)).count()
        print(f"Students with legacy 'teacher_id' set: {legacy_teacher_id_count}")
    except Exception as e:
        print("Note: teacher_id column no longer exists (migration already applied)")

    if unlinked_students == 0:
        print("\nSUCCESS: All students have StudentTeacher links.")
    else:
        print(f"\nWARNING: {unlinked_students} students have NO StudentTeacher links. Investigate before removing legacy dependencies.")
