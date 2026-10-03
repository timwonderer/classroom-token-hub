"""Every application log record is written once (observed doubled in production 2026-10-02).

The production journal carried each app line twice: once in the configured
format, once as ``INFO:app:...``. The second copy came from the root logger,
which ``create_app()`` left without handlers. The passwordless SDK calls the
module-level ``logging.debug()`` on every API request, and that call runs
``logging.basicConfig()`` on a handler-less root. From then on every
``app.logger`` record propagated to a second, default-format stream handler.

``create_app()`` now puts its handlers on the root logger, which makes the
implicit ``basicConfig()`` a no-op.

These run in a subprocess: under pytest the root logger already carries
pytest's own capture handlers, and those mask the defect.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import logging
from app import app, create_app

app.logger.info("PROBE-before")
logging.debug("ApiSecret: PROBE-secret")   # the passwordless SDK's call shape
app.logger.info("PROBE-after")
logging.getLogger("app.feats.base").warning("PROBE-child")
create_app()
app.logger.info("PROBE-recreated")
"""


def _run_probe() -> str:
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    env.pop("LOG_FORMAT", None)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout + result.stderr


def test_app_records_are_written_once_after_a_third_party_root_level_call():
    output = _run_probe()
    for marker in ("PROBE-before", "PROBE-after", "PROBE-child", "PROBE-recreated"):
        lines = [line for line in output.splitlines() if marker in line]
        assert len(lines) == 1, f"{marker} written {len(lines)} times:\n" + "\n".join(lines)
    assert "INFO:app:" not in output


def test_third_party_debug_records_stay_dropped():
    """Root stays at WARNING: the SDK logs request headers at DEBUG."""
    assert "PROBE-secret" not in _run_probe()
