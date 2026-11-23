"""Regression test for the PASSWORDLESS_API_KEY leak conftest.py now resets.

tests/conftest.py resets PASSWORDLESS_API_KEY/PASSWORDLESS_API_PUBLIC to "" at
session start so a developer's own .env can't leak a real key into
teacher-destruction tests. The reset has to survive app/__init__.py's own
load_dotenv(dotenv_path=..., override=False) call, which runs again later in
conftest.py at `from app import app as flask_app, db` — override=False only
protects a key already *present* in os.environ, so popping the key (leaving
it absent) let that later call repopulate it straight from .env. See
CHANGELOG.md [Unreleased] / PR #1799.

Per CodeRabbit's review on that PR: a test that reimplements the reset itself
proves nothing about whether tests/conftest.py's own reset still runs. These
tests instead spawn a fresh subprocess that imports the real conftest.py (and
through it, the real app) with a value actually present in .env — the exact
scenario the bug occurred in — and read os.environ back out afterward.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

# Importing conftest.py (without running pytest) executes its module-level
# env setup and the `from app import app as flask_app, db` import, but not
# any fixture — the schema drop/recreate lives in a session-scoped fixture,
# never at import time, so this is safe to run standalone.
_PROBE = textwrap.dedent(
    """
    import json
    import os
    import sys
    sys.path.insert(0, "tests")
    import conftest  # noqa: F401
    print(json.dumps({
        "key": os.environ.get("PASSWORDLESS_API_KEY"),
        "public": os.environ.get("PASSWORDLESS_API_PUBLIC"),
    }))
    """
)


_LEAK_VARS = ("PASSWORDLESS_API_KEY", "PASSWORDLESS_API_PUBLIC")


def _subprocess_env_with_no_ambient_leak_vars():
    # The outer pytest process already ran the real (fixed) conftest.py once
    # at collection time, which leaves these two vars set to "" in *this*
    # process's os.environ. A plain inherited env would carry that "" into
    # the child regardless of what the child's own conftest.py does, masking
    # exactly the regression this test exists to catch. Strip them so the
    # child starts with nothing ambient — only .env can supply a value.
    return {k: v for k, v in os.environ.items() if k not in _LEAK_VARS}


def _run_probe_with_a_key_leaked_from_dotenv():
    original = ENV_PATH.read_bytes() if ENV_PATH.exists() else None
    try:
        ENV_PATH.write_bytes(
            (original or b"")
            + b"\nPASSWORDLESS_API_KEY=leaked-from-dotenv\n"
            b"PASSWORDLESS_API_PUBLIC=leaked-from-dotenv\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=REPO_ROOT,
            env=_subprocess_env_with_no_ambient_leak_vars(),
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        if original is None:
            ENV_PATH.unlink(missing_ok=True)
        else:
            ENV_PATH.write_bytes(original)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_conftest_clears_a_passwordless_key_leaked_from_dotenv():
    assert _run_probe_with_a_key_leaked_from_dotenv() == {"key": "", "public": ""}


def test_removing_the_conftest_reset_would_leak_the_dotenv_value():
    """Pattern 7 (tests/helpers): prove the property, not a coincidence — revert
    the fix to the prior os.environ.pop(...) form and watch this go red."""
    conftest_path = REPO_ROOT / "tests" / "conftest.py"
    original = conftest_path.read_bytes()
    reverted = original.replace(
        b'os.environ["PASSWORDLESS_API_KEY"] = ""\n'
        b'os.environ["PASSWORDLESS_API_PUBLIC"] = ""\n',
        b'os.environ.pop("PASSWORDLESS_API_KEY", None)\n'
        b'os.environ.pop("PASSWORDLESS_API_PUBLIC", None)\n',
    )
    assert reverted != original, "expected fix text not found verbatim in conftest.py"
    conftest_path.write_bytes(reverted)
    try:
        payload = _run_probe_with_a_key_leaked_from_dotenv()
    finally:
        conftest_path.write_bytes(original)
    assert payload == {"key": "leaked-from-dotenv", "public": "leaked-from-dotenv"}
