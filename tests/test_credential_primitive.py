"""Certification of the canonical password primitive in `app/hash_utils.py`.

SPEC-SEC-001 §V.1 is binding through INV-ARC-019 §VI, which incorporates it as
the code-level contract for the credential material `users` owns. These tests
exist because the specification's requirements are, individually, all things
that hold *silently* when they hold and fail *silently* when they do not:

- A drifted KDF profile mints new hashes under different parameters while every
  existing hash keeps verifying, because the encoded verifier carries its own
  parameters. Nothing in the application observes the change.
- A pepper accidentally reintroduced as a KDF input produces working
  authentication right up until the key is rotated, at which point every
  credential in the system is invalid at once.
- A verification path that raises on a malformed verifier instead of returning
  False discloses, through the difference between a 500 and a normal failure,
  exactly the condition §V.1.6 says must not be disclosed.

None of those are observable from source inspection alone, which §VI of the
specification says is insufficient evidence.
"""

import os

import pytest
from werkzeug.security import generate_password_hash

from app.hash_utils import PASSWORD_KDF, hash_password, verify_password

# The profile as written in SPEC-SEC-001 §V.1.2, duplicated here on purpose.
# Asserting `PASSWORD_KDF == PASSWORD_KDF` would pass under any value; the
# literal is what makes editing the constant a test failure rather than a
# silent reparameterization.
SPEC_PROFILE = "scrypt:32768:8:1"


def test_the_pinned_profile_is_the_one_the_specification_names():
    assert PASSWORD_KDF == SPEC_PROFILE


def test_produced_verifiers_carry_the_pinned_profile():
    """The encoded verifier's own parameters, not the constant, are checked.

    `generate_password_hash` writes the profile it actually used into the
    returned string, so this reads back what was done rather than what was
    requested.
    """
    encoded = hash_password("correct horse battery staple")
    method, salt, digest = encoded.split("$", 2)

    assert method == SPEC_PROFILE
    assert salt, "verifier carries no salt"
    assert digest, "verifier carries no digest"


def test_the_profile_is_passed_explicitly_and_not_inherited_from_werkzeug():
    """Guards the reason the constant exists at all.

    Werkzeug's default currently equals the spec profile, so a `method=`
    argument silently removed from `hash_password` would leave every other test
    in this file passing. This one fails the moment the two disagree, which is
    the only moment the distinction has ever mattered.
    """
    library_default = generate_password_hash("x").split("$", 1)[0]

    if library_default == SPEC_PROFILE:
        pytest.skip(
            "Werkzeug's default still matches SPEC-SEC-001 §V.1.2, so the "
            "explicit pin is not yet distinguishable from inheriting it. "
            "This test becomes load-bearing the moment that changes — which "
            "is precisely the upgrade the pin exists to survive."
        )

    assert hash_password("x").split("$", 1)[0] == SPEC_PROFILE


def test_each_hash_carries_its_own_random_salt():
    """§V.1.2. Identical inputs must not produce identical verifiers."""
    first = hash_password("same-passphrase")
    second = hash_password("same-passphrase")

    assert first != second
    assert first.split("$")[1] != second.split("$")[1]
    assert verify_password("same-passphrase", first)
    assert verify_password("same-passphrase", second)


def test_verification_takes_plaintext_first():
    """The seam deliberately reverses Werkzeug's `(stored_hash, plaintext)`.

    A call site that passes them in library order would be comparing a
    passphrase against a verifier used as a passphrase — which fails closed,
    and so would never be noticed as a bug at that call site. It is pinned
    here so the seam's own order cannot be "corrected" back later.
    """
    encoded = hash_password("s3cret")

    assert verify_password("s3cret", encoded) is True
    assert verify_password(encoded, "s3cret") is False


def test_verification_returns_only_a_boolean():
    """§V.1.5 — callers receive a success result, never algorithm detail."""
    encoded = hash_password("s3cret")

    assert verify_password("s3cret", encoded) is True
    assert verify_password("wrong", encoded) is False


@pytest.mark.parametrize(
    "unusable",
    [
        "",
        "not-a-hash",
        "scrypt:32768:8:1",  # method only, no salt or digest
        "scrypt:32768:8:1$saltbutnodigest",
        "$$",
        "pbkdf2:sha256:600000$abc$" + "0" * 64,  # well-formed, wrong algorithm
    ],
    ids=[
        "empty",
        "garbage",
        "method-only",
        "no-digest",
        "empty-fields",
        "foreign-algorithm",
    ],
)
def test_unusable_verifiers_fail_closed_without_disclosing_why(unusable):
    """§V.1.6. Malformed and unusable verifiers must fail closed.

    Raising here would be a disclosure channel: an exception escaping a login
    handler distinguishes "this account's stored verifier is damaged" from
    "wrong passphrase" by response code alone.
    """
    assert verify_password("anything", unusable) is False


def test_an_empty_passphrase_is_rejected_rather_than_hashed_for_comparison():
    assert verify_password("", hash_password("real")) is False


def test_no_application_secret_is_an_input_to_the_kdf():
    """§V.1.3 and INV-ARC-019 §VI consequence 1.

    Rotating any of these keys must not invalidate a single credential. The
    test mutates all three between hashing and verifying; if any were reaching
    the KDF, verification would fail here — and in production it would fail for
    every user simultaneously, during a routine key rotation.
    """
    secrets_under_test = ("PEPPER_KEY", "SECRET_KEY", "ENCRYPTION_KEY")
    original = {name: os.environ.get(name) for name in secrets_under_test}

    try:
        for name in secrets_under_test:
            os.environ[name] = "value-at-hash-time"
        encoded = hash_password("portable-credential")

        for name in secrets_under_test:
            os.environ[name] = "rotated-to-something-entirely-different"
        assert verify_password("portable-credential", encoded) is True
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_the_verifier_does_not_contain_the_plaintext():
    """§V.1.4 — storage is verifier-only, never recoverable."""
    passphrase = "a-very-distinctive-passphrase"
    encoded = hash_password(passphrase)

    assert passphrase not in encoded
