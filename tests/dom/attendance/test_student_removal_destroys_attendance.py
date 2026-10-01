"""Removing a student seat destroys that seat's attendance with it.

Live defect, release 314158d53: the ``attendance_sessions_no_delete`` trigger
(migration e7a4c2d9f013) refused every DELETE unless the transaction declared
class or account teardown. Student removal — ``POST /admin/students/bulk-delete``
for part of a roster, FEAT-IDEN-006 — declares neither, so removing any student
who had ever clocked in failed with "Could not delete the selected students.
Nothing was deleted." No test removed a student who had history.

The law is INV-CORE-000 §III.6: removing a seat erases it from the class "as if
they never existed in that class". DOM-PROD-001 §VII.1.a (v1.4) states the
boundary the trigger now enforces: attendance is immutable while its seat
exists, and is destroyed with the seat. Deleting the rows of a seat that still
exists remains refused.

The history seeded here deliberately includes a ``mechanism='self'`` row. Its
``actor_seat_id`` is the removed seat itself, so the actor foreign key fires on
the same seat deletion as the target foreign key. Under the former
``ON DELETE SET NULL`` that action tried to rewrite a NOT NULL column on an
append-only row, and whether it ran before or after the target cascade depended
on internal trigger names. Every real student clock-in writes such a row.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, Seat
from app.services.context_resolver import CanonicalContext
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.class_domain import enable_class_feature
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


def _seed_attendance_history(classroom, student, tag):
    """A closed attendance session: teacher taps the student in, student taps out.

    The tap-out is a ``self`` row whose actor is the student's own seat — the
    shape every real student clock action produces.
    """
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    record_attendance_session(
        ctx=_teacher_ctx(classroom),
        target_seat_id=student.seat.id,
        actor_seat_id=classroom.teacher_seat.id,
        mechanism="teacher",
        status="active",
        reason="start_work",
        idempotency_key=f"removal-att-in:{tag}",
    )
    record_attendance_session(
        ctx=_student_ctx(classroom, student),
        status="inactive",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,
        idempotency_key=f"removal-att-out:{tag}",
    )
    db.session.commit()

    rows = AttendanceSession.query.filter_by(
        class_id=classroom.class_id, target_seat_id=student.seat.id
    ).all()
    assert {row.mechanism for row in rows} == {"teacher", "self"}
    self_row = next(row for row in rows if row.mechanism == "self")
    assert self_row.actor_seat_id == student.seat.id
    return [row.id for row in rows]


def _seed_hall_pass(classroom, student, tag):
    from app.feats.base import FEATContext
    from app.feats.prod import record_hall_pass_log
    from app.services.entitlement_service import grant_hall_passes

    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"bypass:removal-hp:{tag}"):
        grant_hall_passes(student.seat, 1, correlation_id=f"removal-hp:{tag}")
    log = record_hall_pass_log(
        ctx=_teacher_ctx(classroom),
        requested_by_seat_id=student.seat.id,
        approved_by_seat_id=classroom.teacher_seat.id,
        destination="Bathroom",
        reason="teacher_approved",
        idempotency_key=f"removal-hp-log:{tag}",
    ).hall_pass_log
    db.session.commit()
    return log.id


def _count(sql, **params):
    return db.session.execute(sa.text(sql), params).scalar()


def _bulk_delete(client, seat_ids, phrase):
    return client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": list(seat_ids), **valid_destruction_gate(phrase)},
    )


def test_INV_CORE_000_III_6__removing_a_student_with_attendance_destroys_it_with_the_seat(client, app):
    """The live defect: removal of a student who has clocked in must succeed."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    removed = classroom.students[0]
    removed_seat_id = removed.seat.id
    attendance_ids = _seed_attendance_history(classroom, removed, "e2e")
    hall_pass_id = _seed_hall_pass(classroom, removed, "e2e")

    response = _bulk_delete(client, [removed_seat_id], "DELETE STUDENTS")

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["class_deleted"] is False and body["account_deleted"] is False

    db.session.expire_all()
    assert db.session.get(Seat, removed_seat_id) is None
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE id = ANY(:ids)", ids=attendance_ids
    ) == 0
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE target_seat_id = :s OR actor_seat_id = :s",
        s=removed_seat_id,
    ) == 0
    assert _count("SELECT count(*) FROM hall_pass_logs WHERE id = :id", id=hall_pass_id) == 0
    assert db.session.get(ClassEconomy, classroom.class_id) is not None


