"""Exactly one process runs the scheduled jobs (app/scheduler_ownership.py).

Until 2026-09-27, importing the ``app`` package started a scheduler in any
process that did it, including the release's ``flask db upgrade``, which runs
beside the live server. These tests hold both layers of the fix: nothing starts
the scheduler on import, and nothing starts it without the advisory lock.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.extensions import db, scheduler
from app.scheduled_tasks import init_scheduled_tasks
from app import scheduler_ownership
from app.scheduler_ownership import (
    SchedulerOwnershipError,
    start_scheduler_when_owner,
    stop_scheduler_ownership,
    try_acquire_scheduler_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_scheduler_left_running():
    yield
    stop_scheduler_ownership()
    assert not scheduler.running


def _wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def test_importing_the_app_in_a_non_test_process_does_not_start_the_scheduler(app):
    """The exact defect: a fresh interpreter that imports the application, as
    every flask command and script does, must not be running scheduled jobs."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "FLASK_ENV": "development",
        "DATABASE_URL": app.config["SQLALCHEMY_DATABASE_URI"],
        "SECRET_KEY": "test-secret",
        "PEPPER_KEY": "test-primary-pepper",
        "ENCRYPTION_KEY": "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=",
        "AUDIT_HMAC_KEY": "test-audit-hmac-key-for-tests-only-not-for-production",
        "PYTHONPATH": str(REPO_ROOT),
    }
    # Wait before looking: an ownership thread started on import would start
    # the scheduler asynchronously, and an immediate check would miss it.
    probe = (
        "import time, threading\n"
        "import app.models\n"
        "time.sleep(3)\n"
        "from app.extensions import scheduler\n"
        "print('SCHEDULER_RUNNING=' + str(scheduler.running))\n"
        "print('OWNER_THREAD=' + str(any(t.name == 'cth-scheduler-owner' for t in threading.enumerate())))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "SCHEDULER_RUNNING=False" in result.stdout
    assert "OWNER_THREAD=False" in result.stdout


def _server_worker_probe(app, seconds=4):
    """A separate OS process doing what a gunicorn worker's post_worker_init does."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "FLASK_ENV": "development",
        "DATABASE_URL": app.config["SQLALCHEMY_DATABASE_URI"],
        "SECRET_KEY": "test-secret",
        "PEPPER_KEY": "test-primary-pepper",
        "ENCRYPTION_KEY": "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=",
        "AUDIT_HMAC_KEY": "test-audit-hmac-key-for-tests-only-not-for-production",
        "PYTHONPATH": str(REPO_ROOT),
    }
    probe = (
        "import time\n"
        "from app import app\n"
        "from app.extensions import scheduler\n"
        "from app.scheduler_ownership import start_scheduler_when_owner, stop_scheduler_ownership\n"
        "start_scheduler_when_owner(app, retry_seconds=0.2)\n"
        f"time.sleep({seconds})\n"
        "print('SCHEDULER_RUNNING=' + str(scheduler.running))\n"
        "stop_scheduler_ownership()\n"
    )
    return subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=120,
    )


def test_a_second_worker_process_does_not_start_the_scheduler_while_the_lock_is_held(app):
    """Multi-worker deployment (SOP-DEP-001 §VII): every worker runs the hook, and
    only the lock holder may run the jobs. The holder here is this test process;
    the second worker is a real separate process."""
    with app.app_context():
        owner = try_acquire_scheduler_lock(db.engine)
    assert owner is not None
    try:
        result = _server_worker_probe(app)
    finally:
        owner.close()
    assert result.returncode == 0, result.stderr[-2000:]
    assert "SCHEDULER_RUNNING=False" in result.stdout
    assert "another process holds the scheduler lock" in result.stderr + result.stdout

    # Control: the same process, with no other holder, does start it. Without
    # this the assertion above could pass because the probe never started anything.
    result = _server_worker_probe(app)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "SCHEDULER_RUNNING=True" in result.stdout
    assert "this process holds the scheduler lock" in result.stderr + result.stdout


def test_init_scheduled_tasks_refuses_without_the_scheduler_lock(app):
    with pytest.raises(SchedulerOwnershipError):
        init_scheduled_tasks(app)
    assert not scheduler.running


def test_only_one_session_can_hold_the_scheduler_lock(app):
    with app.app_context():
        first = try_acquire_scheduler_lock(db.engine)
        assert first is not None
        try:
            assert try_acquire_scheduler_lock(db.engine) is None
        finally:
            first.close()
        # Closing the owning connection is what releases it.
        again = try_acquire_scheduler_lock(db.engine)
        assert again is not None
        again.close()


def test_the_owner_runs_the_jobs_and_a_competing_process_cannot(app):
    start_scheduler_when_owner(app, retry_seconds=0.1)
    assert _wait_for(lambda: scheduler.running), "the owner never started the scheduler"
    assert scheduler_ownership.owns_scheduler()

    with app.app_context():
        assert try_acquire_scheduler_lock(db.engine) is None, (
            "a second session took the lock while the owner was running jobs"
        )

    stop_scheduler_ownership()
    assert not scheduler.running
    with app.app_context():
        released = try_acquire_scheduler_lock(db.engine)
        assert released is not None
        released.close()


def test_a_waiting_process_takes_over_only_after_the_owner_lets_go(app):
    """An overlapping restart: the new server waits, then takes over."""
    with app.app_context():
        old_owner = try_acquire_scheduler_lock(db.engine)
    assert old_owner is not None
    try:
        start_scheduler_when_owner(app, retry_seconds=0.1)
        time.sleep(0.5)
        assert not scheduler.running, "started while another session held the lock"
    finally:
        old_owner.close()
    assert _wait_for(lambda: scheduler.running), "never took over after the lock was released"


def test_losing_the_lock_connection_stops_the_jobs_before_reacquiring(app, monkeypatch):
    """If the owner's connection dies, Postgres has released the lock and
    another process may take it; the jobs must stop rather than run unguarded."""
    start_scheduler_when_owner(app, retry_seconds=0.1)
    assert _wait_for(lambda: scheduler.running)
    lost = scheduler_ownership._owner_connection

    stops = []
    real_shutdown = scheduler.shutdown
    monkeypatch.setattr(scheduler, "shutdown", lambda *a, **k: (stops.append(1), real_shutdown(*a, **k)))
    lost.invalidate()

    assert _wait_for(lambda: stops), "the scheduler kept running after its lock connection died"
    assert _wait_for(
        lambda: scheduler.running and scheduler_ownership._owner_connection not in (None, lost)
    ), "never re-acquired the lock on a new connection"


def test_the_gunicorn_worker_hook_is_the_path_that_starts_the_scheduler(monkeypatch):
    import runpy

    calls = []
    monkeypatch.setattr(
        scheduler_ownership, "start_scheduler_when_owner", lambda app, **kw: calls.append(app)
    )
    config = runpy.run_path(str(REPO_ROOT / "gunicorn.conf.py"))
    config["post_worker_init"](worker=None)
    assert len(calls) == 1
