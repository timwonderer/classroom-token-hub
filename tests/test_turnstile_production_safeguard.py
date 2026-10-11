"""A missing Turnstile key must never open the bot check in production (audit S3).

``verify_turnstile_token`` skips verification when ``TURNSTILE_SECRET_KEY`` is
unset so local development needs no registered key. Before this safeguard the
key was also absent from the startup requirements, so a production deploy that
dropped it started normally and student login, seat claim, student recovery and
teacher recovery all lost their only bot check. These tests hold both layers:
production refuses to start without the pair, and the verifier fails closed if
the key is gone at request time.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.utils.turnstile import verify_turnstile_token

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def production_config(app):
    keys = ("ENV", "TESTING", "TURNSTILE_SECRET_KEY")
    saved = {key: app.config.get(key) for key in keys}
    app.config.update(ENV="production", TESTING=False)
    try:
        yield app
    finally:
        app.config.update(saved)


def test_verifier_fails_closed_in_production_when_the_secret_is_missing(production_config):
    production_config.config["TURNSTILE_SECRET_KEY"] = None
    with production_config.test_request_context("/"):
        assert verify_turnstile_token("any-token", "203.0.113.9") is False
        assert verify_turnstile_token(None, "203.0.113.9") is False


def test_verifier_fails_closed_for_an_empty_secret_in_production(production_config):
    production_config.config["TURNSTILE_SECRET_KEY"] = ""
    with production_config.test_request_context("/"):
        assert verify_turnstile_token("any-token") is False


def test_verifier_still_skips_without_a_key_outside_production(app):
    saved = {key: app.config.get(key) for key in ("ENV", "TESTING", "TURNSTILE_SECRET_KEY")}
    app.config.update(ENV="development", TESTING=False, TURNSTILE_SECRET_KEY=None)
    try:
        with app.test_request_context("/"):
            assert verify_turnstile_token(None) is True
    finally:
        app.config.update(saved)


def test_verifier_fails_closed_for_a_non_development_non_production_env_with_no_secret(app):
    """CodeRabbit review on PR #1536: FLASK_ENV has no enum validation, so an
    externally-reachable deploy could set it to something other than
    'production' (e.g. 'staging') and, before this fix, silently inherit the
    development-only bypass. The bypass is now an explicit allow-list of
    exactly 'development'; anything else with no secret configured fails
    closed, matching production's own behavior."""
    saved = {key: app.config.get(key) for key in ("ENV", "TESTING", "TURNSTILE_SECRET_KEY")}
    app.config.update(ENV="staging", TESTING=False, TURNSTILE_SECRET_KEY=None)
    try:
        with app.test_request_context("/"):
            assert verify_turnstile_token("any-token") is False
    finally:
        app.config.update(saved)


def test_verifier_with_a_secret_in_production_still_rejects_a_missing_token(production_config):
    """Control: the configured path is unchanged, so the fail-closed branch above
    is distinguishable from the existing no-token rejection."""
    production_config.config["TURNSTILE_SECRET_KEY"] = "configured-secret"
    with production_config.test_request_context("/"):
        assert verify_turnstile_token(None) is False


def _import_app(extra_env: dict, database_url: str):
    # The subprocess needs these set, but not to any particular value — reuse
    # whatever conftest.py already put in this process's own environment
    # (it sets or defaults every one of these at collection time) rather than
    # retyping a second copy of them here.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "DATABASE_URL": database_url,
        "SECRET_KEY": os.environ["SECRET_KEY"],
        "PEPPER_KEY": os.environ["PEPPER_KEY"],
        "ENCRYPTION_KEY": os.environ["ENCRYPTION_KEY"],
        "AUDIT_HMAC_KEY": os.environ["AUDIT_HMAC_KEY"],
        "PYTHONPATH": str(REPO_ROOT),
        **extra_env,
    }
    return subprocess.run(
        [sys.executable, "-c", "import app"], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=120,
    )


def test_production_startup_refuses_to_run_without_the_turnstile_pair(app):
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]
    for present, absent in (
        ({}, "TURNSTILE_SECRET_KEY, TURNSTILE_SITE_KEY"),
        ({"TURNSTILE_SITE_KEY": "site"}, "TURNSTILE_SECRET_KEY"),
        ({"TURNSTILE_SECRET_KEY": "secret"}, "TURNSTILE_SITE_KEY"),
    ):
        result = _import_app({"FLASK_ENV": "production", **present}, database_url)
        assert result.returncode != 0
        assert f"Missing required environment variables: {absent}" in result.stderr


def test_production_startup_accepts_the_pair_and_development_needs_neither(app):
    """Control: the refusal above is caused by the missing keys and nothing else."""
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]
    keys = {"TURNSTILE_SECRET_KEY": "secret", "TURNSTILE_SITE_KEY": "site"}
    for env in ({"FLASK_ENV": "production", **keys}, {"FLASK_ENV": "development"}):
        result = _import_app(env, database_url)
        assert "Missing required environment variables" not in result.stderr, result.stderr[-1500:]
        assert result.returncode == 0, result.stderr[-1500:]
