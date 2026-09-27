"""Exactly one process may run the scheduled jobs.

Scheduled jobs settle the ledger, run payroll, pay interest and reconcile rent.
Two schedulers running at once would run each of those twice. Until 2026-09-27,
``create_app()`` started the scheduler in every process that imported the
``app`` package: every ``flask`` command, every script, and the release
workflow's ``flask db upgrade``, which runs while the old server is still up.
Production had no class data yet, so nothing was double-run. That was luck.

Two independent layers now prevent it:

1. **Only the server asks.** Nothing starts the scheduler on import or in
   ``create_app()``. The gunicorn ``post_worker_init`` hook in
   ``gunicorn.conf.py`` is the one caller of ``start_scheduler_when_owner``.
   CLI commands, migrations, scripts and shells never run gunicorn hooks.
2. **Only the lock holder may start it.** ``init_scheduled_tasks`` refuses to
   start unless this process holds a PostgreSQL session-level advisory lock on
   a dedicated connection. A second server worker, an overlapping restart, or a
   stray call cannot take it while the owner lives. The owner re-checks every
   heartbeat (10s by default) that its own session still holds the lock, and
   stops its jobs as soon as it does not.

A new owner waiting on a restart keeps retrying in the background and takes over
when the old process exits and Postgres releases its lock.
"""

from __future__ import annotations

import logging
import os
import threading

from sqlalchemy import text

logger = logging.getLogger(__name__)

# A fixed advisory-lock key for "the CTH scheduler owner", in the signed bigint
# range. It only has to be unique among advisory locks this database uses; it
# is the only one.
SCHEDULER_LOCK_KEY = 7_425_163_849_122_001

_state_lock = threading.Lock()
_owner_connection = None
_owner_thread: threading.Thread | None = None


class SchedulerOwnershipError(RuntimeError):
    """Raised when something tries to start the scheduler without owning it."""


def owns_scheduler() -> bool:
    """Whether this process currently holds the scheduler lock."""
    return _owner_connection is not None


def try_acquire_scheduler_lock(engine):
    """Take the advisory lock on a dedicated connection.

    Returns that connection, which must stay open for as long as the lock is
    meant to be held, or ``None`` when another session holds it. The lock is
    tied to the connection: closing the connection releases it.
    """
    connection = engine.connect()
    try:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEDULER_LOCK_KEY}
        ).scalar()
        # Leave no transaction open on a connection that lives for the process.
        connection.commit()
    except Exception:
        connection.close()
        raise
    if not acquired:
        connection.close()
        return None
    # Take this connection out of the pool. A session-level advisory lock lives
    # as long as the database session, and a pooled connection's close() only
    # returns the session to the pool with the lock still held. Detached,
    # close() ends the session and Postgres releases the lock.
    connection.detach()
    return connection


def holds_scheduler_lock(connection) -> bool:
    """Whether the session behind ``connection`` holds the scheduler lock now.

    Checking only that the connection answers is not enough. After a dropped
    connection, SQLAlchemy reconnects on the next use, and that new session
    holds no lock even though ``SELECT 1`` succeeds. So ask Postgres whether this
    backend holds the lock. A bigint advisory key is stored as
    classid (high 32 bits), objid (low 32 bits), objsubid 1.
    """
    held = connection.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_locks"
            " WHERE locktype = 'advisory' AND granted AND objsubid = 1"
            " AND pid = pg_backend_pid()"
            " AND ((classid::bigint << 32) | objid::bigint) = :key)"
        ),
        {"key": SCHEDULER_LOCK_KEY},
    ).scalar()
    connection.commit()
    return bool(held)


def _release_ownership() -> None:
    global _owner_connection
    from app.extensions import scheduler

    with _state_lock:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        if _owner_connection is not None:
            try:
                _owner_connection.close()
            except Exception:
                pass
        _owner_connection = None


def _ownership_loop(app, retry_seconds: float, stop: threading.Event) -> None:
    global _owner_connection
    from app.scheduled_tasks import init_scheduled_tasks

    waiting_logged = False
    while not stop.is_set():
        if _owner_connection is None:
            try:
                with app.app_context():
                    from app.extensions import db
                    connection = try_acquire_scheduler_lock(db.engine)
            except Exception:
                logger.exception("Scheduler lock attempt failed; retrying")
                connection = None
            if connection is None:
                if not waiting_logged:
                    app.logger.warning(
                        "Scheduler not started in pid %s: another process holds the "
                        "scheduler lock. Retrying every %ss.", os.getpid(), retry_seconds,
                    )
                    waiting_logged = True
            else:
                with _state_lock:
                    _owner_connection = connection
                try:
                    init_scheduled_tasks(app)
                except Exception:
                    logger.exception("Scheduler failed to start; releasing the lock")
                    _release_ownership()
                else:
                    app.logger.warning(
                        "Scheduler started in pid %s: this process holds the scheduler lock.",
                        os.getpid(),
                    )
                    waiting_logged = False
        else:
            # Heartbeat. If this session no longer holds the lock (the
            # connection died, or was silently replaced by a reconnect),
            # another process may take it: stop our jobs rather than run them
            # unguarded.
            try:
                still_held = holds_scheduler_lock(_owner_connection)
            except Exception:
                still_held = False
            if not still_held:
                app.logger.error(
                    "Scheduler lock no longer held in pid %s; stopping scheduled jobs "
                    "and re-acquiring.", os.getpid(),
                )
                _release_ownership()
        stop.wait(retry_seconds)


def start_scheduler_when_owner(app, *, retry_seconds: float = 10.0) -> threading.Thread:
    """Start the scheduled jobs in this process once it owns the scheduler lock.

    The one caller is the gunicorn ``post_worker_init`` hook. Returns the
    background thread that acquires, heartbeats and, if needed, re-acquires the
    lock. Calling it twice in one process returns the running thread.
    """
    global _owner_thread
    with _state_lock:
        if _owner_thread is not None and _owner_thread.is_alive():
            return _owner_thread
        stop = threading.Event()
        _owner_thread = threading.Thread(
            target=_ownership_loop,
            args=(app, retry_seconds, stop),
            name="cth-scheduler-owner",
            daemon=True,
        )
        _owner_thread.stop_event = stop  # type: ignore[attr-defined]
        _owner_thread.start()
        return _owner_thread


def stop_scheduler_ownership() -> None:
    """Stop the ownership thread and the scheduler, and release the lock."""
    global _owner_thread
    thread = _owner_thread
    if thread is not None:
        thread.stop_event.set()  # type: ignore[attr-defined]
        thread.join(timeout=5)
    _owner_thread = None
    _release_ownership()
