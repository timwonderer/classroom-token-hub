"""Startup must refuse to run without the keys the invariants call mandatory.

INV-ARC-016 §VII: "The `AUDIT_HMAC_KEY` environment variable is required at
application startup. The application shall refuse to start if this variable is
absent."

That wording matters. `audit_service` already raised on a missing key -- but it
wrapped its own `_load_signing_key()` in `try/except RuntimeError` so the module
could import under pytest before fixtures ran, leaving `_SIGNING_KEY = b""`. The
process therefore started clean and raised `AuditContextError` at the *first
audited write* instead: mid-transaction, inside a FEAT, in front of a user, on a
box that had looked healthy since deploy. Deferred enforcement is not
enforcement, and "refuse to start" can only be honored at start.

These tests run the import in a subprocess because the check lives at module
scope in `app/__init__.py` and has already passed by the time any test collects.

The key is set to the empty string rather than deleted, deliberately:
`load_dotenv(..., override=False)` would otherwise refill it from the repo's own
`.env`, and the test would pass while proving nothing.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every name the startup gate is expected to enforce. Parametrizing over the
# list rather than over AUDIT_HMAC_KEY alone means a future deletion from
# `required_env_vars` fails here instead of silently widening what may boot.
REQUIRED_ENV_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "FLASK_ENV",
    "ENCRYPTION_KEY",
    "PEPPER_KEY",
    "AUDIT_HMAC_KEY",
]

_IMPORT_APP = "import app"


def _boot(**env_overrides) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", _IMPORT_APP],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("var", REQUIRED_ENV_VARS)
def test_startup_refuses_without_a_required_key(var):
    """Importing `app` must fail loudly, and name the variable it wants."""
    result = _boot(**{var: ""})

    assert result.returncode != 0, (
        f"the application started with {var} unset; "
        "the startup gate in app/__init__.py is not covering it"
    )
    assert "Missing required environment variables" in result.stderr
    assert var in result.stderr


def test_audit_key_failure_is_not_deferred_to_first_write():
    """The regression this suite exists for.

    Pins the *timing*, not just the existence, of the failure. If someone
    removes AUDIT_HMAC_KEY from `required_env_vars`, the import below starts
    succeeding again -- the old behavior, where the process comes up healthy and
    the audit chain breaks later under load.
    """
    result = _boot(AUDIT_HMAC_KEY="")

    assert result.returncode != 0
    assert "AUDIT_HMAC_KEY" in result.stderr


def test_a_fully_configured_environment_still_boots():
    """The negative control.

    Without this, a gate that rejected *every* environment would pass the tests
    above and be indistinguishable from a correct one.
    """
    result = _boot()

    assert result.returncode == 0, (
        f"a fully configured environment failed to boot:\n{result.stderr}"
    )
