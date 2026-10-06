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


def axe_violations(page, url: str, *, before_axe=None) -> list:
    response = page.goto(url, wait_until="networkidle")
    assert response is not None and response.ok, f"Could not load {url} (status {response.status if response else 'no response'})"
    if before_axe is not None:
        before_axe(page)
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


def format_violations(violations: list) -> str:
    return "\n".join(
        f"violation: {v['id']} [{v['impact']}] {v['help']}\n"
        + "\n".join(f"    - {n['target']}: {n['failureSummary']}" for n in v["nodes"])
        for v in violations
    )


def _interact(page, state) -> None:
    """Click each of the state's selectors, then let transitions settle.

    Hidden content (an inactive Bootstrap tab pane) is invisible to axe, so a
    state that audits one reveals it the way a user would.
    """
    for selector in state.interact:
        page.click(selector)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)  # Bootstrap's fade transition; contrast is computed on settled opacity


def _fulfill_with(fixture):
    return lambda route, _request=None: route.fulfill(status=200, body=fixture.html, headers=fixture.headers)


def audit_fixture_states(browser, base_url: str, states, *, flask_app=flask_app) -> tuple[dict[str, str], set[str]]:
    """Render every registered state and run axe over it in ``browser``.

    The HTML is produced by the real Jinja environment and response pipeline
    (``tests.a11y_fixtures.render_state``) and handed to Chromium at a URL on the
    live test server, so the project's real CSS, fonts and template JS load.

    Returns ``(failures, rendered_templates)``. ``failures`` maps
    ``"<template>::<state>"`` to a report naming the template, the state and the
    reason (a render failure or the axe violations); ``rendered_templates`` is the
    set of templates that rendered successfully, for the coverage guard.
    """
    from tests.a11y_fixtures import FixtureRenderError, render_state

    failures: dict[str, str] = {}
    rendered_templates: set[str] = set()
    for state in states:
        try:
            fixture = render_state(flask_app, state)
        except FixtureRenderError as exc:
            failures[state.id] = f"AXE FAIL (fixture cannot render)\n{exc}"
            continue
        rendered_templates.update(fixture.templates)

        context = browser.new_context(base_url=base_url)
        page = context.new_page()
        url = f"{base_url}/__a11y_fixture__/{state.template.replace('/', '__')}/{state.state}"
        page.route(f"{url}**", _fulfill_with(fixture))
        if state.query:
            url = f"{url}?{state.query}"
        try:
            violations = axe_violations(page, url, before_axe=lambda p, s=state: _interact(p, s))
        finally:
            context.close()
        if violations:
            failures[state.id] = (
                f"AXE FAIL\ntemplate: templates/{state.template}\nstate: {state.state}\n"
                + format_violations(violations)
            )
    return failures, rendered_templates


def record_fixture_templates(names: set[str]) -> None:
    """Merge fixture-rendered templates into ``AXE_FIXTURE_TEMPLATES_FILE``."""
    target = os.environ.get("AXE_FIXTURE_TEMPLATES_FILE")
    if not target:
        return
    path = Path(target)
    existing: set[str] = set()
    if path.exists():
        existing = set(json.loads(path.read_text(encoding="utf-8")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(existing | names)), encoding="utf-8")
