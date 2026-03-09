#!/usr/bin/env python
"""Debug script to find orphaned or duplicate student records."""

from wsgi import app
from app.models import Student, TeacherBlock, StudentTeacher
from sqlalchemy import func, text

with app.app_context():
    # Find students with no TeacherBlocks (orphaned)
    print('=== Students with No TeacherBlocks (Orphaned) ===')
    orphaned = Student.query.outerjoin(TeacherBlock).filter(TeacherBlock.id == None).all()
    if orphaned:
        for s in orphaned:
            print(f'ID {s.id}: {s.first_name}/{s.last_initial} | Username: {"SET" if s.username_hash else "NOT SET"}')
    else:
        print("(none)")
    
    print()
    print('=== Students with Multiple TeacherBlocks ===')
    # Find students linked to multiple TeacherBlocks
    dup_query = Student.query.join(TeacherBlock).group_by(Student.id).having(func.count(TeacherBlock.id) > 1)
    dup_students = dup_query.all()
    if dup_students:
        for s in dup_students:
            tbs = TeacherBlock.query.filter_by(student_id=s.id).all()
            print(f'ID {s.id}: {s.first_name}/{s.last_initial} | Has {len(tbs)} TeacherBlocks')
            for tb in tbs:
                print(f'  - TB {tb.id}: join_code={tb.join_code}, is_claimed={tb.is_claimed}')
    else:
        print("(none)")
    
    print()
    print('=== All Unclaimed TeacherBlocks ===')
    unclaimed = TeacherBlock.query.filter_by(is_claimed=False).all()
    print(f"Total unclaimed: {len(unclaimed)}")
    for tb in unclaimed[-5:]:  # Show last 5
        print(f'TB {tb.id}: {tb.first_name}/{tb.last_initial} join_code={tb.join_code} student_id={tb.student_id}')
