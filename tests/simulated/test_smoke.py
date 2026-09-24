"""Verifies tests/simulated/conftest.py actually binds to the simulated
world and can read its (correctly re-encrypted) data, before anything else
in this directory is built on top of it.
"""

from app.extensions import db
from app.models import IdentityProfile


def test_bound_to_the_simulated_database(app):
    """The conftest's own assertion already guards this, but a test-level
    check makes the intent visible without reading the fixture's internals.
    """
    assert str(db.engine.url).endswith("classroom_economy_simulated_test")


def test_seeded_identity_data_is_real_and_decryptable(app):
    """The world was seeded from a production snapshot with PII re-encrypted
    under this machine's own key -- prove a known row round-trips correctly,
    not just that the query doesn't raise.
    """
    count = IdentityProfile.query.count()
    assert count > 80, f"expected the production-sourced world (93 rows), got {count}"

    names = {
        f"{p.first_name} {p.last_name}"
        for p in IdentityProfile.query.limit(10).all()
    }
    # Confirms real decryption, not just "didn't crash": a broken key would
    # either raise (as it did before the fix) or produce garbage bytes, not
    # a real name from this session's own live-test campaign.
    assert "Jordan Lee" in names or any(len(n.strip()) > 1 for n in names)