def test_DOM_PROD_001_VII_1a__attendance_of_a_seat_that_still_exists_cannot_be_deleted(app):
    """Seat removal is the only path; deleting a live seat's rows stays refused."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        student = classroom.students[0]
        attendance_ids = _seed_attendance_history(classroom, student, "guard")

        with pytest.raises(DBAPIError) as exc:
            db.session.execute(
                sa.text("DELETE FROM attendance_sessions WHERE id = ANY(:ids)"),
                {"ids": attendance_ids},
            )
        assert "append-only" in str(exc.value)
        db.session.rollback()

        assert _count(
            "SELECT count(*) FROM attendance_sessions WHERE id = ANY(:ids)", ids=attendance_ids
        ) == len(attendance_ids)


def test_DOM_PROD_001_VII_1a__an_actor_seat_cannot_take_a_surviving_seats_attendance_with_it(app):
    """Deleting the seat that ACTED on a row does not license deleting the row.

    The row belongs to its target seat. A teacher seat deleted while the student
    it recorded survives (not a valid runtime state outside teardown — DOM-LED-001
    §VII.2) must be refused rather than strip the student's history.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        student = classroom.students[0]
        attendance_ids = _seed_attendance_history(classroom, student, "actor")

        # Delete the teacher seat itself, so the refusal comes from the actor
        # foreign key's cascade reaching the guard — not from a hand-written
        # DELETE on attendance_sessions.
        with pytest.raises(DBAPIError) as exc:
            db.session.execute(
                sa.text("DELETE FROM seats WHERE id = :actor"),
                {"actor": classroom.teacher_seat.id},
            )
        assert "attendance_sessions is append-only" in str(exc.value)
        db.session.rollback()

        assert _count(
            "SELECT count(*) FROM attendance_sessions WHERE id = ANY(:ids)", ids=attendance_ids
        ) == len(attendance_ids)


def test_DOM_PROD_001_VII_1a__class_teardown_still_destroys_attendance(client, app):
    """Emptying the roster destroys the class universe, history and all."""
    surviving = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    assert surviving.teacher_user.id == classroom.teacher_user.id
    for index, student in enumerate(classroom.students):
        _seed_attendance_history(classroom, student, f"teardown-{index}")

    seat_ids = [s.id for s in Seat.query.filter_by(class_id=classroom.class_id, role="student")]
    response = _bulk_delete(client, seat_ids, "DELETE CLASS")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["class_deleted"] is True
    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE class_id = :c", c=classroom.class_id
    ) == 0


def test_INV_PROD_001__removing_a_student_leaves_another_classs_attendance_untouched(client, app):
    """Same teacher, two periods: removal in one never reaches the other."""
    other = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    assert other.teacher_user.id == classroom.teacher_user.id

    other_ids = _seed_attendance_history(other, other.students[0], "other-class")
    classmate_ids = _seed_attendance_history(classroom, classroom.students[1], "classmate")
    removed = classroom.students[0]
    _seed_attendance_history(classroom, removed, "removed")

    response = _bulk_delete(client, [removed.seat.id], "DELETE STUDENTS")
    assert response.status_code == 200, response.get_data(as_text=True)

    db.session.expire_all()
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE id = ANY(:ids)", ids=other_ids
    ) == len(other_ids)
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE id = ANY(:ids)", ids=classmate_ids
    ) == len(classmate_ids)
    assert _count(
        "SELECT count(*) FROM attendance_sessions WHERE target_seat_id = :s", s=removed.seat.id
    ) == 0
