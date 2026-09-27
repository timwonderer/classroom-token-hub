"""FEAT-IDEN-003: one path issues student reset codes, scoped to the active class.

Two paths used to issue codes. The roster edit form issued them inside
FEAT-IDEN-006, which is the wrong authority for recovery. A separate
``/recovery/admin/generate-code/<seat_id>`` route ran FEAT-IDEN-003 but
checked only that the teacher owned the seat's class, so a seat in any other
class the teacher owned would do. Both are gone. ``POST /admin/student/reset-code``
runs FEAT-IDEN-003 against the request's active class (INV-ARC-004 §V.1),
requires a claimed student seat and the actor's own teacher seat in that class
(DOM-IDEN-002 §IX Step 1, FEAT-IDEN-003 §III.A), and never logs the code.
"""

from __future__ import annotations

import logging

import pytest

from app import db
from app.feats.base import get_active_feat_name
from app.models import Seat, User
from app.services.student_recovery import is_trivially_weak_reset_code
from tests.dom.identity.helpers import admin_generate_recovery_code
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


@pytest.fixture
def issuer_calls(monkeypatch):
    """Record the FEAT active whenever a reset code is actually issued."""
    import app.services.student_recovery as module

    seen: list[str | None] = []
    original = module.issue_student_recovery_code

    def wrapper(*args, **kwargs):
        seen.append(get_active_feat_name())
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "issue_student_recovery_code", wrapper)
    return seen


def _reset_code(seat):
    db.session.expire_all()
    return db.session.get(User, seat.user_id).reset_code


def test_DOM_IDEN_002__reset_code_is_issued_under_feat_iden_003(client, issuer_calls):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = classroom.students[0].seat

    response = admin_generate_recovery_code(client, seat.id)

    assert response.status_code == 302
    assert issuer_calls == ["FEAT-IDEN-003"]
    code = _reset_code(seat)
    assert code is not None and len(code) == 8


def test_INV_ARC_004__a_seat_in_another_owned_class_is_refused(client, issuer_calls):
    """The previous route accepted any seat in any class the teacher owned."""
    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    assert active.teacher_user.id == other.teacher_user.id
    foreign_seat = other.students[0].seat

    response = admin_generate_recovery_code(client, foreign_seat.id)

    assert response.status_code == 302
    assert issuer_calls == []
    assert _reset_code(foreign_seat) is None


def test_DOM_IDEN_002__an_unclaimed_seat_gets_no_reset_code(client, issuer_calls):
    from app.feats.base import FEATContext
    from app.services.classroom_setup import create_student_seat_with_profile

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="reset:unclaimed"):
        pending = create_student_seat_with_profile(
            class_id=classroom.class_id, first_name="Pending", last_name="Student",
        )

    response = admin_generate_recovery_code(client, pending.id)

    assert response.status_code == 302
    assert issuer_calls == []
    db.session.expire_all()
    assert db.session.get(Seat, pending.id).user_id is None


def test_DOM_IDEN_002__the_roster_edit_form_no_longer_issues_codes(client, issuer_calls):
    """Recovery left FEAT-IDEN-006: posting the retired ``reset_login`` field
    with an edit changes the name and issues nothing."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0]

    response = client.post(
        "/admin/student/edit",
        data={
            "seat_id": student.seat.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "reset_login": "on",
        },
    )

    assert response.status_code == 302
    assert issuer_calls == []
    assert _reset_code(student.seat) is None


def test_FEAT_IDEN_003__the_reset_code_never_reaches_the_log(client, caplog):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = classroom.students[0].seat

    with caplog.at_level(logging.DEBUG):
        admin_generate_recovery_code(client, seat.id)

    code = _reset_code(seat)
    assert code
    assert code not in "\n".join(record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "code, weak",
    [
        ("AAAAAAAA", True),   # one repeated character
        ("ABCDEFGH", True),   # ascending run through the alphabet
        ("HGFEDCBA", True),   # descending run
        ("23456789", True),   # run through the digits
        ("ABCDEFGJ", False),  # near miss: G -> J skips H
        ("A7F2K9M3", False),
    ],
)
def test_FEAT_IDEN_003__trivially_weak_codes_are_recognised(code, weak):
    assert is_trivially_weak_reset_code(code) is weak


def test_FEAT_IDEN_003__a_weak_draw_is_never_issued(client, monkeypatch):
    """Force the first draw to be all one character; the issuer must redraw."""
    import app.services.student_recovery as module

    from types import SimpleNamespace

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = classroom.students[0].seat
    # Patch only this module's view of ``secrets``: the shared module also
    # salts password hashes.
    draws = iter("A" * 8 + "A7F2K9M3")
    monkeypatch.setattr(module, "secrets", SimpleNamespace(choice=lambda _alphabet: next(draws)))

    admin_generate_recovery_code(client, seat.id)

    assert _reset_code(seat) == "A7F2K9M3"
