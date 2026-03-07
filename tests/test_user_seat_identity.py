import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Seat, User


def test_user_can_hold_multiple_join_code_seats(client):
    user = User(username="user_a", password_hash="hash_a")
    db.session.add(user)
    db.session.flush()

    db.session.add(Seat(user_id=user.id, join_code="JOIN_A", block="A"))
    db.session.add(Seat(user_id=user.id, join_code="JOIN_B", block="B"))
    db.session.commit()

    seats = Seat.query.filter_by(user_id=user.id).order_by(Seat.join_code.asc()).all()
    assert [s.join_code for s in seats] == ["JOIN_A", "JOIN_B"]


def test_user_cannot_have_duplicate_seat_for_same_join_code(client):
    user = User(username="user_b", password_hash="hash_b")
    db.session.add(user)
    db.session.flush()

    db.session.add(Seat(user_id=user.id, join_code="JOIN_X", block="X"))
    db.session.commit()

    db.session.add(Seat(user_id=user.id, join_code="JOIN_X", block="X"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_different_users_can_share_same_join_code(client):
    user1 = User(username="user_c1", password_hash="hash_c1")
    user2 = User(username="user_c2", password_hash="hash_c2")
    db.session.add_all([user1, user2])
    db.session.flush()

    db.session.add(Seat(user_id=user1.id, join_code="JOIN_SHARED", block="A"))
    db.session.add(Seat(user_id=user2.id, join_code="JOIN_SHARED", block="A"))
    db.session.commit()

    shared = Seat.query.filter_by(join_code="JOIN_SHARED").all()
    assert len(shared) == 2
