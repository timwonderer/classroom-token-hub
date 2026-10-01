"""Incident OPS-DB-001 (2026-09-30): the request trace writer must never hang a worker.

Production ran one sync worker. A signed-in student posted the claim form for a
seat in their own class. Setup staging locked the class and seat rows
``FOR UPDATE`` and never ended that transaction. The ``after_request`` TLCP
writer then inserted a trace on a second connection; the trace's ``class_id``
foreign key needs ``FOR KEY SHARE`` on that same class row, so the writer waited
on its own request. Postgres cannot see a wait that crosses two connections of
one process, and the role has no lock timeout, so the worker hung until
gunicorn killed it. Four such requests took the site down for about 8 minutes.

The writer is off under TESTING, so no test ever ran it. These tests turn it on
(``tlcp_trace_enabled``) and run the real routes. A watchdog cancels any backend
still waiting on a lock after a deadline, so a regression fails in seconds
instead of hanging CI.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from datetime import timedelta

import pytest
import sqlalchemy as sa

from app import db
from app.feats.base import FEATContext
from app.models import ActorRequestTrace
from app.services import student_setup
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import login_student
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.request_lock_guard import leaked_row_locks

WAITERS = """
SELECT pid FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid()
  AND wait_event_type = 'Lock'
"""


@pytest.fixture
def side_engine(app):
    """Connections independent of the request's session, like a second worker."""
    engine = sa.create_engine(
        db.engine.url.render_as_string(hide_password=False), poolclass=sa.pool.NullPool
    )
    yield engine
    engine.dispose()


@contextmanager
def lock_watchdog(engine, deadline):
    """Cancel every backend still waiting on a lock after ``deadline`` seconds."""
    report = {"cancelled": []}
    stop = threading.Event()

    def watch():
        if stop.wait(deadline):
            return
        with engine.connect() as conn:
            for (pid,) in conn.execute(sa.text(WAITERS)):
                conn.execute(sa.text("SELECT pg_cancel_backend(:p)"), {"p": pid})
                report["cancelled"].append(pid)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        yield report
    finally:
        report["elapsed"] = time.monotonic() - started
        stop.set()
        thread.join(10)


@contextmanager
def held_lock(engine, sql, params):
    """Another transaction holding a lock for the duration of the block."""
    conn = engine.connect()
    trans = conn.begin()
    try:
        conn.execute(sa.text(sql), params)
        yield
    finally:
        trans.rollback()
        conn.close()


def _traces(seat_public_id):
    db.session.expire_all()
    return ActorRequestTrace.query.filter_by(actor_public_id=seat_public_id).count()


def _unclaim(client, seat):
    response = client.post('/admin/student/unclaim', json=dict(
        seat_id=seat.id, claim_generation=seat.claim_generation,
        first_name='Fresh', last_name='Claim', confirmation='UNCLAIM'))
    assert response.status_code == 200, response.data


def _class_with_unclaimed_seat(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    _unclaim(client, classroom.students[1].seat)
    with client.session_transaction() as sess:
        sess.clear()
    return classroom


def _claim(client, classroom):
    return client.post('/student/claim-account', data=dict(
        join_code=classroom.join_code, first_name='Fresh', last_name='Claim'))


def _row_is_free(engine, sql, params):
    """Whether another transaction could take this row FOR UPDATE right now."""
    with engine.connect() as conn:
        try:
            conn.execute(sa.text(sql + " FOR UPDATE NOWAIT"), params)
            return True
        except sa.exc.OperationalError:
            return False
        finally:
            conn.rollback()


# ------------------------------------------------------------ the incident

def test_OPS_DB_001__signed_in_claim_in_own_class_does_not_wait_on_itself(
        client, app, side_engine, tlcp_trace_enabled):
    """The production shape: signed in to class H, claiming another seat of H.

    The identity-establishment gate (#1457) now refuses this request with 409
    before any staging runs, so it takes no row lock at all. The request must
    still finish promptly with its trace written: the refusal path is not
    allowed to reintroduce the wait.
    """
    classroom = _class_with_unclaimed_seat(client, app)
    signed_in = classroom.students[0]
    login_student(client, signed_in)

    with lock_watchdog(side_engine, deadline=5) as report:
        response = _claim(client, classroom)

    assert report["cancelled"] == [], "the trace writer waited on its own request's lock"
    assert response.status_code == 409
    assert report["elapsed"] < 5
    # Nothing was contended, so the trace was written, not skipped.
    assert _traces(signed_in.seat.public_id) >= 1


# ------------------------------------------------- staging lock scope (fix 1)

def test_OPS_DB_001__claim_staging_releases_class_and_seat_locks_before_responding(
        client, app, side_engine):
    classroom = _class_with_unclaimed_seat(client, app)
    seat = classroom.students[1].seat

    response = _claim(client, classroom)
    assert response.status_code == 302 and '/create-username' in response.location

    assert _row_is_free(side_engine, "SELECT 1 FROM classes WHERE class_id = :c",
                        {"c": classroom.class_id})
    assert _row_is_free(side_engine, "SELECT 1 FROM seats WHERE id = :s", {"s": seat.id})


def test_OPS_DB_001__claim_staging_releases_locks_when_staging_fails(
        client, app, side_engine, monkeypatch):
    classroom = _class_with_unclaimed_seat(client, app)

    def expired(*args, **kwargs):
        raise student_setup.SetupExpired('Setup expired.')

    monkeypatch.setattr(student_setup, 'begin', expired)
    response = _claim(client, classroom)
    assert response.status_code == 302 and '/claim-account' in response.location

    assert _row_is_free(side_engine, "SELECT 1 FROM classes WHERE class_id = :c",
                        {"c": classroom.class_id})


def test_OPS_DB_001__recovery_staging_releases_the_user_lock_before_responding(
        client, app, side_engine):
    classroom = initialize('chemistry_p1', app)
    user = classroom.students[0].user
    user.reset_code = "LOCKFREE"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="ops-db-001:recovery-lock"):
        db.session.flush()

    response = client.post('/recovery/lookup', data={'reset_code': 'LOCKFREE'})
    assert response.status_code == 302 and '/student/create-username' in response.location

    assert _row_is_free(side_engine, "SELECT 1 FROM users WHERE id = :u", {"u": user.id})


