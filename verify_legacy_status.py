
from app import create_app, db
from app.models import Student, StudentTeacher, TeacherBlock

app = create_app()

with app.app_context():
    total_students = Student.query.count()
    
    # Students without any StudentTeacher links (The "Legacy" or "Orphan" ones)
    unlinked_students = Student.query.outerjoin(StudentTeacher).filter(StudentTeacher.id == None).count()
    
    # Students with teacher_id set (Legacy Marker)
    legacy_teacher_id_count = Student.query.filter(Student.teacher_id != None).count()
    
    # Students with TeacherBlock seats claim
    claimed_seats = TeacherBlock.query.filter_by(is_claimed=True).count()
    
    print(f"Total Students: {total_students}")
    print(f"Students with NO StudentTeacher links (Unmigrated/Orphans): {unlinked_students}")
    print(f"Students with legacy 'teacher_id' set: {legacy_teacher_id_count}")
    print(f"Total Claimed TeacherBlock Seats: {claimed_seats}")
    
    if unlinked_students == 0:
        print("\nSUCCESS: All students have StudentTeacher links. Legacy teacher_id dependency can be safely removed.")
    else:
        print(f"\nWARNING: {unlinked_students} students have NO links. Removing teacher_id dependency might break them.")
