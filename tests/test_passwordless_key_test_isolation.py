"""Regression test for the PASSWORDLESS_API_KEY leak conftest.py now resets.

tests/conftest.py resets PASSWORDLESS_API_KEY/PASSWORDLESS_API_PUBLIC to "" at
session start so a developer's own .env can't leak a real key into
teacher-destruction tests. The reset has to survive app/__init__.py's own
load_dotenv(dotenv_path=..., override=False) call, which runs again later in
conftest.py at `from app import app as flask_app, db` — override=False only
protects a key already *present* in os.environ, so popping the key (leaving
it absent) let that later call repopulate it straight from .env. See
CHANGELOG.md [Unreleased] / PR #1799.
"""
import os

from dotenv import load_dotenv

from app.services.passkey_service import passkey_service_configured


def test_empty_string_reset_survives_a_later_load_dotenv_override_false(tmp_path, monkeypatch):
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("PASSWORDLESS_API_KEY=should-not-leak\nPASSWORDLESS_API_PUBLIC=should-not-leak\n")

    monkeypatch.setenv("PASSWORDLESS_API_KEY", "")
    monkeypatch.setenv("PASSWORDLESS_API_PUBLIC", "")

    # Simulates app/__init__.py's own dotenv load that runs after conftest's reset.
    load_dotenv(dotenv_path=dotenv_file, override=False)

    assert os.environ["PASSWORDLESS_API_KEY"] == ""
    assert os.environ["PASSWORDLESS_API_PUBLIC"] == ""
    assert passkey_service_configured() is False


def test_popping_the_key_would_have_let_a_later_load_dotenv_restore_it(tmp_path, monkeypatch):
    """Proves the regression: this is the exact failure mode of the prior
    os.environ.pop(...)-based reset, before it was changed to "" assignment."""
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("PASSWORDLESS_API_KEY=leaked-value\n")

    monkeypatch.delenv("PASSWORDLESS_API_KEY", raising=False)

    load_dotenv(dotenv_path=dotenv_file, override=False)

    assert os.environ.get("PASSWORDLESS_API_KEY") == "leaked-value"
