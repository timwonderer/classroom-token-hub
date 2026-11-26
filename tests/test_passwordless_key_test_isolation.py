"""Regression test for the PASSWORDLESS_API_KEY leak conftest.py now resets.

tests/conftest.py resets PASSWORDLESS_API_KEY/PASSWORDLESS_API_PUBLIC to "" at
session start so a developer's own .env can't leak a real key into
teacher-destruction tests. The reset has to survive app/__init__.py's own
load_dotenv(dotenv_path=..., override=False) call, which runs again later in
conftest.py at `from app import app as flask_app, db` — override=False only
protects a key already *present* in os.environ, so popping the key (leaving
it absent) let that later call repopulate it straight from .env. See
CHANGELOG.md [Unreleased] / PR #1799.

Earlier drafts of this test ran a real subprocess against the shared .env /
tests/conftest.py on disk to exercise the production code path directly.
CodeRabbit correctly flagged that mutating those shared files — even
temporarily, even with a try/finally restore — is unsafe if a second pytest
session starts concurrently in the same checkout (it would read, or write
back, the wrong content). This version instead:

1. Asserts directly on conftest.py's own source text, so reverting the fix
   to the prior os.environ.pop(...) form fails this test outright — no
   subprocess, no file mutation, nothing shared with a concurrent session.
   (Same idea as the pure-function checks in test_conftest_drop_guard.py.)
2. Proves the underlying load_dotenv(override=False) mechanism in full
   isolation, using pytest's own tmp_path/monkeypatch fixtures.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"


def test_conftest_resets_passwordless_vars_with_assignment_not_pop():
    """Mutation proof (testing.md MISTAKE 6a): reverting conftest.py's reset
    to the prior os.environ.pop(...) form flips every assertion here."""
    source = CONFTEST_PATH.read_text()
    assert 'os.environ["PASSWORDLESS_API_KEY"] = ""' in source
    assert 'os.environ["PASSWORDLESS_API_PUBLIC"] = ""' in source
    assert 'os.environ.pop("PASSWORDLESS_API_KEY"' not in source
    assert 'os.environ.pop("PASSWORDLESS_API_PUBLIC"' not in source


def test_empty_string_reset_survives_a_later_load_dotenv_override_false(tmp_path, monkeypatch):
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("PASSWORDLESS_API_KEY=should-not-leak\nPASSWORDLESS_API_PUBLIC=should-not-leak\n")

    # Mirrors conftest.py's own reset, in isolation.
    monkeypatch.setenv("PASSWORDLESS_API_KEY", "")
    monkeypatch.setenv("PASSWORDLESS_API_PUBLIC", "")

    # Mirrors app/__init__.py's own dotenv load, which runs again later.
    load_dotenv(dotenv_path=dotenv_file, override=False)

    assert os.environ["PASSWORDLESS_API_KEY"] == ""
    assert os.environ["PASSWORDLESS_API_PUBLIC"] == ""


def test_popping_the_key_would_have_let_a_later_load_dotenv_restore_it(tmp_path, monkeypatch):
    """Pattern 7 (.claude/rules/testing.md): proves the property, not a
    coincidence — this is the exact failure mode of the prior
    os.environ.pop(...)-based reset, before it was changed to "" assignment."""
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("PASSWORDLESS_API_KEY=leaked-value\n")

    monkeypatch.delenv("PASSWORDLESS_API_KEY", raising=False)

    load_dotenv(dotenv_path=dotenv_file, override=False)

    assert os.environ.get("PASSWORDLESS_API_KEY") == "leaked-value"
