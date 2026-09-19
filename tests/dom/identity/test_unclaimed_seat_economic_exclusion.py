"""An unclaimed seat keeps its rows but joins no economic activity or display.

A seat with ``claimed_at IS NULL`` still exists and keeps every row it has ever
accumulated — unclaiming detaches a principal, it does not punish the student who
will re-claim. What an unclaimed seat must not do is take part in the economy or
appear on a teacher surface other than the Student Management roster.

Regression: the teacher dashboard counted every student seat in the class, so a
class with three claimed students and thirteen unclaimed roster seats reported 16
"Active Students" and an economy value that included a balance stranded on an
unclaimed seat, while Banking and Payroll reported 3 students and $0.00 for the
same class. The class-wide bonus paid unclaimed seats too.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, Transaction
from tests.helpers.canonical_classroom import _provision_roster_seat
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction


STRANDED = Decimal("77.77")


def _unclaimed_seat_holding_money(classroom):
    """A roster seat with no principal, carrying a balance from before it was unclaimed."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"unclaimed:{classroom.class_id}"):
        seat = _provision_roster_seat(
            classroom.class_id,
            {"first_name": "Unclaimed", "last_name": "Namesake"},
        )
        create_ledger_idempotent_transaction(
            idempotency_key=f"stranded:{seat.id}",
            seat_id=seat.id,
            class_id=classroom.class_id,
            amount=STRANDED,
            account_type="checking",
            type="manual_payment",
            description="Manual Credit: before the seat was unclaimed",
        )
    db.session.commit()
    assert seat.claimed_at is None and seat.user_id is None
    return seat


def _claimed_student_count(class_id):
    return Seat.query.filter(
        Seat.class_id == class_id, Seat.role == "student", Seat.claimed_at.isnot(None)
    ).count()


def test_DOM_IDEN_001__dashboard_counts_and_totals_skip_unclaimed_seats(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = _unclaimed_seat_holding_money(classroom)
    claimed = _claimed_student_count(classroom.class_id)

    response = client.get("/admin/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    counted = re.search(
        r"Active Students.*?display-6[^>]*>\s*(\d+)", body, re.DOTALL
    )
    assert counted, "dashboard did not render an Active Students figure"
    assert int(counted.group(1)) == claimed

    # The stranded balance belongs to no participating student, so it is in
    # neither the economy value nor the recent-activity feed.
    assert str(STRANDED) not in body
    assert "before the seat was unclaimed" not in body
    assert f'data-seat-id="{seat.id}"' not in body


def test_DOM_IDEN_001__banking_stats_and_transaction_log_skip_unclaimed_seats(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    _unclaimed_seat_holding_money(classroom)

    response = client.get("/admin/banking")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert str(STRANDED) not in body
    assert "before the seat was unclaimed" not in body


def test_DOM_IDEN_001__class_wide_bonus_pays_only_claimed_seats(client):
    """An unclaimed seat holds no principal, so a bonus must not credit it."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = _unclaimed_seat_holding_money(classroom)

    before = Transaction.query.filter_by(seat_id=seat.id).count()
    response = client.post(
        "/admin/bonuses",
        data={"title": "Field day bonus", "amount": "5.00", "type": "bonus"},
    )
    assert response.status_code in (200, 302)

    assert Transaction.query.filter_by(seat_id=seat.id).count() == before
    assert not Transaction.query.filter(
        Transaction.seat_id == seat.id, Transaction.description.ilike("%Field day bonus%")
    ).first()
    # The claimed roster did receive it, so the bonus itself still works.
    claimed_ids = [
        row.id for row in Seat.query.filter(
            Seat.class_id == classroom.class_id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
        ).all()
    ]
    assert Transaction.query.filter(
        Transaction.seat_id.in_(claimed_ids),
        Transaction.description.ilike("%Field day bonus%"),
    ).count() == len(claimed_ids)


def test_DOM_IDEN_001__unclaiming_preserves_the_seats_rows(client):
    """The rows survive as long as the seat does; only deleting the seat removes them."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = _unclaimed_seat_holding_money(classroom)

    rows = Transaction.query.filter_by(seat_id=seat.id).all()
    assert len(rows) == 1
    assert rows[0].amount == STRANDED
    assert db.session.get(Seat, seat.id) is not None


def _unclaim_in_place(seat):
    """Put a claimed seat into the post-unclaim state, keeping its rows.

    Mirrors what FEAT-IDEN-006 leaves behind (DOM-IDEN-005 §Explicit Unclaim:
    the seat and its economic/productivity facts survive) without re-testing the
    unclaim command itself.
    """
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"unclaim-in-place:{seat.id}"):
        seat.user_id = None
        seat.claimed_at = None
        db.session.flush()
    db.session.commit()


def test_DOM_IDEN_002__payroll_history_hides_events_of_an_unclaimed_seat(client):
    """A payroll event recorded before the unclaim stays on the seat, unlisted."""
    from app.feats.prod import record_payroll_event
    from app.models import PayrollEvent, PolicyVersion

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0].seat
    policy = PolicyVersion.query.filter_by(
        class_id=classroom.class_id, domain="payroll", is_active=True
    ).first()

    record_payroll_event(
        ctx=_teacher_context(classroom),
        target_seat_id=student.id,
        payroll_event_type="manual_credit",
        correlation_id="corr_unclaimed_history",
        idempotency_key=f"manual_credit:{classroom.class_id}:{student.id}:history",
        policy_version_id=policy.id if policy else None,
        mechanism="TEACHER",
        summary_json={"description": "Manual Credit: paid while claimed"},
        amount=Decimal("12.00"),
    )
    db.session.commit()
    assert PayrollEvent.query.filter_by(target_seat_id=student.id).count() == 1

    listed = client.get("/admin/payroll-history")
    assert listed.status_code == 200
    assert "paid while claimed" in listed.get_data(as_text=True)

    _unclaim_in_place(student)

    after = client.get("/admin/payroll-history")
    assert after.status_code == 200
    body = after.get_data(as_text=True)
    assert "paid while claimed" not in body
    assert "Unknown" not in body
    # The event itself is retained, only hidden.
    assert PayrollEvent.query.filter_by(target_seat_id=student.id).count() == 1


