"""Passkey credential ids: one canonical spelling at the provider boundary (FEAT-IDEN-102/107/108).

Observed on staging against the real passwordless.dev (2026-11-27): ``/signin/verify`` returns
``credentialId`` in standard base64 with padding, which is what is stored, while
``/credentials/list`` (and the only spelling ``/credentials/delete`` matches) is unpadded
base64url. The ids below are those exact pairs.
"""
from __future__ import annotations

import pytest

from app import db
from app.models import CredentialOperation, CredentialOperationStage, PasskeyCredential
from app.services import passkey_service
from app.services.credential_reconciliation import CredentialClass as C, classify_inventory
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.passkey import (  # noqa: F401  (fake_passwordless is a fixture)
    fake_passwordless, give_totp_seed, provider_credential_id, record_passkey, totp_code,
)

PAIRS = [
    ("FFfvlncYlCXf2iZMAlpKsWTAe/0=", "FFfvlncYlCXf2iZMAlpKsWTAe_0"),
    ("r+1uQN7KSsGlfCIH7gt0Hg==", "r-1uQN7KSsGlfCIH7gt0Hg"),
]


def _teacher(client, app, fake, passkeys):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    user_id = classroom.teacher_user.id
    give_totp_seed(user_id)
    for credential in passkeys:
        record_passkey(user_id, credential, fake, name=f"name-{credential}")
    return classroom, user_id


def _bound(user_id):
    db.session.expire_all()
    return sorted(r.credential_id for r in PasskeyCredential.query.filter_by(user_id=user_id).all())


def _row_id(credential_id):
    return PasskeyCredential.query.filter_by(credential_id=credential_id).one().id


def _revoke(client, row_id):
    return client.delete(f"/admin/passkey/{row_id}/delete", json={"totp_code": totp_code()})


def test_the_fake_lists_base64url_and_deletes_only_that_spelling(fake_passwordless):
    for stored, listed in PAIRS:
        fake_passwordless.credentials[stored] = "user_1"
    assert sorted(i.descriptor.id for i in fake_passwordless.get_credentials("user_1")) == sorted(p[1] for p in PAIRS)
    with pytest.raises(Exception):
        fake_passwordless.delete_credential(type("D", (), {"credential_id": PAIRS[0][0]})())


@pytest.mark.parametrize("stored, listed", PAIRS)
def test_the_canonical_form_is_base64url_without_padding_whatever_the_input_spelling(stored, listed):
    assert passkey_service.canonical_credential_id(stored) == listed
    assert passkey_service.canonical_credential_id(listed) == listed
    assert passkey_service.canonical_credential_id(listed + "=" * (-len(listed) % 4)) == listed


@pytest.mark.parametrize("stored, listed", PAIRS)
def test_revoke_retires_the_credential_the_provider_lists_as_base64url(client, app, fake_passwordless, stored, listed):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=(stored, "cred-keep"))

    response = _revoke(client, _row_id(stored))

    assert response.status_code == 200, response.get_json()
    assert [c for c in fake_passwordless.calls if c[0] == "delete_credential"] == [("delete_credential", listed)]
    assert stored not in fake_passwordless.credentials
    assert _bound(user_id) == ["cred-keep"]
    db.session.expire_all()
    (operation,) = CredentialOperation.query.filter_by(user_id=user_id).all()
    assert operation.stage is CredentialOperationStage.COMPLETED


@pytest.mark.parametrize("stored, listed", PAIRS)
def test_the_absence_check_treats_the_base64url_listing_as_the_same_id(
    client, app, fake_passwordless, stored, listed,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=(stored,))
    external = fake_passwordless.credentials[stored]

    assert passkey_service._credential_absent_from_inventory(stored, user_id) is False  # still listed
    fake_passwordless.credentials.pop(stored)
    assert passkey_service._credential_absent_from_inventory(stored, user_id) is True  # gone, whichever spelling
    assert external


@pytest.mark.parametrize("stored, listed", PAIRS)
def test_a_provider_404_with_the_credential_still_listed_is_not_a_confirmed_deletion(
    client, app, fake_passwordless, stored, listed,
):
    _, user_id = _teacher(client, app, fake_passwordless, passkeys=(stored, "cred-keep"))
    fake_passwordless.generic_404_deletes = True

    with pytest.raises(passkey_service.PasskeyServiceUnavailable):
        passkey_service.retire_remote_credential(stored, user_id)


@pytest.mark.parametrize("stored, listed", PAIRS)
def test_reconciliation_never_classifies_an_active_binding_as_provider_only_across_encodings(stored, listed):
    result = classify_inventory(provider_ids=[listed], active_ids=[stored])
    assert result.provider == {listed: C.ACTIVE}
    assert result.provider_only == () and result.unexpectedly_absent == ()

    both = classify_inventory(provider_ids=[p[1] for p in PAIRS], active_ids=[p[0] for p in PAIRS])
    assert both.provider_only == () and both.unexpectedly_absent == ()

    retiring = classify_inventory(provider_ids=[listed], active_ids=[stored], retiring_id=stored)
    assert retiring.provider == {listed: C.RETIRING} and retiring.unexpectedly_absent == ()
    pending = classify_inventory(provider_ids=[listed], active_ids=[], pending_id=stored)
    assert pending.provider == {listed: C.PENDING}


def test_distinct_credentials_stay_distinct():
    a, b = (p[0] for p in PAIRS)
    assert passkey_service.canonical_credential_id(a) != passkey_service.canonical_credential_id(b)
    assert provider_credential_id(a) == PAIRS[0][1]
