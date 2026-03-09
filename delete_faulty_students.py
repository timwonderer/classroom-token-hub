#!/usr/bin/env python
"""
Delete limbo student records that were created but never completed setup.

A limbo student is one that:
1. Has no username_hash (never completed setup)
2. Has orphaned or incomplete TeacherBlock links
"""

from wsgi import app
from app.models import Student, TeacherBlock, StudentTeacher, IdentityProfile, db

with app.app_context():
    # Find students with no username (incomplete setup)
    incomplete_students = Student.query.filter(Student.username_hash == None).all()
    
    print(f"Found {len(incomplete_students)} incomplete student(s)")
    print()
    
    for student in incomplete_students:
        # Count linked TeacherBlocks
        tb_count = TeacherBlock.query.filter_by(student_id=student.id).count()
        st_count = StudentTeacher.query.filter_by(student_id=student.id).count()
        
        print(f"Deleting Student {student.id}: {student.first_name}/{student.last_initial}")
        print(f"  - No username (incomplete setup)")
        print(f"  - Linked to {tb_count} TeacherBlock(s)")
        print(f"  - Linked to {st_count} teacher(s)")
        
        # Unlink from TeacherBlocks (reset to unclaimed)
        for tb in TeacherBlock.query.filter_by(student_id=student.id).all():
            print(f"    Unlinking TB {tb.id} ({tb.join_code})")
            tb.student_id = None
            if tb.is_claimed:
                tb.is_claimed = False
        
        # Unlink from StudentTeacher relationships
        for st in StudentTeacher.query.filter_by(student_id=student.id).all():
            print(f"    Removing StudentTeacher link to teacher {st.teacher_id}")
            db.session.delete(st)
        
        # Delete the Student record
        db.session.delete(student)
        print()
    
    if incomplete_students:
        print("Committing changes...")
        db.session.commit()
        print("✅ Deleted!")
    else:
        print("✅ No incomplete students found!")
