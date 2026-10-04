"""Removing a student seat destroys that seat's payroll events with it.

#1450 installs ``payroll_event_no_delete`` (migration a7e3c9d1f5b2). As first
written it refused every DELETE unless the transaction declared class-universe
destruction, so removing part of a roster (``POST /admin/students/bulk-delete``,
FEAT-IDEN-006) failed for any student who had ever been paid, even once by a
manual payment: "Could not delete the selected students. Nothing was deleted."

The law is membership by existence (INV-ARC-013, INV-CORE-000 §III.6): an entry
anchored to ``class_id`` or ``seat_id`` exists only while its anchor exists. A
payroll event belongs to its ``target_seat_id``; it is immutable while that seat
exists and is destroyed with it (DOM-PROD-001 §XI.3, the rule §VII.1.a states
for attendance). The guard admits exactly that: a DELETE whose target seat is
already gone, which only the seat's own FK cascade can produce, or one inside
declared class-universe destruction. Deleting a live seat's events stays refused.

This mirrors #1461 (migration bb5557cb1609) for ``attendance_sessions``.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from tests.helpers.payroll_fixture import record_payroll_source_fixture
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, ClassEconomy, PayrollEvent, Seat
from app.services.context_resolver import CanonicalContext
from app.services.payroll.settings import current_payroll_setting
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.class_domain import enable_class_feature, manual_payroll
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _seed_attendance(classroom, student, tag):
    """A closed session: teacher taps in, the student taps out (a ``self`` row)."""
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    record_attendance_session(
        ctx=_teacher_ctx(classroom), target_seat_id=student.seat.id,
        actor_seat_id=classroom.teacher_seat.id, mechanism="teacher",
        status="active", reason="start_work", idempotency_key=f"pe-removal-in:{tag}",
    )
    record_attendance_session(
        ctx=_student_ctx(classroom, student), status="inactive",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY, idempotency_key=f"pe-removal-out:{tag}",
    )
    db.session.commit()


def _seed_payroll_history(client, classroom, student, tag):
    """Attendance, a manual payment through the teacher route, and a ``payroll``
    event priced by the class's setting.

    Returns the ids of the seat's payroll events (a ``payroll`` and a
    ``manual_credit``). ``client`` must be signed in as ``classroom``'s teacher.
    """
    _seed_attendance(classroom, student, tag)
    response = manual_payroll(client, student_ids=[student.seat.public_id],
                              description="Helped clean up", amount="2.00")
    assert response.status_code == 302
    setting = current_payroll_setting(classroom.class_id)
    with FEATContext("FEAT-PROD-003", idempotency_key=f"pe-removal-run:{tag}"):
        record_payroll_source_fixture(
            class_id=classroom.class_id, target_seat_id=student.seat.id,
            actor_seat_id=classroom.teacher_seat.id, correlation_id=f"pe-removal-run:{tag}",
            idempotency_key=f"pe-removal-run:{tag}", payroll_event_type="payroll",
            mechanism="SYSTEM", policy_uuid=setting.policy_uuid, summary_json={},
        )
        db.session.flush()
    db.session.commit()
    db.session.expire_all()
    events = PayrollEvent.query.filter_by(
        class_id=classroom.class_id, target_seat_id=student.seat.id
    ).all()
    assert {event.payroll_event_type for event in events} == {"payroll", "manual_credit"}
    return [event.id for event in events]


def _insert_event(classroom, *, target_seat_id, actor_seat_id, tag):
    """A manual-credit event with chosen seats, for the schema-level cases."""
    with FEATContext("FEAT-PROD-003", idempotency_key=f"pe-removal:{tag}"):
        event = record_payroll_source_fixture(
            class_id=classroom.class_id, target_seat_id=target_seat_id,
            actor_seat_id=actor_seat_id, correlation_id=f"pe-removal:{tag}",
            idempotency_key=f"pe-removal:{tag}", payroll_event_type="manual_credit",
            mechanism="TEACHER", summary_json={},
        )
        db.session.flush()
        event_id = event.id
    db.session.commit()
    return event_id


def _count(sql, **params):
    return db.session.execute(sa.text(sql), params).scalar()


def _bulk_delete(client, seat_ids, phrase):
    return client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": list(seat_ids), **valid_destruction_gate(phrase)},
    )


def live_seat_payroll_delete_is_refused(event_ids) -> bool:
    """Detector: does the database refuse deleting a live seat's payroll events?"""
    db.session.execute(sa.text("SAVEPOINT pe_probe"))
    try:
        db.session.execute(sa.text("DELETE FROM payroll_event WHERE id = ANY(:ids)"), {"ids": event_ids})
    except DBAPIError as exc:
        db.session.execute(sa.text("ROLLBACK TO SAVEPOINT pe_probe"))
        assert "payroll_event is append-only" in str(exc.orig)
        return True
    db.session.execute(sa.text("ROLLBACK TO SAVEPOINT pe_probe"))
    return False


