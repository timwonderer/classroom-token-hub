"""Same-teacher/two-class isolation for deleting unclaimed (pending) seats.

Guards the P0 class-isolation invariant on the live roster deletion route,
``/admin/students/bulk-delete``: a deletion acts on exactly the single active
canonical class (``g.canonical_context.class_id``) and never reaches a sibling
class owned by the same teacher. These cases use *unclaimed* seats; the
claimed-seat case is ``test_teacher_lifecycle::test_student_delete_rejects_sibling_class_ids``.

The retired ``/admin/pending-students/bulk-delete`` route these tests first
guarded, and its ``all_pending`` mode, were removed 2026-09-27 (REF-API-001 §VII-D).

``chemistry_p1`` and ``ap_csp_p3`` are both owned by ``teacher_alice`` in the
canonical fixtures, so provisioning both yields one teacher owning two classes —
the precise scenario a class-isolation violation would leak across.
"""

from app.extensions import db
from app.feats.base import FEATContext
from app.hash_utils import hash_claim_name, hash_roster_fingerprint
from app.models import IdentityProfile, Seat
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _add_pending_seat(class_id: str, first_name: str, last_name: str) -> int:
    """Create one unclaimed (pending) roster seat in ``class_id`` via the setup FEAT boundary."""
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"pending-seat:{class_id}:{first_name}:{last_name}",
    ):
        seat = Seat(
            class_id=class_id,
            role="student",
            claimed_at=None,
            user_id=None,
            claim_first_name_hash=hash_claim_name(first_name.lower(), class_id=class_id, field="first"),
            claim_last_name_hash=hash_claim_name(last_name.lower(), class_id=class_id, field="last"),
            roster_fingerprint=hash_roster_fingerprint(class_id=class_id, first_name=first_name, last_name=last_name),
        )
        db.session.add(seat)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=seat.id,
                class_id=class_id,
                profile_type="student",
                first_name=first_name,
                last_name=last_name,
            )
        )
        db.session.flush()
        seat_id = seat.id
    return seat_id


def _gate():
    return {"gate_phrase": "DELETE STUDENTS", "gate_countdown_seconds": 30, "gate_hold_seconds": 10}


def test_DOM_CLASS_001__bulk_delete_rejects_foreign_unclaimed_seat_id(client):
    """An unclaimed seat from a sibling class is refused, not deleted."""
    other = initialize("ap_csp_p3", client.application)
    initialize_as_teacher("chemistry_p1", client, client.application)

    other_pending = _add_pending_seat(other.class_id, "Otto", "Outsider")

    response = client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": [other_pending], **_gate()},
    )
    assert response.status_code == 404

    db.session.expire_all()
    assert db.session.get(Seat, other_pending) is not None


def test_DOM_CLASS_001__mixed_selection_with_a_foreign_seat_changes_nothing(client):
    """One foreign id fails the whole request closed: the active class's own
    selected seat survives too, so a refusal never becomes a partial delete."""
    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    assert active.teacher_user.id == other.teacher_user.id

    active_pending = _add_pending_seat(active.class_id, "Penny", "Active")
    other_pending = _add_pending_seat(other.class_id, "Otto", "Outsider")

    response = client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": [active_pending, other_pending], **_gate()},
    )
    assert response.status_code == 404

    db.session.expire_all()
    assert db.session.get(Seat, active_pending) is not None
    assert db.session.get(Seat, other_pending) is not None
