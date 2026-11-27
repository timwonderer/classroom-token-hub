"""The pure classification behind principal credential reconciliation (FEAT-IDEN-108 §VI.2).

Exact credential ids only; nothing here reads a database, calls a provider or imports an
inventory entry into local state.
"""
from __future__ import annotations

import pytest

from app.services.credential_reconciliation import CredentialClass as C, classify_inventory


def _classify(provider, active=(), **kwargs):
    return classify_inventory(provider_ids=provider, active_ids=active, **kwargs)


def test_each_class_is_assigned_by_exact_credential_id():
    result = _classify(
        ["a", "b", "new", "stray"], active=["a", "b", "gone"], pending_id="new", retiring_id="b",
    )

    assert result.provider == {
        "a": C.ACTIVE, "b": C.RETIRING, "new": C.PENDING, "stray": C.PROVIDER_ONLY,
    }
    assert result.provider_only == ("stray",)
    assert result.unexpectedly_absent == ("gone",)
    assert result.deferred is False


def test_an_id_that_only_resembles_another_is_provider_only():
    result = _classify(["cred-a2", "CRED-A", "cred-a "], active=["cred-a"])

    assert set(result.provider_only) == {"cred-a2", "CRED-A", "cred-a "}
    assert result.unexpectedly_absent == ("cred-a",)


def test_the_same_id_in_another_base64_spelling_is_the_same_credential():
    """A provider that re-encodes an id must not make an activated binding look provider-only."""
    result = _classify(["ab+/cd=="], active=["ab-_cd"])

    assert result.provider == {"ab+/cd==": C.ACTIVE}
    assert result.provider_only == () and result.unexpectedly_absent == ()


def test_an_unknown_id_pending_registration_protects_every_provider_only_entry():
    result = _classify(["a", "late-1", "late-2"], active=["a"], pending_registration_unknown=True)

    assert result.provider == {"a": C.ACTIVE, "late-1": C.PENDING, "late-2": C.PENDING}
    assert result.provider_only == ()
    assert result.deferred is True


def test_once_the_pending_id_is_known_a_stray_is_classified_anew():
    result = _classify(["a", "new", "late"], active=["a"], pending_id="new")

    assert result.provider_only == ("late",) and result.deferred is False


def test_an_empty_inventory_with_active_bindings_is_absence_never_deletion():
    result = _classify([], active=["a", "b"])

    assert result.provider == {} and result.provider_only == ()
    assert result.unexpectedly_absent == ("a", "b")


def test_the_retiring_credential_is_expected_to_be_absent_remotely():
    result = _classify(["a"], active=["a", "b"], retiring_id="b")

    assert result.unexpectedly_absent == ()


def test_a_pending_candidate_is_never_an_unexpected_absence_and_is_not_active():
    result = _classify(["a"], active=["a"], pending_id="new")

    assert result.unexpectedly_absent == ()
    assert result.provider == {"a": C.ACTIVE}


def test_classification_never_imports_inventory_into_the_active_set():
    active = ["a"]
    _classify(["a", "stray"], active=active)

    assert active == ["a"]


@pytest.mark.parametrize("provider_only_id", ["stray", "another"])
def test_a_credential_listed_but_unknown_to_every_local_set_is_provider_only(provider_only_id):
    assert _classify([provider_only_id], active=["a"], pending_id="p", retiring_id="r").provider_only == (
        provider_only_id,
    )


def test_a_one_shot_iterator_of_active_ids_still_reports_the_absent_ones():
    """The active ids are used twice; consuming an iterator once must not hide an unexpected absence."""
    result = _classify(["a"], active=iter(["a", "gone"]))

    assert result.provider == {"a": C.ACTIVE}
    assert result.unexpectedly_absent == ("gone",)
