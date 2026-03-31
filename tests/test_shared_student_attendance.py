
import uuid
from datetime import datetime, timezone
from app import db
from app.models import Admin, Seat, Student, StudentTeacher, TapEvent
from app.attendance import get_all_block_statuses
from tests.helpers.class_scope import create_class_scope

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
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=t1.id))
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=t2.id))
    create_class_scope(
        teacher=t1,
        join_code="JC1",
        student=student,
        block="PERIOD 1",
        display_name="PERIOD 1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    create_class_scope(
        teacher=t2,
        join_code="JC2",
        student=student,
        block="PERIOD 1",
        display_name="PERIOD 1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JC1").first()
    assert seat is not None

    # 4. Tap In for T1 (JC1)
    now = datetime.now(timezone.utc)
    tap = TapEvent(student_id=student.id, seat_id=seat.id, period="PERIOD 1", status="active", timestamp=now, join_code="JC1")
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
    # The non-scoped helper now resolves through a single class context and remains
    # seat-scoped, so it should not leak JC1 activity into the other class.
    global_status = get_all_block_statuses(student, join_code=None)
    assert "PERIOD 1" in global_status
    assert global_status["PERIOD 1"]["active"] is False
