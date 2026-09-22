"""A registered passkey must actually survive past the request that saved it.

``passkey_register_finish`` and ``passkey_delete`` called
``admin_identity_service.create_admin_credential`` / ``delete_admin_credential``
directly -- raw Core statements against ``db.session`` -- with no
``@requires_feat_context`` wrapping the route and no explicit
``db.session.commit()``. Nothing in this codebase auto-commits at request
teardown (commits happen only inside a ``FEATContext``'s own transaction),
so the write was staged and then silently discarded when the request's
session tore down. The route still flashed "Passkey registered
successfully!" and returned ``{"success": true}`` -- observed live: the UI
reports success, but Passkey Settings shows "You don't have any passkeys
registered yet," and a subsequent sign-in attempt then correctly (but
confusingly) fails with "Invalid credentials," since no credential ever
really existed.

Fixed by wrapping both routes in ``@requires_feat_context("FEAT-OPS-001")``,
matching the already-correct sibling route ``passkey_auth_finish``, whose
FEATContext owns the transaction and commits on clean exit.
"""
from __future__ import annotations

from tests.helpers.classroom_initializer import initialize_as_teacher


def _register(client, name="Test Passkey"):
    return client.post(
        "/admin/passkey/register/finish",
        json={"token": "opaque-passwordless-dev-token", "authenticatorName": name},
    )


def test_a_registered_passkey_survives_past_the_request_that_saved_it(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    resp = _register(client, "YubiKey 5")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # A FRESH request (its own request-scoped session) must still see it --
    # this is exactly what the live report showed failing.
    listing = client.get("/admin/passkey/list")
    assert listing.status_code == 200
    names = [p["name"] for p in listing.get_json()["passkeys"]]
    assert "YubiKey 5" in names, (
        "the credential vanished across requests -- the write was never committed"
    )

    with app.app_context():
        from app.services.admin_identity_service import admin_has_passkeys
        assert admin_has_passkeys(classroom.teacher_user.id) is True


def test_a_deleted_passkey_stays_deleted_past_the_request(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    _register(client, "Old Phone")

    listing = client.get("/admin/passkey/list").get_json()
    passkey_id = next(p["id"] for p in listing["passkeys"] if p["name"] == "Old Phone")

    delete_resp = client.delete(f"/admin/passkey/{passkey_id}/delete")
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["success"] is True

    # Fresh request again -- the deletion must have actually committed too.
    listing_after = client.get("/admin/passkey/list").get_json()
    assert all(p["id"] != passkey_id for p in listing_after["passkeys"]), (
        "the deleted credential reappeared -- the delete was never committed"
    )