# ----------------------------------------------------- trace writer (fix 2)

def test_trace_is_written_for_an_ordinary_signed_in_request(
        client, app, side_engine, tlcp_trace_enabled):
    classroom = initialize('chemistry_p1', app)
    student = classroom.students[0]
    login_student(client, student)
    before = _traces(student.seat.public_id)

    with lock_watchdog(side_engine, deadline=5) as report:
        response = client.get('/student/dashboard')

    assert response.status_code == 200
    assert report["cancelled"] == []
    assert _traces(student.seat.public_id) == before + 1


def test_trace_is_skipped_not_waited_when_the_class_row_is_locked(
        client, app, side_engine, tlcp_trace_enabled):
    """Class destruction, an unclaim, or a claim elsewhere holds the class row."""
    classroom = initialize('chemistry_p1', app)
    student = classroom.students[0]
    login_student(client, student)
    before = _traces(student.seat.public_id)

    with held_lock(side_engine, "SELECT 1 FROM classes WHERE class_id = :c FOR UPDATE",
                   {"c": classroom.class_id}):
        with lock_watchdog(side_engine, deadline=5) as report:
            response = client.get('/student/dashboard')

    assert report["cancelled"] == [], "the trace writer waited on a locked class row"
    assert response.status_code == 200
    assert report["elapsed"] < 2
    assert _traces(student.seat.public_id) == before


def test_trace_writer_gives_up_after_its_lock_timeout(
        client, app, side_engine, tlcp_trace_enabled, caplog):
    """Any other wait the writer meets is bounded; the response still goes out."""
    caplog.set_level(logging.WARNING)
    classroom = initialize('chemistry_p1', app)
    student = classroom.students[0]
    login_student(client, student)
    before = _traces(student.seat.public_id)

    # EXCLUSIVE blocks the INSERT but not reads, so only the writer waits.
    with held_lock(side_engine, "LOCK TABLE actor_request_trace IN EXCLUSIVE MODE", {}):
        with lock_watchdog(side_engine, deadline=8) as report:
            response = client.get('/student/dashboard')

    assert report["cancelled"] == [], "the trace writer waited without a lock timeout"
    assert response.status_code == 200
    assert 1.5 < report["elapsed"] < 6
    assert any("Failed to persist TLCP request trace" in r.getMessage() for r in caplog.records)
    assert _traces(student.seat.public_id) == before


# ------------------------------------------- runtime guard: mutation proof

def test_lock_leak_predicate():
    assert not leaked_row_locks(None, None)
    assert leaked_row_locks(None, "731")
    assert not leaked_row_locks("731", "731"), "state the test seeded is not the route's"
    assert leaked_row_locks("731", "732")


def test_request_lock_guard_reports_staging_that_keeps_its_locks(
        client, app, side_engine, monkeypatch, request_lock_guard):
    """Mutation proof (SOP-TEST-003 §IX.A): undo fix 1 and the guard must see it."""
    from app.routes import student as student_routes

    classroom = _class_with_unclaimed_seat(client, app)
    monkeypatch.setattr(student_routes, '_end_setup_staging_transaction', lambda: None)

    try:
        response = _claim(client, classroom)
        assert response.status_code == 302

        assert request_lock_guard.violations == ["POST /student/claim-account -> 302"]
        assert not _row_is_free(side_engine, "SELECT 1 FROM classes WHERE class_id = :c",
                                {"c": classroom.class_id})
    finally:
        # Release the locks this test leaked on purpose, even if an assertion
        # failed, so they cannot block later tests or schema teardown.
        request_lock_guard.violations.clear()
        db.session.rollback()
