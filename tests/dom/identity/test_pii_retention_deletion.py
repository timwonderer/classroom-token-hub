"""INV-ARC-018 §VIII — PII must not outlive the identity record that owns it.

`scripts/validate-pii-storage.py` proves PII is stored in a permitted *form*.
It says nothing about *duration*, and a correctly encrypted name that survives
the deletion of its seat is still retained PII. This module is the retention
half of the CI-PII evidence: it exercises each of the four §VIII rules against a
real database.

Every test asserts the PII existed and was populated before the deletion it is
about to perform. A fixture that quietly stopped creating identity profiles
would otherwise turn each of these into a test that deletes nothing and asserts
that nothing is absent.
"""
from __future__ import annotations

from sqlalchemy import text

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, IdentityProfile, Seat, User
from app.services.classroom_setup import delete_seat_with_profile
from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _class_delete_phrase(class_id: str) -> str:
    class_row = db.session.get(ClassEconomy, class_id)
    label = (class_row.display_name or "").strip() or class_row.join_code
    return f"DELETE {label}".upper()


def _assert_pii_is_present(seat: Seat) -> IdentityProfile:
    """Refuse to run a retention assertion against a seat that carries no PII."""
    profile = IdentityProfile.query.filter_by(seat_id=seat.id).one()
    assert profile.first_name, "fixture seat has no display PII to retain or delete"
    assert profile.last_name
    assert seat.claim_first_name_hash, "fixture seat has no claim hashes"
    assert seat.claim_last_name_hash
    return profile


# ---------------------------------------------------------------------------
# §VIII.1 — seat deletion destroys seat PII and its identity profile together.
# ---------------------------------------------------------------------------


def test_seat_deletion_removes_the_identity_profile_in_the_same_transaction(client):
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    seat_id = seat.id
    profile_id = _assert_pii_is_present(seat).id

    with FEATContext("FEAT-IDEN-007", idempotency_key="arc018:seat-delete"):
        delete_seat_with_profile(seat)
        db.session.flush()
        # Before the transaction closes, not merely after it. §VIII.1 requires
        # that no window exists in which the profile outlives its seat.
        assert db.session.get(Seat, seat_id) is None
        assert db.session.get(IdentityProfile, profile_id) is None

    db.session.expire_all()
    assert db.session.get(IdentityProfile, profile_id) is None


def test_seat_deletion_removes_the_claim_verification_hashes(client):
    """The hashes live on `seats`, so their deletion is the row's deletion."""
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    seat_id = seat.id
    _assert_pii_is_present(seat)

    with FEATContext("FEAT-IDEN-007", idempotency_key="arc018:claim-hash-delete"):
        delete_seat_with_profile(seat)
        db.session.flush()

    db.session.expire_all()
    residue = db.session.execute(
        text(
            "SELECT claim_first_name_hash, claim_last_name_hash "
            "FROM seats WHERE id = :seat_id"
        ),
        {"seat_id": seat_id},
    ).fetchall()
    assert residue == []


def test_the_database_cascade_deletes_profile_pii_without_the_orm(client):
    """§VIII.4 is enforced by the schema, not only by the deletion helper.

    `delete_seat_with_profile` removes the profile explicitly. If that were the
    only protection, any other path that deletes a seat would strand its PII.
    This deletes the seat row directly in SQL so the `ON DELETE CASCADE` on
    `identity_profiles.seat_id` is what is under test.
    """
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    seat_id = seat.id
    profile_id = _assert_pii_is_present(seat).id

    db.session.execute(
        text("UPDATE users SET last_active_seat_id = NULL WHERE last_active_seat_id = :seat_id"),
        {"seat_id": seat_id},
    )
    db.session.execute(text("DELETE FROM seats WHERE id = :seat_id"), {"seat_id": seat_id})
    db.session.commit()
    db.session.expire_all()

    surviving = db.session.execute(
        text("SELECT id FROM identity_profiles WHERE id = :profile_id"),
        {"profile_id": profile_id},
    ).fetchall()
    assert surviving == [], "identity_profiles row survived the deletion of its seat"


# ---------------------------------------------------------------------------
# §VIII.2 — user deletion destroys the username hash.
# ---------------------------------------------------------------------------


def test_user_deletion_removes_the_username_hash(client):
    classroom = initialize("chemistry_p1", db)
    student = classroom.students[0]
    user_id = student.user_id

    stored_hash = db.session.get(User, user_id).username_hash
    assert stored_hash, "fixture user has no username hash to retain or delete"

    with FEATContext("FEAT-IDEN-007", idempotency_key="arc018:user-delete"):
        db.session.delete(db.session.get(User, user_id))
        db.session.flush()

    db.session.expire_all()
    residue = db.session.execute(
        text("SELECT id FROM users WHERE username_hash = :h"), {"h": stored_hash}
    ).fetchall()
    assert residue == []


# ---------------------------------------------------------------------------
# §VIII.3 and §VIII.4 — class deletion cascades, and leaves nothing orphaned.
# ---------------------------------------------------------------------------


def test_class_deletion_leaves_no_identity_profile_behind(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id

    profile_ids = [_assert_pii_is_present(s.seat).id for s in classroom.students]
    assert profile_ids, "fixture class has no students, so it retains no PII"

    resp = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(class_id))
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(ClassEconomy, class_id) is None
    for profile_id in profile_ids:
        assert db.session.get(IdentityProfile, profile_id) is None


def test_class_deletion_leaves_no_profile_referencing_a_deleted_seat(client, app):
    """§VIII.4 stated globally: no surviving profile may point at a dead seat."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id
    assert [_assert_pii_is_present(s.seat).id for s in classroom.students]

    resp = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(class_id))
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    db.session.expire_all()

    orphans = db.session.execute(
        text(
            "SELECT p.id FROM identity_profiles p "
            "LEFT JOIN seats s ON s.id = p.seat_id "
            "WHERE p.seat_id IS NOT NULL AND s.id IS NULL"
        )
    ).fetchall()
    assert orphans == []

    stranded = db.session.execute(
        text("SELECT id FROM identity_profiles WHERE class_id = :class_id"),
        {"class_id": class_id},
    ).fetchall()
    assert stranded == []