def test_INV_ARC_013__removing_a_paid_student_destroys_their_payroll_events_with_the_seat(client, app):
    """The live defect: removing a student who has been paid must succeed."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    removed = classroom.students[0]
    removed_seat_id = removed.seat.id
    event_ids = _seed_payroll_history(client, classroom, removed, "e2e")

    response = _bulk_delete(client, [removed_seat_id], "DELETE STUDENTS")

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["class_deleted"] is False and body["account_deleted"] is False
    db.session.expire_all()
    assert db.session.get(Seat, removed_seat_id) is None
    assert _count("SELECT count(*) FROM payroll_event WHERE id = ANY(:ids)", ids=event_ids) == 0
    assert _count(
        "SELECT count(*) FROM payroll_event WHERE target_seat_id = :s OR actor_seat_id = :s",
        s=removed_seat_id,
    ) == 0
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE target_seat_id = :s", s=removed_seat_id
    ) == 0
    assert db.session.get(ClassEconomy, classroom.class_id) is not None


def test_DOM_PROD_001_XI_3__payroll_events_of_a_seat_that_still_exists_cannot_be_deleted(client, app):
    """Seat removal is the only path; deleting a live seat's events stays refused."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    event_ids = _seed_payroll_history(client, classroom, classroom.students[0], "guard")

    assert live_seat_payroll_delete_is_refused(event_ids)
    assert _count("SELECT count(*) FROM payroll_event WHERE id = ANY(:ids)", ids=event_ids) == len(event_ids)


def test_DOM_PROD_001_XI_3__mutation_proof_a_loosened_guard_is_detected(client, app):
    """The detector above must report a guard that admits a live seat's DELETE.

    The near miss: the seat-existence test keyed on ``actor_seat_id`` instead of
    ``target_seat_id`` — the actor is the teacher seat, which exists, so the
    mutation must look at the wrong anchor to pass. Installed and rolled back
    inside this test's transaction.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    event_id = _insert_event(classroom, target_seat_id=student.seat.id,
                             actor_seat_id=classroom.teacher_seat.id, tag="mutation")
    assert live_seat_payroll_delete_is_refused([event_id])

    db.session.execute(sa.text("""
        CREATE OR REPLACE FUNCTION prevent_payroll_event_delete() RETURNS TRIGGER AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM seats WHERE id = OLD.target_seat_id)
               OR EXISTS (SELECT 1 FROM seats WHERE id = OLD.actor_seat_id) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'payroll_event is append-only (mutated)';
        END; $$ LANGUAGE plpgsql;
    """))
    try:
        assert live_seat_payroll_delete_is_refused([event_id]) is False
    finally:
        db.session.rollback()
    assert live_seat_payroll_delete_is_refused([event_id])
    db.session.rollback()


def test_DOM_PROD_001_XI_3__an_actor_seat_cannot_take_a_surviving_seats_payroll_events_with_it(app):
    """Deleting the seat that ACTED on an event does not license deleting it.

    The event belongs to its target seat. A teacher seat deleted while the
    student it paid survives (not a valid runtime state outside teardown) is
    refused by the guard rather than stripping the student's history.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    event_id = _insert_event(classroom, target_seat_id=student.seat.id,
                             actor_seat_id=classroom.teacher_seat.id, tag="actor")

    with pytest.raises(DBAPIError) as exc:
        db.session.execute(sa.text("DELETE FROM seats WHERE id = :actor"),
                           {"actor": classroom.teacher_seat.id})
    assert "payroll_event is append-only" in str(exc.value)
    db.session.rollback()
    assert _count("SELECT count(*) FROM payroll_event WHERE id = :i", i=event_id) == 1


