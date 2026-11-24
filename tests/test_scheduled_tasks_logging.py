"""Scheduled-job start/completion lines never reached the production journal
(issue #1717).

``run_store_item_expiry_job`` and its siblings logged
``logger = logging.getLogger('scheduled_tasks')`` -- a bare, top-level logger
name with no dot, so it is its own direct child of the *root* logger, not of
``app``. ``create_app()`` (see ``app/__init__.py``) sets an explicit level on
``app.logger`` (``app``) but deliberately leaves root at ``WARNING`` so
third-party ``DEBUG``/``INFO`` records stay dropped (see
``test_logging_single_write.py``). A logger with no level of its own resolves
its *effective* level by walking up to the nearest ancestor that has one, and
``logging.Logger.isEnabledFor`` rejects a record against that effective level
before it is ever handed to any handler -- so every
``logger.info("Starting scheduled ...")`` / ``"... job completed ..."`` call in
``app/scheduled_tasks.py`` was silently dropped at the logger itself, never
reaching root's handlers (and therefore never reaching
``journalctl -u classroom-economy``), while ``app.feats.base``'s
``logging.getLogger(__name__)`` (a child of ``app``, which FEAT-ENTRY lines use
and which DOES reach the journal) inherited ``app.logger``'s INFO level
correctly.

The fix: ``app/scheduled_tasks.py`` now uses ``logging.getLogger(__name__)``,
making its logger ``app.scheduled_tasks`` -- a child of ``app`` -- exactly like
``app.feats.base``.

This test exercises the real production logging configuration built by
``create_app()`` (not ``caplog`` with no real config, which would pass whether
or not this bug were present) in a subprocess, the same way
``test_logging_single_write.py`` does, and asserts the scheduled-tasks
logger's effective level admits INFO and that an INFO record actually reaches
stdout (root's stream handler -- what systemd/journald captures).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import logging
from app import app, create_app  # noqa: F401  (import builds the production logging config)
import app.scheduled_tasks as scheduled_tasks

logger = logging.getLogger(scheduled_tasks.__name__)
print("EFFECTIVE_LEVEL=" + logging.getLevelName(logger.getEffectiveLevel()))
print("IS_ENABLED_FOR_INFO=" + str(logger.isEnabledFor(logging.INFO)))

# Exercise the module's OWN logger calls end to end (not a synthetic logger
# constructed by this probe), through the module's real start-of-job and
# end-of-job log lines, under create_app()'s real production logging config.
# run_rent_reconciliation_job is a plain function (not FEAT-context-wrapped at
# the top level); this test runs outside the per-test fixture that gives
# every pytest `app`-using test its own fresh database, so the rent feature
# gate is forced off here to guarantee this probe only ever reads
# ClassEconomy and never writes to whatever database TEST_DATABASE_URL/
# DATABASE_URL happens to name.
import app.services.class_configuration_query_service as _ccqs
_ccqs.is_feature_enabled = lambda *a, **k: False

with app.app_context():
    scheduled_tasks.run_rent_reconciliation_job()
"""


def _run_probe() -> str:
    # Point the subprocess's own app instance (which reads DATABASE_URL fresh
    # from the environment/.env, independently of this process's Flask
    # config) at the exact database the `app` fixture just migrated, so the
    # probe's `classes` table exists whether or not this file is run alone.
    # Without this, a lone, from-scratch run of this file hits a database
    # with no schema at all: run_rent_reconciliation_job's enumeration query
    # raises, is caught, and the job returns before its completion line —
    # the regression this test exists to catch would then go unnoticed.
    test_db_url = os.environ["TEST_DATABASE_URL"]
    env = dict(
        os.environ,
        PYTHONPATH=str(REPO_ROOT),
        FLASK_ENV="production",
        DATABASE_URL=test_db_url,
        # create_app() requires these only in production (app/__init__.py);
        # verify_turnstile_token() itself is not exercised by this probe.
        TURNSTILE_SECRET_KEY="probe-secret",
        TURNSTILE_SITE_KEY="probe-site",
    )
    env.pop("LOG_FORMAT", None)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return result.stdout + result.stderr


def test_scheduled_tasks_logger_is_a_child_of_app_and_enabled_for_info(app):
    """The logger's own level, not just a handler's, must admit INFO.

    Requests the `app` fixture solely so tests/conftest.py migrates
    TEST_DATABASE_URL before the subprocess (pointed at that same URL via
    `_run_probe`) connects to it -- this test makes no DB assertions itself,
    but shares `_run_probe` with the one that does.
    """
    output = _run_probe()
    assert "EFFECTIVE_LEVEL=INFO" in output, output
    assert "IS_ENABLED_FOR_INFO=True" in output, output


def test_scheduled_job_start_and_completion_lines_reach_the_journal_sink(app):
    """Under the production logging configuration, a real job's own start and
    completion INFO lines (the lines issue #1717 found missing from
    `journalctl -u classroom-economy`) reach the stream handler that
    journald reads (stdout under systemd) -- not just the per-class ERROR/
    exception lines a failure would produce.

    Requests the `app` fixture so tests/conftest.py gives TEST_DATABASE_URL a
    freshly migrated schema before the subprocess runs against it (via
    `_run_probe`, which points the subprocess at that exact URL) -- this test
    must pass whether it is the only test collected in a run or one of many.
    """
    output = _run_probe()
    assert "Starting scheduled rent reconciliation job" in output, output
    # Counts are not asserted exactly: `app` only guarantees a migrated
    # schema, not a seeded fixture -- the line reaching the sink at all,
    # against a real, possibly-empty `classes` table, is what issue #1717
    # found missing.
    assert re.search(
        r"Rent reconciliation job completed\. "
        r"Reconciled \d+ class\(es\), skipped \d+, failed 0",
        output,
    ), output
