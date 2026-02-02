
import uuid
from datetime import datetime, timezone
from app import db
from app.models import Admin, Student, StudentTeacher, TapEvent, TeacherBlock
from app.attendance import get_all_block_statuses

def test_attendance_status_isolation(client):
    """
    Verify that attendance status (Active/Inactive) is isolated between teachers
    even if they share the same block name.
    """
    # 1. Setup Teachers
    t1 = Admin(username=f"t1_{uuid.uuid4().hex[:8]}", totp_secret='secret')
    t2 = Admin(username=f"t2_{uuid.uuid4().hex[:8]}", totp_secret='secret')
    db.session.add_all([t1, t2])
    db.session.commit()

    # 2. Setup Student
    student = Student(
        first_name="Shared",
        last_initial="S",
        block="PERIOD 1",
        salt=b'salt'
    )
    db.session.add(student)
    db.session.commit()

    # 3. Create Links & Seats
    db.session.add(StudentTeacher(student_id=student.id, admin_id=t1.id))
    db.session.add(StudentTeacher(student_id=student.id, admin_id=t2.id))
    
    tb1 = TeacherBlock(
        teacher_id=t1.id, block="PERIOD 1", join_code="JC1", student_id=student.id, is_claimed=True,
        first_name="Shared", last_initial="S", salt=b'salt', first_half_hash="hash", dob_sum=10, last_name_hash_by_part="hash"
    )
    tb2 = TeacherBlock(
        teacher_id=t2.id, block="PERIOD 1", join_code="JC2", student_id=student.id, is_claimed=True,
        first_name="Shared", last_initial="S", salt=b'salt', first_half_hash="hash", dob_sum=10, last_name_hash_by_part="hash"
    )
    db.session.add_all([tb1, tb2])
    db.session.commit()

    # 4. Tap In for T1 (JC1)
    now = datetime.now(timezone.utc)
    tap = TapEvent(student_id=student.id, period="PERIOD 1", status="active", timestamp=now, join_code="JC1")
    db.session.add(tap)
    db.session.commit()
    
    # 5. Check Status via get_all_block_statuses WITH Join Code (Scoped View)
    # T1 View
    status_t1 = get_all_block_statuses(student, join_code="JC1")
    assert "PERIOD 1" in status_t1
    assert status_t1["PERIOD 1"]["active"] is True

    # T2 View (Scoped)
    status_t2 = get_all_block_statuses(student, join_code="JC2")
    assert "PERIOD 1" in status_t2
    # Should NOT be active because tap was for JC1
    assert status_t2["PERIOD 1"]["active"] is False

    # 6. Check Status via Global View (No Join Code)
    # This is where we expect potential ambiguity/leak if code iterates string blocks
    global_status = get_all_block_statuses(student, join_code=None)

    # Without join_code scoping, the function iterates student.block string which
    # contains "PERIOD 1, PERIOD 1" (duplicated block names). The dict key is the
    # block name, so collisions occur.
    assert "PERIOD 1" in global_status

    # The global view (no join_code) will show the status from the latest event
    # for "PERIOD 1" across ALL classes, which can be misleading. In this case,
    # since we only have one tap event (JC1), it will show active=True.
    # However, this is inherently ambiguous when a student has multiple classes
    # with the same block name - we can't tell WHICH class the status is for.
    assert global_status["PERIOD 1"]["active"] is True

    # NOTE: The global view is problematic for multi-teacher scenarios with
    # duplicate block names. The scoped views (passing join_code) are the
    # recommended approach for accuracy. 
