"""Teacher-note (IdentityProfile.notes) render surface and its class scoping.

The note is teacher-authored free text about one seat in one class. Its only
enforceable contract is encryption at rest plus single-teacher, single-class
visibility, so these tests pin two things:

  - the note is readable back on the surfaces that render it, and
  - it never crosses a class boundary, including between two classes owned by
    the same teacher (Ava Chen holds a different note in chemistry_p1 and in
    ap_csp_p3, both under teacher_alice).

The read path must be a class-scoped query in the rendering request, never the
session-cached DisplayMetadata — serializing a decrypted note into the session
cookie is an INV-ARC-005 exposure.
"""
from __future__ import annotations

import re
from dataclasses import fields

from app.models import IdentityProfile
from app.utils.display_metadata import (
    DISPLAY_METADATA_SESSION_KEY,
    DisplayMetadata,
    get_cached_display_metadata,
)
from tests.helpers.canonical_classroom import login_teacher, provision_classroom

CHEM_AVA_NOTE = "Excellent lab partner"
CSP_AVA_NOTE = "Always finishes early"


def _seat_for(classroom, first_name):
    for student in classroom.students:
        if student.first_name == first_name:
            return student
    raise AssertionError(f"{first_name} not in roster")


def _detail_url_for(roster_html, public_id):
    """Pull the signed student-detail URL the roster rendered for this seat.

    Detail access is gated by a signed nav token, so tests navigate the way a
    teacher does rather than forging one.
    """
    match = re.search(
        rf'href="(/admin/students/{re.escape(public_id)}\?nav=[^"]+)"',
        roster_html,
    )
    assert match, f"roster did not link to seat {public_id}"
    return match.group(1).replace("&amp;", "&")


def test_student_detail_renders_teacher_note(app, client):
    """The teacher can read back the note they wrote, on the student detail page."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        ava = _seat_for(classroom, "Ava")
        public_id = ava.seat.public_id
        login_teacher(client, classroom)

    roster = client.get("/admin/students")
    assert roster.status_code == 200

    detail = client.get(_detail_url_for(roster.get_data(as_text=True), public_id))
    assert detail.status_code == 200
    assert CHEM_AVA_NOTE in detail.get_data(as_text=True)


def test_roster_exposes_teacher_note_for_active_class(app, client):
    """The roster edit modal is hydrated with the note for the active class."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)

    roster = client.get("/admin/students")
    assert roster.status_code == 200
    assert CHEM_AVA_NOTE in roster.get_data(as_text=True)


def test_teacher_note_does_not_cross_class_boundary_for_same_teacher(app, client):
    """Same teacher, same student, two classes — only the active class's note renders.

    This is the isolation case that a teacher_id-only scope would leak: Ava Chen
    holds a seat in both chemistry_p1 and ap_csp_p3 under teacher_alice.
    """
    with app.app_context():
        chemistry = provision_classroom("chemistry_p1")
        csp = provision_classroom("ap_csp_p3")
        csp_ava_public_id = _seat_for(csp, "Ava").seat.public_id
        # Act inside chemistry_p1.
        login_teacher(client, chemistry)

    roster = client.get("/admin/students")
    body = roster.get_data(as_text=True)
    assert CHEM_AVA_NOTE in body
    assert CSP_AVA_NOTE not in body

    # The other class's seat is not reachable from this class scope at all.
    leaked = client.get(f"/admin/students/{csp_ava_public_id}")
    assert leaked.status_code == 404


def test_teacher_note_not_reachable_across_teachers(app, client):
    """A note on another teacher's seat is not readable, even for the same student name."""
    with app.app_context():
        chemistry = provision_classroom("chemistry_p1")
        biology = provision_classroom("biology_block_a")
        other_seat_public_id = _seat_for(biology, "Ava").seat.public_id
        login_teacher(client, chemistry)

    resp = client.get(f"/admin/students/{other_seat_public_id}")
    assert resp.status_code == 404


def test_teacher_note_is_never_written_into_the_session(app, client):
    """INV-ARC-005: no decrypted note may be serialized into the session cookie."""
    assert "teacher_note" not in {f.name for f in fields(DisplayMetadata)}

    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)

    assert client.get("/admin/students").status_code == 200

    with client.session_transaction() as sess:
        cached = sess.get(DISPLAY_METADATA_SESSION_KEY) or {}
        assert "teacher_note" not in cached
        serialized = " ".join(str(v) for v in cached.values())
        assert CHEM_AVA_NOTE not in serialized


def test_stale_session_metadata_is_discarded_not_fatal(app, client):
    """A cookie signed before teacher_note was dropped must not 500 the request.

    Sessions outlive deploys, so the cached shape is an external boundary.
    """
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)

    assert client.get("/admin/students").status_code == 200

    with client.session_transaction() as sess:
        stale = dict(sess[DISPLAY_METADATA_SESSION_KEY])
        stale["teacher_note"] = CHEM_AVA_NOTE
        sess[DISPLAY_METADATA_SESSION_KEY] = stale

    # Serving the request again must succeed (cache rejected, then re-resolved).
    again = client.get("/admin/students")
    assert again.status_code == 200

    with client.session_transaction() as sess:
        assert "teacher_note" not in sess[DISPLAY_METADATA_SESSION_KEY]


def test_edit_student_persists_the_note(app, client):
    """Editing the note through the real route must survive the request.

    The route mutates the profile inside @requires_feat_context("FEAT-IDEN-006")
    and never calls db.session.commit() itself; the FEAT transaction boundary is
    what persists it. This pins that the write actually lands.
    """
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        ava = _seat_for(classroom, "Ava")
        seat_id = ava.seat_id
        class_id = classroom.class_id
        login_teacher(client, classroom)

    resp = client.post("/admin/student/edit", data={
        "seat_id": seat_id,
        "first_name": "Ava",
        "last_name": "Chen",
        "notes": "Moved to front row",
    })
    assert resp.status_code == 302

    with app.app_context():
        profile = IdentityProfile.query.filter_by(
            seat_id=seat_id, class_id=class_id,
        ).first()
        assert profile.notes == "Moved to front row"


def test_edit_student_cannot_write_a_note_outside_the_active_class(app, client):
    """A seat in another class must not be writable from this class scope."""
    with app.app_context():
        chemistry = provision_classroom("chemistry_p1")
        csp = provision_classroom("ap_csp_p3")
        csp_ava = _seat_for(csp, "Ava")
        csp_seat_id = csp_ava.seat_id
        csp_class_id = csp.class_id
        login_teacher(client, chemistry)

    resp = client.post("/admin/student/edit", data={
        "seat_id": csp_seat_id,
        "first_name": "Ava",
        "last_name": "Chen",
        "notes": "written from the wrong class",
    })
    assert resp.status_code == 404

    with app.app_context():
        profile = IdentityProfile.query.filter_by(
            seat_id=csp_seat_id, class_id=csp_class_id,
        ).first()
        assert profile.notes == CSP_AVA_NOTE


def test_cached_metadata_rejects_payload_missing_new_fields(app):
    """A cookie predating a *added* field is also rejected rather than decoded."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")

        from app.services.context_resolver import CanonicalContext
        ctx = CanonicalContext(
            user_id=classroom.teacher_user_id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat_id,
            actor_role="teacher",
        )

        with app.test_request_context():
            from flask import session as flask_session
            flask_session[DISPLAY_METADATA_SESSION_KEY] = {"context_key": "x"}
            assert get_cached_display_metadata(ctx) is None