def test_DOM_PROD_001_XI_3__a_seat_that_is_its_own_events_actor_is_removable(app):
    """Schema case: an event whose actor IS the removed seat.

    Every runtime writer records ``actor_seat_id = ctx.seat_id`` under a teacher
    context, so a student is never a payroll actor today (asserted below, in
    ``test_..._live_writers_record_the_teacher_seat_as_actor``). The schema
    allows it, though, and under ``ON DELETE SET NULL`` on that NOT NULL,
    update-refusing column the seat's removal would abort. CASCADE lets the
    guard decide on the target seat, as for attendance (#1461).
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    seat_id = student.seat.id
    event_id = _insert_event(classroom, target_seat_id=seat_id, actor_seat_id=seat_id, tag="self")

    db.session.execute(sa.text("DELETE FROM identity_profiles WHERE seat_id = :s"), {"s": seat_id})
    db.session.execute(sa.text("DELETE FROM seats WHERE id = :s"), {"s": seat_id})
    assert _count("SELECT count(*) FROM payroll_event WHERE id = :i", i=event_id) == 0
    db.session.rollback()


def test_DOM_PROD_001_XI_3__live_writers_record_the_teacher_seat_as_actor(client, app):
    """Evidence for the FK decision: the teacher's manual payment records the
    teacher seat as actor. Every writer goes through ``_record_payroll_event_impl``,
    which stamps ``actor_seat_id = ctx.seat_id`` and is reached only under a
    teacher context (manual payment, teacher and scheduled runs, insurance claim
    approval), so removing a student never reaches payroll_event through
    ``actor_seat_id``."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    response = manual_payroll(client, student_ids=[student.seat.public_id],
                              description="Helped clean up", amount="2.00")
    assert response.status_code == 302
    event = PayrollEvent.query.filter_by(class_id=classroom.class_id, target_seat_id=student.seat.id).one()
    assert event.actor_seat_id == classroom.teacher_seat.id


def test_DOM_PROD_001_XI_3__class_teardown_still_destroys_payroll_events_and_settings(client, app):
    """Emptying the roster destroys the class universe, history and all."""
    surviving = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    assert surviving.teacher_user.id == classroom.teacher_user.id
    _seed_payroll_history(client, classroom, classroom.students[0], "teardown")

    seat_ids = [s.id for s in Seat.query.filter_by(class_id=classroom.class_id, role="student")]
    response = _bulk_delete(client, seat_ids, "DELETE CLASS")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["class_deleted"] is True
    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert _count("SELECT count(*) FROM payroll_event WHERE class_id = :c", c=classroom.class_id) == 0
    assert _count("SELECT count(*) FROM payroll_settings WHERE class_id = :c", c=classroom.class_id) == 0


def test_INV_PROD_001__removing_a_student_leaves_another_classs_payroll_events_untouched(client, app):
    """Same teacher, two periods: removal in one never reaches the other."""
    other = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    assert other.teacher_user.id == classroom.teacher_user.id

    other_id = _insert_event(other, target_seat_id=other.students[0].seat.id,
                             actor_seat_id=other.teacher_seat.id, tag="other-class")
    classmate_id = _insert_event(classroom, target_seat_id=classroom.students[1].seat.id,
                                 actor_seat_id=classroom.teacher_seat.id, tag="classmate")
    removed = classroom.students[0]
    removed_ids = _seed_payroll_history(client, classroom, removed, "removed")

    response = _bulk_delete(client, [removed.seat.id], "DELETE STUDENTS")
    assert response.status_code == 200, response.get_data(as_text=True)

    db.session.expire_all()
    assert _count("SELECT count(*) FROM payroll_event WHERE id = :i", i=other_id) == 1
    assert _count("SELECT count(*) FROM payroll_event WHERE id = :i", i=classmate_id) == 1
    assert _count("SELECT count(*) FROM payroll_event WHERE id = ANY(:ids)", ids=removed_ids) == 0
