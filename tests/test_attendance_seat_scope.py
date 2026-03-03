from app import db
from app.hash_utils import get_random_salt
from app.models import Seat, Student, StudentBlock, TapEvent, User


def _student() -> Student:
    return Student(
        first_name="Attend",
        last_initial="A",
        block="A",
        salt=get_random_salt(),
        first_half_hash=None,
        second_half_hash=None,
    )


def test_tap_event_autofills_seat_id_from_join_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username=f"tap_user_{student.id}", password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, student_id=student.id, join_code="JOIN_TAP", block="A")
    db.session.add(seat)
    db.session.flush()

    event = TapEvent(student_id=student.id, join_code="JOIN_TAP", period="A", status="active")
    db.session.add(event)
    db.session.commit()

    db.session.refresh(event)
    assert event.seat_id == seat.id


def test_student_block_autofills_seat_id_from_join_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username=f"sb_user_{student.id}", password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, student_id=student.id, join_code="JOIN_SB", block="A")
    db.session.add(seat)
    db.session.flush()

    student_block = StudentBlock(student_id=student.id, join_code="JOIN_SB", period="A")
    db.session.add(student_block)
    db.session.commit()

    db.session.refresh(student_block)
    assert student_block.seat_id == seat.id
