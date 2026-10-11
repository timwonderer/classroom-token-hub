"""FEAT-IDEN-002 Step 4.2 PIN format, enforced server-side (audit S8).

``student_pin_setup.html`` only checks ``/^\\d{4,6}$/`` in the browser. A
crafted POST bypassed that entirely: the activation path hashed whatever PIN
arrived with no length, repeated-digit, or sequential check, although the
FEAT contract's failure table names exactly those three. These exercise the
real setup route end to end against ``activate_student_credentials``.
"""
from __future__ import annotations

import pytest

from app.models import Seat, User
from tests.dom.identity.helpers import (
    TEST_STUDENT_PASSPHRASE as PASSPHRASE,
    student_create_username,
    student_setup_pin_passphrase,
)
from tests.helpers.classroom_initializer import initialize_as_teacher

INVALID_PIN_MESSAGE = "PIN must be 4-6 digits, not all the same or sequential."


def _unclaim(client, seat):
    return client.post('/admin/student/unclaim', json=dict(
        seat_id=seat.id, claim_generation=seat.claim_generation,
        first_name='Fresh', last_name='Claim', confirmation='UNCLAIM'))


@pytest.fixture
def claiming(client, app):
    """A student part-way through claiming a seat, with a username generated."""
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    assert _unclaim(client, seat).status_code == 200
    with client.session_transaction() as sess:
        sess.clear()
    response = client.post('/student/claim-account', data=dict(
        join_code=classroom.join_code, first_name='Fresh', last_name='Claim'))
    assert response.status_code == 302 and '/create-username' in response.location
    assert student_create_username(client, 'otter', follow_redirects=False).status_code == 302
    return {"seat_id": seat.id}


@pytest.mark.parametrize("pin", [
    "123",          # too short
    "1234567",      # too long
    "abcd",         # not digits
    "1111",         # all the same
    "1234",         # ascending sequential
    "4321",         # descending sequential
    "654321",       # descending sequential, 6 digits
    "",             # empty
])
def test_a_malformed_pin_is_refused_and_nothing_is_created(client, app, claiming, pin):
    seat_id = claiming["seat_id"]
    response = student_setup_pin_passphrase(
        client, pin=pin, confirm_pin=pin, passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=True,
    )
    assert response.status_code == 200
    assert INVALID_PIN_MESSAGE.encode() in response.data or pin == ""
    with app.app_context():
        seat = Seat.query.filter_by(id=seat_id).one()
        assert seat.user_id is None, "a malformed PIN must not complete the claim"


@pytest.mark.parametrize("pin", ["4290", "13579", "048372"])
def test_a_well_formed_non_sequential_pin_is_accepted(client, app, claiming, pin):
    seat_id = claiming["seat_id"]
    response = student_setup_pin_passphrase(
        client, pin=pin, confirm_pin=pin, passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=True,
    )
    assert response.status_code == 200
    assert INVALID_PIN_MESSAGE.encode() not in response.data
    with app.app_context():
        seat = Seat.query.filter_by(id=seat_id).one()
        assert seat.user_id is not None
        user = User.query.filter_by(id=seat.user_id).one()
        assert user.pin_hash is not None


def test_a_single_repeated_nonstart_digit_run_is_not_falsely_flagged_sequential(client, app, claiming):
    """1221 is neither ascending nor descending nor all-same; must be accepted."""
    seat_id = claiming["seat_id"]
    response = student_setup_pin_passphrase(
        client, pin="1221", confirm_pin="1221", passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=True,
    )
    assert response.status_code == 200
    assert INVALID_PIN_MESSAGE.encode() not in response.data
    with app.app_context():
        assert Seat.query.filter_by(id=seat_id).one().user_id is not None
