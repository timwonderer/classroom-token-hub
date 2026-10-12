"""Audit O4: one status read must not scan the seat's attendance history
three or four times over.

``get_class_attendance_status`` -- what both ``/api/student-status`` (polled
roughly every 10 seconds per open tab) and the dashboard render call -- used
to run the identical unbounded query (every row for one seat, ordered by
time) independently in up to four places: once for its own "is this seat
active" check, and again inside ``is_done_for_day``,
``calculate_unpaid_attendance_seconds`` and
``calculate_worked_attendance_seconds_today``.

``_canonical_seat_rows`` now runs that query once per request and memoizes
it; ``record_attendance_session_command`` -- the sole writer of this table
-- drops the memoized entry immediately after it writes, so a write and a
read inside the same request (exactly what ``/api/tap`` does: write, then
compute the response from fresh state) can never observe stale data.
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession
from app.services.attendance_service import (
    _canonical_seat_rows,
    get_class_attendance_status,
    invalidate_canonical_seat_rows_cache,
)
from app.services.context_resolver import CanonicalContext
from tests.helpers.canonical_classroom import login_student
from tests.helpers.classroom_initializer import initialize


def _ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _count_attendance_queries(app, fn):
    """Run ``fn`` and return how many SELECTs hit attendance_sessions."""
    counter = {"n": 0}

    def _before_execute(conn, clauseelement, multiparams, params, execution_options=None, **kw):
        sql = str(clauseelement)
        if "attendance_sessions" in sql and sql.strip().upper().startswith("SELECT"):
            counter["n"] += 1

    event_key = (db.engine, "before_execute")
    sa.event.listen(*event_key, _before_execute)
    try:
        fn()
    finally:
        sa.event.remove(*event_key, _before_execute)
    return counter["n"]


def test_one_status_read_queries_attendance_history_once_not_four_times(client, app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    login_student(client, student)
    ctx = _ctx(classroom, student)

    with app.test_request_context("/api/student-status"):
        from flask import g
        g.canonical_context = ctx
        query_count = _count_attendance_queries(
            app,
            lambda: get_class_attendance_status(student.seat, class_id=classroom.class_id, ctx=ctx),
        )

    # One shared unbounded history query (the fix) plus is_done_for_day's own
    # narrow, already-bounded query (status + reason_code + today's range) --
    # down from four separate unbounded scans before this change.
    assert query_count == 2, (
        f"expected the shared unbounded query plus is_done_for_day's bounded "
        f"query only, got {query_count}"
    )


def test_cache_memoizes_repeat_reads_within_one_request(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]

    with app.test_request_context("/"):
        first = _canonical_seat_rows(student.seat.id, classroom.class_id)
        again = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert first is again  # memoized within this request


def test_tap_then_poll_reflects_the_just_written_session_not_a_stale_cache(client, app):
    """End-to-end proof across the real routes, covering all three
    properties together: the write inside ``/api/tap`` invalidates whatever
    this request already cached, and the next request's poll starts from
    nothing cached at all -- no stale state crosses either boundary.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    login_student(client, student)

    tap_in = client.post("/api/tap", json={"action": "start_work", "pin": student.pin})
    assert tap_in.status_code == 200, tap_in.get_json()
    assert tap_in.get_json()["active"] is True

    status = client.get("/api/student-status")
    assert status.status_code == 200
    assert status.get_json()["attendance_state"]["active"] is True

    tap_out = client.post(
        "/api/tap",
        json={"action": "stop_work", "pin": student.pin, "reason": "done"},
    )
    assert tap_out.status_code == 200, tap_out.get_json()
    assert tap_out.get_json()["active"] is False

    status_after = client.get("/api/student-status")
    assert status_after.get_json()["attendance_state"]["active"] is False


def test_a_write_mid_request_invalidates_the_cache_for_that_seat(app):
    """Mutation proof: without the writer's invalidation call, this returns
    the pre-write snapshot and a tap-triggered read would see stale state.
    """
    from app.feats.prod import record_attendance_session

    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _ctx(classroom, student)

    with app.test_request_context("/"):
        before = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert before == []

        # record_attendance_session is itself the FEAT-PROD-001 boundary; it
        # must not be wrapped in another FEATContext (one FEAT per request).
        record_attendance_session(
            ctx=ctx,
            target_seat_id=student.seat.id,
            actor_seat_id=student.seat.id,
            mechanism="self",
            status="active",
            idempotency_key="o4-cache-mid-request:tap-in",
        )
        db.session.commit()

        after = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert len(after) == 1
        assert after[0].status == "active"


def test_invalidate_is_a_noop_outside_a_request(app):
    """No cache exists outside a request context, so this must not raise."""
    with app.app_context():
        invalidate_canonical_seat_rows_cache(1, "some-class")


def test_a_direct_write_outside_the_writer_still_invalidates_the_cache(app):
    """Mutation proof for the ``after_flush`` backstop listener specifically.

    ``test_a_write_mid_request_invalidates_the_cache_for_that_seat`` goes
    through ``record_attendance_session``, which invalidates its own scope
    directly -- so that test alone would still pass if the generic
    ``after_flush`` listener in attendance_service.py stopped working. This
    one writes the row the way several test fixtures across the suite do
    (direct ``db.session.add`` inside a bare ``FEATContext``, bypassing the
    writer entirely) so only the listener can be responsible for the cache
    reflecting it.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]

    with app.test_request_context("/"):
        before = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert before == []

        with FEATContext(
            "FEAT-PROD-001", correlation_id=f"direct:{uuid4()}", idempotency_key=f"direct:{uuid4()}"
        ):
            db.session.add(AttendanceSession(
                target_seat_id=student.seat.id, class_id=classroom.class_id,
                actor_seat_id=student.seat.id, status="active",
                reason_code="start_work",
            ))
            db.session.flush()

        after = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert len(after) == 1
        assert after[0].status == "active"


def test_a_rollback_after_a_cached_flush_clears_the_cache(app):
    """Mutation proof for the ``after_rollback`` listener.

    A flush is visible to a query in the same transaction, so a read between
    a flush and a rollback can populate the cache with a row the rollback
    then discards. Without a rollback listener, a later read in the same
    request would keep serving that now-nonexistent row.
    """
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]

    with app.test_request_context("/"):
        assert _canonical_seat_rows(student.seat.id, classroom.class_id) == []

        try:
            with FEATContext(
                "FEAT-PROD-001", correlation_id=f"rb:{uuid4()}", idempotency_key=f"rb:{uuid4()}"
            ):
                db.session.add(AttendanceSession(
                    target_seat_id=student.seat.id, class_id=classroom.class_id,
                    actor_seat_id=student.seat.id, status="active",
                    reason_code="start_work",
                ))
                db.session.flush()
                # Cache now holds the flushed-but-uncommitted row.
                mid_txn = _canonical_seat_rows(student.seat.id, classroom.class_id)
                assert len(mid_txn) == 1
                raise ValueError("force a rollback of this FEAT")
        except ValueError:
            pass  # FEATContext.__exit__ already rolled back; this is expected.

        after_rollback = _canonical_seat_rows(student.seat.id, classroom.class_id)
        assert after_rollback == [], (
            "the rolled-back row must not remain visible via a stale cache entry"
        )
