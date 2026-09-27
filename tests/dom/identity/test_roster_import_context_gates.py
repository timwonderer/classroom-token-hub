"""Roster import refuses to write without lawful class context, and never logs names.

``POST /admin/upload-students`` is the only way a teacher adds students; v2 has
no separate single-student add (the v1 ``/admin/student/add-individual`` route
was removed 2026-09-27, REF-API-001 §VII-D). These are negative tests of the
live path. Runtime class authority is the User's canonical pointers
(``last_active_class_id`` / ``last_active_seat_id``, DOM-IDEN-006), so each
case corrupts or removes *those*, or supplies a competing class selector, and
asserts that nothing was written anywhere.
"""

from __future__ import annotations

import logging

from app.extensions import db
from app.feats.base import FEATContext
from app.models import IdentityProfile, Seat, User
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _seat_count(class_id: str) -> int:
    return Seat.query.filter_by(class_id=class_id, role="student").count()


def _profile_count(class_id: str) -> int:
    return IdentityProfile.query.filter_by(class_id=class_id).count()


def _set_pointers(user_id: int, *, class_id, seat_id, key: str) -> None:
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"import-gates:{key}"):
        user = db.session.get(User, user_id)
        user.last_active_class_id = class_id
        user.last_active_seat_id = seat_id
        db.session.flush()


ROWS = [{"first_name": "Gatekept", "last_name": "Student"}]


def test_DOM_IDEN_006__import_refuses_without_an_active_class(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    _set_pointers(classroom.teacher_user.id, class_id=None, seat_id=None, key="no-class")
    seats, profiles = _seat_count(classroom.class_id), _profile_count(classroom.class_id)

    response = client.post("/admin/upload-students", json={"students": ROWS})

    assert response.status_code == 400
    db.session.expire_all()
    assert _seat_count(classroom.class_id) == seats
    assert _profile_count(classroom.class_id) == profiles


def test_DOM_IDEN_006__import_writes_only_into_the_active_class(client):
    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    assert active.teacher_user.id == other.teacher_user.id
    active_before, other_before = _seat_count(active.class_id), _seat_count(other.class_id)

    response = client.post("/admin/upload-students", json={"students": ROWS})

    assert response.status_code == 200
    db.session.expire_all()
    assert _seat_count(active.class_id) == active_before + 1
    assert _seat_count(other.class_id) == other_before


def test_DOM_IDEN_006__import_ignores_or_refuses_a_competing_class_selector(client):
    """A request-body class_id naming the teacher's other class is an assertion,
    not authority: it must never redirect the write into that class."""
    other = initialize("ap_csp_p3", client.application)
    initialize_as_teacher("chemistry_p1", client, client.application)
    seats_before, profiles_before = _seat_count(other.class_id), _profile_count(other.class_id)

    client.post("/admin/upload-students", json={"students": ROWS, "class_id": other.class_id})

    db.session.expire_all()
    assert _seat_count(other.class_id) == seats_before
    assert _profile_count(other.class_id) == profiles_before


def test_DOM_IDEN_006__import_refuses_a_seat_pointer_from_another_class(client):
    """last_active_seat_id pointing into the teacher's other class is a corrupted
    canonical context (ContextMismatch). The request must fail closed."""
    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    foreign_teacher_seat = Seat.query.filter_by(class_id=other.class_id, role="teacher").one()
    _set_pointers(
        active.teacher_user.id,
        class_id=active.class_id,
        seat_id=foreign_teacher_seat.id,
        key="foreign-seat",
    )
    active_before, other_before = _seat_count(active.class_id), _seat_count(other.class_id)

    response = client.post("/admin/upload-students", json={"students": ROWS})

    assert response.status_code in (302, 401)
    db.session.expire_all()
    assert _seat_count(active.class_id) == active_before
    assert _seat_count(other.class_id) == other_before


def test_INV_ARC_005__import_never_logs_student_names(client, caplog):
    """Neither a successful import nor a refused one puts a student's name in
    the application log (INV-CORE-000 §III.2, INV-ARC-005)."""
    initialize_as_teacher("chemistry_p1", client, client.application)
    first, last = "Zephyrine", "Quillsbury"

    with caplog.at_level(logging.DEBUG):
        ok = client.post(
            "/admin/upload-students",
            json={"students": [{"first_name": first, "last_name": last}]},
        )
        refused = client.post(
            "/admin/upload-students",
            json={"students": [
                {"first_name": f"{first}two", "last_name": last},
                {"first_name": "", "last_name": "Invalid"},
            ]},
        )

    assert ok.status_code == 200
    assert refused.status_code == 400
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert first not in text, "a student's first name reached the application log"
    assert last not in text, "a student's last name reached the application log"
