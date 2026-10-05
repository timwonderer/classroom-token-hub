"""Shared helpers for real WCAG 2.1 A/AA audits of live application pages via
axe-core + Playwright (see tests/test_axe_app_pages.py and tests/simulated/).

Authentication is a real, signature-valid session cookie built via
``flask_app.session_interface.get_signing_serializer`` -- the same mechanism
``client.session_transaction()`` uses -- handed to Playwright's cookie jar.
Not a bypass of the auth boundary: the server verifies the signature exactly
as it would a real login's cookie.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright  # noqa: F401 -- re-exported for skipif checks
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

from flask import template_rendered
from werkzeug.serving import make_server

from app import app as flask_app
from app.extensions import db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import User
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_session import set_canonical_context

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AXE_SOURCE = (REPO_ROOT / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")

# axe-core rules that are known-inapplicable to a component-level page audit
# rather than a real defect. Kept to an explicit, justified allowlist -- an
# empty list is the default and the goal, not a resting state.
ACCEPTED_RULE_IDS: set[str] = set()


def skip_or_fail_without_browser(exc: Exception) -> None:
    """Chromium missing: skip locally, fail where the audit is a gate.

    A skip says "not audited here". The accessibility gate sets
    ``AXE_REQUIRE_BROWSER=1`` because there a skip would let a template change
    merge without ever being audited -- the same silent-green failure the
    ``test_accessibility.py`` empty-corpus bug had.
    """
    if os.environ.get("AXE_REQUIRE_BROWSER") == "1":
        pytest.fail(f"AXE_REQUIRE_BROWSER=1 but Chromium is unavailable: {exc}")
    pytest.skip(f"Chromium is unavailable: {exc}")


def _record_rendered_templates(names: set[str]) -> None:
    """Merge the templates this sweep rendered into ``AXE_RENDERED_TEMPLATES_FILE``.

    ``scripts/check_axe_template_coverage.py`` reads that file to decide whether
    each changed template was actually put in front of axe.
    """
    target = os.environ.get("AXE_RENDERED_TEMPLATES_FILE")
    if not target:
        return
    path = Path(target)
    existing: set[str] = set()
    if path.exists():
        existing = set(json.loads(path.read_text(encoding="utf-8")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(existing | names)), encoding="utf-8")


@pytest.fixture
def wcag_live_server(app):
    """A real HTTP server for the already-configured test Flask app."""
    rendered: set[str] = set()

    def _on_render(sender, template, context, **extra):
        if template.name:
            rendered.add(template.name)

    template_rendered.connect(_on_render, app)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        template_rendered.disconnect(_on_render, app)
        _record_rendered_templates(rendered)


def session_cookie(session_dict: dict) -> str:
    """The exact signed cookie value client.session_transaction() would leave."""
    serializer = flask_app.session_interface.get_signing_serializer(flask_app)
    return serializer.dumps(session_dict)


def authenticated_page(browser, base_url: str, session_dict: dict | None):
    """A fresh browser context, optionally carrying a real, signature-valid
    session cookie (None for a genuinely public/unauthenticated page)."""
    context = browser.new_context(base_url=base_url)
    if session_dict is not None:
        cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
        context.add_cookies([{
            "name": cookie_name,
            "value": session_cookie(session_dict),
            "url": base_url,
        }])
    return context.new_page()


def axe_violations(page, url: str) -> list:
    response = page.goto(url, wait_until="networkidle")
    assert response is not None and response.ok, f"Could not load {url} (status {response.status if response else 'no response'})"
    page.add_script_tag(content=AXE_SOURCE)
    result = page.evaluate("""async () => {
        return await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
        });
    }""")
    return [v for v in result["violations"] if v["id"] not in ACCEPTED_RULE_IDS]


def assert_no_violations(failures: dict[str, list]) -> None:
    assert not failures, "\n\n".join(
        f"{path}:\n" + "\n".join(
            f"  [{v['impact']}] {v['id']}: {v['help']}\n"
            + "\n".join(f"    - {n['target']}: {n['failureSummary']}" for n in v["nodes"])
            for v in violations
        )
        for path, violations in failures.items()
    )


def teacher_session(client, *, user_id: int, class_id: str, seat_id: int) -> dict:
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=user_id, class_id=class_id, seat_id=seat_id, role="admin")
        # set_canonical_context also writes login_time/last_activity (read by
        # routes like student.dashboard) but deliberately never writes "role"
        # ("kept for call-site compatibility; not written anywhere" -- see
        # its own docstring) -- the real app needs it (RoleScopedSessionInterface,
        # establish_*_session), so add it here rather than hand-picking keys
        # and silently missing whatever else a route later starts reading.
        sess["role"] = "admin"
        return dict(sess)


def student_session(client, *, user_id: int, class_id: str, seat_id: int) -> dict:
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=user_id, class_id=class_id, seat_id=seat_id, role="student")
        sess["role"] = "student"
        return dict(sess)


def sysadmin_session(username: str) -> dict:
    """Mirrors tests/helpers/operation_routes.seed_sysadmin_session, but
    against a plain dict (that helper writes straight into a test-client
    session, not a signable dict) -- same keys, same shape. Creates a new
    sysadmin user via the real `create-sysadmin` CLI command if one with
    this username doesn't already exist.
    """
    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    if user is None:
        result = flask_app.test_cli_runner().invoke(args=["create-sysadmin"], input=f"{username}\n")
        assert result.exit_code == 0, result.output
        user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
        assert user is not None, "create-sysadmin did not create a sysadmin user"

    nonce = f"nonce-{username}"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"axe-sweep:sysadmin:{username}:{nonce}"):
        user.current_session_nonce = nonce
        db.session.flush()

    return {
        "is_system_admin": True,
        "user_id": user.id,
        "sysadmin_auth_username": username,
        "current_session_nonce": nonce,
        "last_activity": utc_now().isoformat(),
    }
