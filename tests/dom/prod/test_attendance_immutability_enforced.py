"""Attendance rows cannot be edited, and can only be deleted by teardown.

DOM-PROD-001 says this four times (§108, §176-177, §184, §185) and, until this
migration, the database enforced none of it. `attendance_sessions` carried no
triggers and no chain columns; a direct UPDATE succeeded silently.

The asymmetry is what made it worth closing: `ledger_transaction` — the output —
could not be rewritten, while `attendance_sessions` — the input that justifies
every dollar in that output — could. Payroll reads attendance and nothing else
determines what a student is paid.

These tests drive raw SQL deliberately. The application layer never updates an
attendance row, so an ORM-level test would pass against an unprotected table and
prove only that no code does the thing no code does. The claim under test is
that the DATABASE refuses.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import InternalError, ProgrammingError

from app.extensions import db
from app.feats.prod import record_attendance_session
from app.models import AttendanceSession
from app.services.context_resolver import CanonicalContext
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize

TRIGGER_ERRORS = (InternalError, ProgrammingError, sa.exc.DBAPIError)


def _seed_attendance(classroom):
    student = classroom.students[0]
    ctx = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    # No FEATContext here: record_attendance_session carries its own
    # @requires_feat_context, which OPENS a context rather than asserting one.
    # Wrapping it nests and raises — which is precisely finding 29, committed
    # here by accident while writing the test for finding 27.
    record_attendance_session(
        ctx=ctx,
        target_seat_id=student.seat.id,
        actor_seat_id=classroom.teacher_seat.id,
        mechanism="teacher",
        status="active",
        reason="start_work",
        idempotency_key=f"seed-att:{student.seat.id}",
    )
    db.session.flush()
    row = AttendanceSession.query.filter_by(class_id=classroom.class_id).first()
    assert row is not None
    return row


def test_attendance_row_cannot_be_updated(app):
    """A direct UPDATE must be refused by the database."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _seed_attendance(classroom)
        row_id = row.id

        with pytest.raises(TRIGGER_ERRORS) as exc:
            db.session.execute(
                sa.text("UPDATE attendance_sessions SET status = 'inactive' WHERE id = :id"),
                {"id": row_id},
            )
        assert "append-only" in str(exc.value)
        db.session.rollback()


def test_attendance_row_cannot_be_deleted_without_declaring_teardown(app):
    """Correction by deletion is refused; §184 forbids delete behaviour."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _seed_attendance(classroom)
        row_id = row.id

        with pytest.raises(TRIGGER_ERRORS) as exc:
            db.session.execute(
                sa.text("DELETE FROM attendance_sessions WHERE id = :id"), {"id": row_id}
            )
        assert "append-only" in str(exc.value)
        db.session.rollback()


def test_teardown_may_delete_attendance(app):
    """Destroying a class removes its evidence; that path declares itself.

    Without this the guard would break account destruction, which is why DELETE
    is gated rather than forbidden outright as it is on audit_events.

    The declaration lives in ``teacher_destruction``, which routes actually call.
    ``app/utils/deletion.py`` also deletes attendance rows and was recorded as a
    teardown path, but it imports four models that no longer exist and therefore
    cannot be imported at all — nothing in ``app/`` references it (finding 37).
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _seed_attendance(classroom)
        row_id = row.id

        from app.services.teacher_destruction import declare_attendance_teardown
        declare_attendance_teardown()
        db.session.execute(
            sa.text("DELETE FROM attendance_sessions WHERE id = :id"), {"id": row_id}
        )

        # Asserted against the database, not db.session.get: the ORM identity map
        # still holds the object after a raw DELETE and would report it present.
        remaining = db.session.execute(
            sa.text("SELECT count(*) FROM attendance_sessions WHERE id = :id"),
            {"id": row_id},
        ).scalar()
        assert remaining == 0
        db.session.rollback()


def test_the_teardown_flag_does_not_outlive_its_transaction(app):
    """SET LOCAL expires on rollback, so the guard cannot be left disarmed.

    A session-level SET would persist on a pooled connection and silently
    disable the guard for a later, unrelated request — which would be worse than
    having no guard, because the protection would appear to be present.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        row = _seed_attendance(classroom)
        row_id = row.id

        from app.services.teacher_destruction import declare_attendance_teardown
        declare_attendance_teardown()
        db.session.rollback()

        with pytest.raises(TRIGGER_ERRORS):
            db.session.execute(
                sa.text("DELETE FROM attendance_sessions WHERE id = :id"), {"id": row_id}
            )
        db.session.rollback()