def _teacher_context(classroom):
    from app.services.context_resolver import CanonicalContext
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def test_DOM_IDEN_002__attendance_history_api_hides_an_unclaimed_seat(client):
    """Attendance survives unclaim on the seat but leaves the teacher's log."""
    from app.feats.prod import record_attendance_session
    from app.models import AttendanceSession

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0].seat

    record_attendance_session(
        ctx=_teacher_context(classroom),
        target_seat_id=student.id,
        status="active",
        mechanism="teacher",
        correlation_id="corr_unclaimed_attendance",
        idempotency_key=f"attendance:{classroom.class_id}:{student.id}:active",
    )
    db.session.commit()

    before = client.get("/api/attendance/history")
    assert before.status_code == 200
    assert any(row["seat_id"] == student.id for row in before.get_json()["records"])

    _unclaim_in_place(student)

    after = client.get("/api/attendance/history")
    assert after.status_code == 200
    assert not any(row["seat_id"] == student.id for row in after.get_json()["records"])
    assert AttendanceSession.query.filter_by(target_seat_id=student.id).count() == 1


def test_DOM_IDEN_002__an_unclaimed_seat_cannot_be_renamed(client):
    """Renaming an unclaimed seat would desynchronise its claim key.

    An unclaimed seat's stored name is what a student matches against at claim
    (DOM-IDEN-002 §VIII), and display-name edits do not regenerate claim
    artifacts. Editing one would leave the hashes on the old name while the
    roster showed the new one, so the seat could only be claimed under a name
    the teacher can no longer see. The roster renders no edit control for these
    rows; this holds the same rule for a request that arrives without one.
    """
    from app.models import IdentityProfile

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = _unclaimed_seat_holding_money(classroom)
    before = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    original_first, original_hash = before.first_name, seat.claim_first_name_hash

    response = client.post(
        "/admin/student/edit",
        data={"seat_id": seat.id, "first_name": "Renamed", "last_name": "Namesake"},
    )
    assert response.status_code == 404

    db.session.expire_all()
    after = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert after.first_name == original_first
    assert db.session.get(Seat, seat.id).claim_first_name_hash == original_hash


