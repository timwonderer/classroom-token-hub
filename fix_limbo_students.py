#!/usr/bin/env python
"""
Fix limbo student records that are linked to multiple TeacherBlocks.

A limbo student is one that:
1. Has no username_hash (never completed setup)
2. Is linked to multiple TeacherBlocks

The fix: Unlink all TeacherBlocks except the first one from the student.
"""

from wsgi import app
from app.models import TeacherBlock, Student, db

with app.app_context():
    # Find students with no username but linked to TeacherBlocks
    limbo_students = db.session.execute(db.text("""
        SELECT s.id, COUNT(tb.id) as tb_count
        FROM students s
        INNER JOIN teacher_blocks tb ON s.id = tb.student_id
        WHERE s.username_hash IS NULL
        GROUP BY s.id
        HAVING COUNT(tb.id) > 1
    """)).fetchall()
    
    print(f"Found {len(limbo_students)} limbo student(s)")
    print()
    
    for student_id, tb_count in limbo_students:
        student = Student.query.get(student_id)
        print(f"Student {student_id}: {student.first_name}/{student.last_initial}")
        print(f"  Linked to {tb_count} TeacherBlocks")
        
        # Get all TeacherBlocks linked to this student
        tbs = TeacherBlock.query.filter_by(student_id=student_id).order_by(TeacherBlock.id).all()
        
        # Keep the first one, unlink the rest
        for  i, tb in enumerate(tbs):
            if i == 0:
                print(f"    [KEEP] TB {tb.id}: {tb.join_code} - is_claimed={tb.is_claimed}")
            else:
                print(f"    [UNLINK] TB {tb.id}: {tb.join_code} - is_claimed={tb.is_claimed}")
                # Unlink this TeacherBlock from the student
                tb.student_id = None
                if tb.is_claimed:
                    tb.is_claimed = False
        
        print()
    
    if limbo_students:
        print("Committing changes...")
        db.session.commit()
        print("✅ Fixed!")
    else:
        print("✅ No limbo students found!")
