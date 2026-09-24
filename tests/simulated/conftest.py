"""Fixture overrides for tests/simulated/: a persistent, realistic-world
database instead of the hermetic per-run one the root conftest.py provides.

Why this exists: the root suite (SPEC-TEST-001) rebuilds its schema from
scratch every run specifically so tests never depend on state another test
left behind -- exactly right for fast, deterministic FEAT-correctness
regression testing. But some things (does this page look right against
data shaped like a real, lived-in classroom -- a real claim mid-review, a
real recovery code scoped to one seat) are better served by a rich,
cross-referential world than by a minimal fixture built fresh each time.

That world is `classroom_economy_simulated`, seeded once from a snapshot of
production (with identity PII decrypted on production and re-encrypted here
under this machine's own ENCRYPTION_KEY, never moving the actual production
key) and left to accumulate real FEAT-created history across runs from here
on. Every mutation to it must still go through the same canonical FEAT
helpers the hermetic suite uses (tests/helpers/*) -- persistence changes
*when* data was provisioned, not *how*. Tests here should query for a
scenario matching specific criteria and create one via FEAT when nothing
matches yet, contributing it back for next time, rather than assuming fixed
row counts or indices (which persistence would otherwise make brittle).

This file is NEVER used for the hermetic suite's own tests -- it only takes
effect for test files placed under tests/simulated/, and it never drops or
rewrites the schema.

CRITICAL implementation note: the root conftest.py (loaded first,
unavoidably, for any test anywhere in this repo) forces `DATABASE_URL` to
`TEST_DATABASE_URL` and imports the shared `app`/`db` objects against that
binding before this file ever runs. Flask-SQLAlchemy's own docs are explicit
that "changes to application config after [init_app] will not be reflected"
-- so mutating `flask_app.config['SQLALCHEMY_DATABASE_URI']` on the
already-initialized shared app, as a first attempt at this file did, is
silently a no-op; it kept querying TEST_DATABASE_URL regardless. That
attempt was caught by an explicit runtime assertion before it could write
anywhere, but the earlier and more serious mistake in the same session --
writing production data into the local dev database -- came from this exact
class of error (a config change assumed to take effect that didn't),
undetected because nothing verified it. Never repeat that: always verify
the bound engine URL before trusting it.

The correct fix is Flask-SQLAlchemy's actual supported pattern for this:
a *separate* Flask app instance, built via the same `create_app()` factory,
gets its own independent engine binding in `db`'s internal per-app registry
(`db` is a single shared extension object; `db.init_app(app)` keys its state
by app instance, not globally) -- no shared-state mutation, no cache-clearing
hacks, nothing to invalidate incorrectly.
"""

import os

import pytest
from dotenv import dotenv_values
from pathlib import Path

from app import create_app
from app.extensions import db

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_dotenv = dotenv_values(PROJECT_ROOT / ".env")
SIMULATED_DB_URL = _dotenv.get("SIMULATED_DB_URL") or os.environ.get("SIMULATED_DB_URL")
if not SIMULATED_DB_URL:
    # The parent tests/conftest.py already excludes this whole directory
    # from a bare `pytest` run (via collect_ignore_glob) when this is unset,
    # since a Skipped exception raised here during conftest import -- unlike
    # inside a test module -- aborts the entire collection, not just this
    # directory. This raise only fires if someone runs tests/simulated/
    # directly without the env var configured; a plain message is enough.
    raise RuntimeError("SIMULATED_DB_URL must be set in .env to run tests/simulated/.")


@pytest.fixture
def app():
    """A genuinely separate Flask app instance bound to the simulated-world
    database, via its own call to the create_app() factory -- never mutates
    the shared app the root conftest.py already configured and imported.

    Unlike the root `app` fixture, this never drops/rebuilds the schema --
    the whole point is a long-lived world. Mutations made by a test are
    real, committed, permanent changes to `classroom_economy_simulated`.
    """
    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = SIMULATED_DB_URL
    try:
        simulated_app = create_app()
    finally:
        if prior_database_url is not None:
            os.environ["DATABASE_URL"] = prior_database_url
        else:
            os.environ.pop("DATABASE_URL", None)

    simulated_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SESSION_COOKIE_SECURE=False,
        RATELIMIT_ENABLED=False,
    )

    with simulated_app.app_context():
        bound_url = str(db.engine.url)
        expected_db = SIMULATED_DB_URL.rsplit("/", 1)[-1]
        assert bound_url.endswith(expected_db), (
            f"Refusing to run: bound to {bound_url!r}, not the simulated DB "
            f"({expected_db!r}). Do not proceed."
        )

        yield simulated_app

        # No drop/rebuild, no rollback of committed work: real FEAT commits
        # made during the test are meant to persist in the world. Only the
        # Python-side session object is released.
        try:
            db.session.rollback()
        except Exception:
            pass
        db.session.remove()


@pytest.fixture
def client(app):
    ctx = app.app_context()
    ctx.push()
    test_client = app.test_client()
    yield test_client
    try:
        db.session.rollback()
    except Exception:
        pass
    db.session.remove()
    ctx.pop()