def test_DOM_IDEN_002__a_claimed_seat_can_still_be_renamed(client):
    """The guard is about claim state, not about editing: claimed seats still edit."""
    from app.models import IdentityProfile

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0].seat

    response = client.post(
        "/admin/student/edit",
        data={"seat_id": student.id, "first_name": "Renamed", "last_name": "Student"},
    )
    assert response.status_code in (200, 302)

    db.session.expire_all()
    assert IdentityProfile.query.filter_by(seat_id=student.id).first().first_name == "Renamed"


def _modify_via_feat_class_002(classroom, seat_id, first_name, last_name):
    """Drive the other rename entry point: FEAT-CLASS-002 roster modification.

    `/admin/student/edit` is not the only way a seat gets renamed. FEAT-CLASS-002
    owns `actor_public_id`-based modification of an exported roster
    (FEAT-IDEN-006 §Additive roster import draws the distinction explicitly), and
    it reaches the same profile write through a different door.
    """
    from app.feats.base import generate_correlation_id
    from app.feats.class_configuration.feat_class_002_modify_class_boundary import (
        execute_modify_student,
    )
    from app.services.context_resolver import CanonicalContext

    teacher_seat = Seat.query.filter_by(class_id=classroom.class_id, role="teacher").one()
    return execute_modify_student(
        canonical_context=CanonicalContext(
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            seat_id=teacher_seat.id,
            actor_role="teacher",
        ),
        class_id=classroom.class_id,
        seat_id=seat_id,
        first_name=first_name,
        last_name=last_name,
        correlation_id=generate_correlation_id(),
        idempotency_key=f"class:modify-student:{seat_id}",
    )


def test_DOM_IDEN_002__the_roster_modification_feat_also_refuses_an_unclaimed_seat(client):
    """The same rule, held at the second entry point.

    FEAT-CLASS-002 validated context, ownership, role and non-empty names, but
    never claim state, and then updated the IdentityProfile alone — leaving the
    claim hashes on the old name. Recomputing them instead is not the fix:
    DOM-IDEN-002 §VIII.7 forbids display-name edits from regenerating claim
    artifacts, and DOM-IDEN-005 §Explicit Unclaim puts regeneration at unclaim,
    from freshly entered names.
    """
    from app.models import IdentityProfile

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = _unclaimed_seat_holding_money(classroom)
    before = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    original_first = before.first_name
    original_first_hash = seat.claim_first_name_hash
    original_last_hash = seat.claim_last_name_hash
    original_fingerprint = seat.roster_fingerprint

    result = _modify_via_feat_class_002(classroom, seat.id, "Renamed", "Namesake")

    assert result.success is False
    assert result.error_code == "SEAT_NOT_CLAIMED"

    db.session.expire_all()
    after_seat = db.session.get(Seat, seat.id)
    assert IdentityProfile.query.filter_by(seat_id=seat.id).first().first_name == original_first
    # Neither moved, so the displayed name and the claim key cannot disagree.
    assert after_seat.claim_first_name_hash == original_first_hash
    assert after_seat.claim_last_name_hash == original_last_hash
    assert after_seat.roster_fingerprint == original_fingerprint


def test_DOM_IDEN_002__the_roster_modification_feat_still_renames_a_claimed_seat(client):
    """Scoped to claim state, not to renaming generally."""
    from app.models import IdentityProfile

    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0].seat

    result = _modify_via_feat_class_002(classroom, student.id, "Renamed", "Student")

    assert result.success is True, result.error_message
    db.session.expire_all()
    profile = IdentityProfile.query.filter_by(seat_id=student.id).first()
    assert profile.first_name == "Renamed"
    assert profile.last_name == "Student"


def test_DOM_IDEN_002__renaming_a_claimed_seat_does_not_recreate_claim_artifacts(client):
    """The other half of §VIII.7: cleared artifacts stay cleared.

    Claim material is cleared when the seat is claimed. If a later rename put it
    back, a claimed seat would become claimable again by name.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0].seat

    assert _modify_via_feat_class_002(classroom, student.id, "Renamed", "Student").success is True

    db.session.expire_all()
    after = db.session.get(Seat, student.id)
    assert after.claim_first_name_hash is None
    assert after.claim_last_name_hash is None
    assert after.dedupe_code is None
