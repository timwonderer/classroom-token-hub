"""Deleting a teacher's final class destroys the teacher principal with it.

DOM-IDEN-005 §V.6 and §VI: class teardown destroys the class's seats, including
the administrative one, and a ``users`` row holding no seat anywhere is an
invariant violation — "No constitutional exceptions exist for teacher
identities." So removing the final administrative seat removes the principal.

Before this fix ``/admin/join-code/delete`` ran FEAT-CLASS-001 unconditionally
and the confirmation surface asserted the account survives "even if this is the
only class you own", which left a seatless teacher ``users`` row behind.
"""

from __future__ import annotations

from app import db
from app.models import ClassEconomy, Seat, User
from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _class_delete_phrase(class_id: str) -> str:
    class_row = db.session.get(ClassEconomy, class_id)
    label = (class_row.display_name or "").strip() or class_row.join_code
    return f"DELETE {label}".upper()


def test_deleting_the_only_class_destroys_the_teacher_principal(client, app):
    """The last administrative seat takes the principal with it."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json().get("account_deleted") is True

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(User, teacher_user_id) is None
    assert Seat.query.filter_by(user_id=teacher_user_id).count() == 0


def test_deleting_one_of_several_classes_preserves_the_teacher_principal(client, app):
    """A teacher still seated in another class keeps their account."""
    surviving = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id
    assert surviving.teacher_user.id == teacher_user_id

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json().get("account_deleted") is None

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(User, teacher_user_id) is not None
    assert Seat.query.filter_by(
        user_id=teacher_user_id, class_id=surviving.class_id
    ).count() == 1


def test_final_class_delete_surface_warns_the_account_goes_too(client, app):
    """The confirmation page must not promise a survival it cannot deliver."""
    initialize_as_teacher("chemistry_p1", client, app)

    body = client.get("/admin/class-delete").get_data(as_text=True)
    assert "your teacher account is not deleted by this" not in body.lower()
    assert "only class" in body.lower()


def test_non_final_class_delete_surface_says_the_account_survives(client, app):
    """With another class in hand the original assurance is the true one."""
    initialize("ap_csp_p3", app)
    initialize_as_teacher("chemistry_p1", client, app)

    body = client.get("/admin/class-delete").get_data(as_text=True)
    assert "Your teacher account is not deleted by this." in body
