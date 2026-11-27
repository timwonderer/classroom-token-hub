"""A passkey change must actually survive past the request that made it.

Nothing in this codebase auto-commits at request teardown (commits happen only inside
a ``FEATContext``'s own transaction), so a write staged outside a FEAT is silently
discarded when the request's session tears down. The route still answered success while
Passkey Settings showed no passkey. Enrollment and removal now run under FEAT-IDEN-102
and FEAT-IDEN-107; these tests read back through a fresh session to prove each commit.
"""
from __future__ import annotations

from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.passkey import (  # noqa: F401  (fake_passwordless is a fixture)
    fake_passwordless, finish_registration, give_totp_seed, record_passkey, start_registration, totp_code,
)


def _persisted_passkeys(app, user_id):
    """Read credentials the way a later request would: in a fresh app context
    with a new session, so only committed rows are visible. The JSON listing
    route these tests once read through was removed 2026-09-27 (REF-API-001
    §VII-D); the Settings page renders the same list server-side."""
    from app.extensions import db
    from app.services.admin_identity_service import list_admin_credentials

    with app.app_context():
        db.session.remove()
        return list_admin_credentials(user_id)


def test_a_registered_passkey_survives_past_the_request_that_saved_it(app, client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    give_totp_seed(classroom.teacher_user.id)
    assert start_registration(client).status_code == 200
    resp = finish_registration(
        client, fake_passwordless.complete_registration(classroom.teacher_user.id), name="YubiKey 5",
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # A FRESH session must still see it -- this is exactly what the live
    # report showed failing.
    names = [p.authenticator_name for p in _persisted_passkeys(app, classroom.teacher_user.id)]
    assert "YubiKey 5" in names, (
        "the credential vanished across requests -- the write was never committed"
    )

    with app.app_context():
        from app.services.admin_identity_service import admin_has_passkeys
        assert admin_has_passkeys(classroom.teacher_user.id) is True


def test_a_deleted_passkey_stays_deleted_past_the_request(app, client, fake_passwordless):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    give_totp_seed(classroom.teacher_user.id)
    record_passkey(classroom.teacher_user.id, "cred-old", fake_passwordless, "Old Phone")
    record_passkey(classroom.teacher_user.id, "cred-keep", fake_passwordless, "Keeper")

    passkey_id = next(
        p.id for p in _persisted_passkeys(app, classroom.teacher_user.id)
        if p.authenticator_name == "Old Phone"
    )

    delete_resp = client.delete(f"/admin/passkey/{passkey_id}/delete", json={"totp_code": totp_code()})
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["success"] is True

    # Fresh request again -- the deletion must have actually committed too.
    listing_after = _persisted_passkeys(app, classroom.teacher_user.id)
    assert all(p.id != passkey_id for p in listing_after), (
        "the deleted credential reappeared -- the delete was never committed"
    )


def test_registered_and_last_used_times_show_class_timezone_not_utc(app, client, fake_passwordless):
    """The Passkey Settings page rendered created_at/last_used with a bare
    ``.strftime()`` -- the raw UTC instant, with no conversion and no timezone
    label -- while every other timestamp in the app goes through the
    ``fmt_timestamp`` filter (SPEC-TIME-001) to display in the class's own
    timezone. Test classrooms default to America/Los_Angeles; a September
    date there is Pacific Daylight Time.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    record_passkey(classroom.teacher_user.id, "cred-live", fake_passwordless, "livetest1")

    page = client.get("/admin/passkey/settings").data.decode()

    assert "livetest1" in page
    assert "PDT" in page or "PST" in page, (
        "the passkey settings page is not converting to the class's timezone "
        "(America/Los_Angeles) -- it shows the raw UTC instant instead"
    )
