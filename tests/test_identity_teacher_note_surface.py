"""Teacher-note (IdentityProfile.notes) render surface and its class scoping.

The note is teacher-authored free text about one seat in one class. The platform
never parses, indexes, or interprets it, so it carries no classification of its
own: whatever a teacher types is their business, the roster page advises against
sensitive content, and it is encrypted at rest regardless. `PIIEncryptedType` on
`IdentityProfile.notes` is a storage defense for arbitrary author-supplied text,
not a declaration that the column holds PII.

Its enforceable contract is therefore scope, not classification, and that is what
these tests pin:

  - the note is readable back on the surfaces that render it, and
  - it never crosses a class boundary, including between two classes owned by
    the same teacher (Ava Chen holds a different note in chemistry_p1 and in
    ap_csp_p3, both under teacher_alice), and
  - it is not writable onto a seat outside the active class.

`teacher_note` is a required field of `DisplayMetadata` under SPEC-DISPLAY-001
section VI. `DisplayMetadata` also carries decrypted name fields
(`actor_first_name` and its siblings), and until audit S10 the whole object --
notes included -- was cached in the Flask session, a signed but unencrypted
cookie. SPEC-DISPLAY-001 v1.1 removed that session-cache allowance rather than
weaken INV-CORE-000/INV-ARC-018's no-plaintext-PII-at-rest rule, so
`resolve_display_metadata` is now the only way to get one: it is recomputed on
every request and never persisted to the session.
"""
from __future__ import annotations

import re
from dataclasses import fields

from app.models import IdentityProfile
from app.services.context_resolver import CanonicalContext
from app.utils.display_metadata import DisplayMetadata, resolve_display_metadata
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


def test_teacher_note_is_a_required_display_metadata_field(app, client):
    """SPEC-DISPLAY-001 section VI lists teacher_note among the minimum fields.

    Pinned because the field has no template consumer -- both render surfaces read
    the note from a class-scoped query in the rendering request -- so nothing else
    in the suite would fail if it were dropped from the resolver.
    """
    assert "teacher_note" in {f.name for f in fields(DisplayMetadata)}

    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        ava = _seat_for(classroom, "Ava")
        ctx = CanonicalContext(
            user_id=ava.user_id,
            class_id=classroom.class_id,
            seat_id=ava.seat_id,
            actor_role="student",
        )
        metadata = resolve_display_metadata(ctx)
        assert metadata.teacher_note == CHEM_AVA_NOTE


def test_display_metadata_is_never_written_to_the_session(app, client):
    """Audit S10 regression: ``DisplayMetadata`` carries decrypted PII
    (``actor_first_name`` and its siblings, plus this file's teacher note),
    and a prior revision cached the whole object in the Flask session -- a
    signed but unencrypted cookie, i.e. plaintext PII at rest. There is no
    longer any key that would hold it.
    """
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)

    assert client.get("/admin/students").status_code == 200

    with client.session_transaction() as sess:
        serialized = str(dict(sess))
        assert CHEM_AVA_NOTE not in serialized
        assert "display_metadata" not in sess


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


def test_resolve_display_metadata_recomputes_on_every_call(app):
    """No cache means no staleness class of bug: two calls with the same
    context independently hit the database and agree, rather than one
    serving a value the other wrote.
    """
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        ctx = CanonicalContext(
            user_id=classroom.teacher_user_id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat_id,
            actor_role="teacher",
        )

        first = resolve_display_metadata(ctx)
        second = resolve_display_metadata(ctx)
        assert first == second
        assert first is not second
