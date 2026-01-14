
import pytest
import pyotp
import uuid
from app import db
from app.models import Admin, Student, StudentTeacher
from app.hash_utils import get_random_salt

def test_student_count_relies_only_on_link_table(client):
    """
    Verify that teacher.get_student_count() counts students linked via StudentTeacher.
    """
    # Use random usernames to avoid collision in persistent DB
    t_username = f"harden_prof_{uuid.uuid4().hex[:8]}"
    secret = pyotp.random_base32()
    teacher = Admin(username=t_username, totp_secret=secret)
    db.session.add(teacher)
    db.session.commit()

    # Create Student (with NO teacher_id)
    s_firstname = f"Hardened_{uuid.uuid4().hex[:8]}"
    student = Student(
        first_name=s_firstname,
        last_initial='S',
        block='Period 1',
        salt=get_random_salt() 
    )
    db.session.add(student)
    db.session.commit()

    # 3. Verify count is 0 initially
    initial_count = teacher.get_student_count()
    assert initial_count == 0

    # 4. Link via StudentTeacher
    link = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    db.session.add(link)
    db.session.commit()

    # 5. Verify count is 1
    final_count = teacher.get_student_count()
    assert final_count == 1

def test_delete_teacher_cleans_up_links(client):
    """
    Verify deleting a teacher removes StudentTeacher links but keeps the student.
    """
    from app.models import SystemAdmin
    from datetime import datetime, timezone

    # Create Teacher to delete
    t1_username = f"del_target_{uuid.uuid4().hex[:8]}"
    teacher = Admin(username=t1_username, totp_secret=pyotp.random_base32())
    db.session.add(teacher)
    db.session.commit()
    teacher_id = teacher.id

    # Create Survivor Teacher
    t2_username = f"survivor_{uuid.uuid4().hex[:8]}"
    survivor_teacher = Admin(username=t2_username, totp_secret=pyotp.random_base32())
    db.session.add(survivor_teacher)
    db.session.commit()
    survivor_teacher_id = survivor_teacher.id

    # Create Student
    s_firstname = f"Survivor_{uuid.uuid4().hex[:8]}"
    student = Student(
        first_name=s_firstname,
        last_initial='S',
        block='Period 1',
        salt=get_random_salt()
    )
    db.session.add(student)
    db.session.commit()
    student_id = student.id

    # Link to BOTH
    link1 = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    link2 = StudentTeacher(student_id=student.id, admin_id=survivor_teacher.id)
    db.session.add(link1)
    db.session.add(link2)
    db.session.commit()

    # Login as sysadmin
    sa_username = f"sysadmin_{uuid.uuid4().hex[:8]}"
    sysadmin = SystemAdmin(username=sa_username)
    sysadmin.totp_secret = 'secret'
    db.session.add(sysadmin)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess['is_system_admin'] = True
        sess['sysadmin_id'] = sysadmin.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Perform Delete
    resp = client.post(f'/sysadmin/manage-teachers/delete/{teacher_id}', follow_redirects=True)
    assert resp.status_code == 200
    
    # Verify Teacher Gone
    assert Admin.query.get(teacher_id) is None

    # Verify Student Still Exists (because linked to survivor_teacher)
    s = Student.query.get(student_id)
    assert s is not None
    
    # Verify link to deleted teacher is gone
    assert StudentTeacher.query.filter_by(student_id=student_id, admin_id=teacher_id).count() == 0
    
    # Verify link to survivor teacher remains
    assert StudentTeacher.query.filter_by(student_id=student_id, admin_id=survivor_teacher_id).count() == 1


def test_student_teacher_unique_constraint(client):
    """
    Verify that the database prevents duplicate links between the same student and teacher.
    """
    from sqlalchemy.exc import IntegrityError
    
    # Setup
    t = Admin(username=f"unique_t_{uuid.uuid4().hex}", totp_secret='s')
    s = Student(first_name="Unique", last_initial="S", block="B", salt=b's')
    db.session.add_all([t, s])
    db.session.commit()
    
    # First Link
    link1 = StudentTeacher(student_id=s.id, admin_id=t.id)
    db.session.add(link1)
    db.session.commit()
    
    # Duplicate Link
    link2 = StudentTeacher(student_id=s.id, admin_id=t.id)
    db.session.add(link2)
    
    # Verify IntegrityError
    with pytest.raises(IntegrityError):
        db.session.commit()
    
    db.session.rollback()
