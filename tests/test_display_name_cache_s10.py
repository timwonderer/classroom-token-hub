"""Teacher display-name resolution outside class context (audit S10).

Before this change: ``set_admin_display_name_cache`` wrote the teacher's
decrypted name into the Flask session, and ``get_admin_display_name_cache``
read it back from there. The session is a signed-but-unencrypted cookie, so
that name sat in plaintext at rest on the user's own browser -- in conflict
with INV-CORE-000 section 2 and INV-ARC-018 section VII.1. Tim's ruling
(2026-10-12): resolve it fresh from the database on every call instead.
"""

from __future__ import annotations

from flask import session

from app.extensions import db
from app.feats.base import FEATContext
from app.models import IdentityProfile
from app.utils.display_name_session import (
    ADMIN_DISPLAY_NAME_ID_KEY,
    ADMIN_DISPLAY_NAME_KEY,
    clear_admin_display_name_cache,
    get_admin_display_name_cache,
    set_admin_display_name_cache,
)
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_admin_display_name_resolves_from_the_database_without_priming(app, client):
    """No prior ``set_admin_display_name_cache`` call is needed: the name
    comes straight from the teacher's last active seat/profile, falling back
    to the username placeholder when the fixture gives the teacher no
    ``IdentityProfile`` (``create_class`` does not require one up front).
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    with app.test_request_context():
        name = get_admin_display_name_cache(user_id=classroom.teacher_user.id)

    assert name == f"user_{classroom.teacher_user.id}"


def test_admin_display_name_resolves_the_teachers_profile_when_one_exists(app, client):
    """When the teacher does have an ``IdentityProfile`` on their active
    seat, that real name is what gets resolved -- still straight from the
    database, never from a session write.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    with app.app_context():
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"test-s10:{classroom.teacher_seat_id}"):
            profile = IdentityProfile(
                seat_id=classroom.teacher_seat_id,
                class_id=classroom.class_id,
                profile_type="teacher",
                first_name="Ms.",
                last_name="Rivera",
            )
            db.session.add(profile)
            db.session.flush()

        with app.test_request_context():
            name = get_admin_display_name_cache(user_id=classroom.teacher_user.id)

        assert name == "Ms. Rivera"


def test_set_admin_display_name_cache_does_not_touch_the_session(app, client):
    with app.test_request_context():
        assert ADMIN_DISPLAY_NAME_KEY not in session
        set_admin_display_name_cache(user_id=1, display_name="Someone Decrypted")
        assert ADMIN_DISPLAY_NAME_KEY not in session
        assert ADMIN_DISPLAY_NAME_ID_KEY not in session


def test_get_admin_display_name_cache_purges_a_legacy_session_cookie(app, client):
    """A browser that still carries a pre-fix cookie gets it scrubbed on the
    very next read, rather than it sitting there indefinitely.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    with app.test_request_context():
        session[ADMIN_DISPLAY_NAME_ID_KEY] = classroom.teacher_user.id
        session[ADMIN_DISPLAY_NAME_KEY] = "Stale Plaintext Name"

        name = get_admin_display_name_cache(user_id=classroom.teacher_user.id)

        assert name == f"user_{classroom.teacher_user.id}"
        assert ADMIN_DISPLAY_NAME_KEY not in session
        assert ADMIN_DISPLAY_NAME_ID_KEY not in session


def test_clear_admin_display_name_cache_purges_a_legacy_session_cookie(app, client):
    with app.test_request_context():
        session[ADMIN_DISPLAY_NAME_ID_KEY] = 1
        session[ADMIN_DISPLAY_NAME_KEY] = "Stale Plaintext Name"

        clear_admin_display_name_cache()

        assert ADMIN_DISPLAY_NAME_KEY not in session
        assert ADMIN_DISPLAY_NAME_ID_KEY not in session


def test_admin_dashboard_never_carries_the_teacher_name_in_the_cookie(app, client):
    """End-to-end: after a real teacher session is established, the signed
    session cookie itself never holds the decrypted name.
    """
    initialize_as_teacher("chemistry_p1", client, app)

    response = client.get("/admin/")
    assert response.status_code == 200

    with client.session_transaction() as sess:
        assert ADMIN_DISPLAY_NAME_KEY not in sess
        assert ADMIN_DISPLAY_NAME_ID_KEY not in sess
