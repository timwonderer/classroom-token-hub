"""A hall pass with a request waiting is reserved for that request.

Owner rulings 2026-10-09: a hall-pass request names one particular pass, and its
availability is decided when it is submitted (DOM-STORE-001 §IX: submitted_at is
authoritative). While the request waits, nothing can remove that pass: not a
reversal, not teacher removal, not rent-perk expiry. Approval uses exactly that
pass; rejection returns it unused.
"""

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, Seat
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import (
    expire_rent_perks,
    grant_hall_passes,
    remove_hall_passes,
    revoke_entitlement,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def seat(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        student = classroom.students[0]
        teacher = db.session.get(Seat, classroom.teacher_seat_id)
        yield {
            "class_id": classroom.class_id,
            "seat_id": student.seat_id,
            "student": CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                        seat_id=student.seat_id, actor_role="student"),
            "teacher": CanonicalContext(user_id=teacher.user_id, class_id=classroom.class_id,
                                        seat_id=teacher.id, actor_role="teacher"),
        }


def _grant(seat, n, tag, **kwargs):
    with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key=f"reserve:grant:{tag}"):
        grant_hall_passes(db.session.get(Seat, seat["seat_id"]), n, **kwargs)
    db.session.commit()
    return [
        e.entitlement_id
        for e in EntitlementEvent.query.filter_by(
            target_seat_id=seat["seat_id"], event_type="GRANTED", entitlement_type="HALL_PASS",
        ).order_by(EntitlementEvent.timestamp.asc(), EntitlementEvent.event_id.asc())
    ]


def _request(seat, tag):
    from app.feats.hall_pass_request_feat import submit_hall_pass_request
    from app.models import PendingAction

    request = submit_hall_pass_request(
        ctx=seat["student"], destination="Bathroom", requested_at_utc=utc_now(),
        idempotency_key=f"reserve:request:{tag}",
    )
    db.session.commit()
    named = PendingAction.query.filter_by(pending_action_id=request.request_id).one().entitlement_id
    return request, named


def _ended(entitlement_id, event_type):
    return EntitlementEvent.query.filter_by(entitlement_id=entitlement_id, event_type=event_type).count()


def test_a_direct_use_skips_the_reserved_pass_and_approval_uses_exactly_it(app, seat):
    from app.feats.hall_pass_request_feat import approve_hall_pass_request
    from app.feats.prod import record_hall_pass_log

    with app.app_context():
        first, second = _grant(seat, 2, "direct")
        request, named = _request(seat, "direct")
        assert named == first

        direct = record_hall_pass_log(
            ctx=seat["teacher"], requested_by_seat_id=seat["seat_id"],
            approved_by_seat_id=seat["teacher"].seat_id, destination="Bathroom",
            reason="teacher_approved", idempotency_key="reserve:direct-log",
        ).hall_pass_log
        db.session.commit()
        assert direct.hall_pass_id == second, "a direct use must not take the reserved pass"

        approved = approve_hall_pass_request(
            ctx=seat["teacher"], request_id=request.request_id,
            idempotency_key="reserve:approve",
        ).hall_pass_log
        db.session.commit()
        assert approved.hall_pass_id == first, "approval uses exactly the pass the request names"


def test_removal_skips_the_reserved_pass_and_cannot_take_it(app, seat):
    with app.app_context():
        first, second = _grant(seat, 2, "remove")
        _, named = _request(seat, "remove")
        assert named == first

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="reserve:remove-one"):
            remove_hall_passes(db.session.get(Seat, seat["seat_id"]), 1)
        db.session.commit()
        assert _ended(second, "REVOKED") == 1
        assert _ended(first, "REVOKED") == 0

        with pytest.raises(ValueError, match="request waiting"):
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="reserve:remove-reserved"):
                remove_hall_passes(db.session.get(Seat, seat["seat_id"]), 1)
        db.session.rollback()
        assert _ended(first, "REVOKED") == 0


def test_rent_perk_expiry_skips_the_reserved_pass(app, seat):
    with app.app_context():
        first, second = _grant(seat, 2, "expire", acquisition_type="PERK", correlation_id="reserve-rent")
        _, named = _request(seat, "expire")
        assert named == first

        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="reserve:expire"):
            expired = expire_rent_perks(correlation_id="reserve-rent", class_id=seat["class_id"],
                                        actor_seat_id=seat["teacher"].seat_id)
        db.session.commit()

        assert expired == 1
        assert _ended(first, "EXPIRED") == 0
        assert _ended(second, "EXPIRED") == 1


def test_a_reserved_pass_cannot_be_revoked_directly(app, seat):
    with app.app_context():
        (first,) = _grant(seat, 1, "revoke")
        _request(seat, "revoke")
        grant = EntitlementEvent.query.filter_by(entitlement_id=first, event_type="GRANTED").one()

        with pytest.raises(ValueError, match="request waiting"):
            with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="reserve:revoke"):
                revoke_entitlement(
                    entitlement_id=first, class_id=grant.class_id,
                    target_seat_id=grant.target_seat_id, actor_seat_id=seat["teacher"].seat_id,
                    product_id=grant.product_id, entitlement_type="HALL_PASS",
                    acquisition_type=grant.acquisition_type, correlation_id="reserve-revoke",
                )
        db.session.rollback()
        assert _ended(first, "REVOKED") == 0
