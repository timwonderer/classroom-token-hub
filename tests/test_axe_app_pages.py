"""Real WCAG 2.1 A/AA audit of live application pages via axe-core + Playwright.

``test_accessibility.py`` checks a hand-rolled subset of INV-ARC-020's
requirements (labels, alt text, unique IDs, one h1) against server-rendered
HTML with BeautifulSoup -- it cannot see computed CSS, so it has nothing to
say about color contrast, focus visibility, or ARIA validity against actual
roles. ``test_axe_compliance.py`` runs the real axe-core engine, but only
against the 4 static marketing pages in github-pages/, not the application
itself.

This file runs the same axe-core engine against real, authenticated,
server-rendered application pages. It needs an actual browser (computed
styles do not exist without one) and an actual HTTP server (relative asset
URLs -- CSS, fonts, the Turnstile/Material Symbols scripts -- must resolve
for the rendered page to look like what a user really sees), so it starts a
throwaway ``werkzeug`` server bound to the same Flask app object the test
suite already configures, and drives a headless Chromium via Playwright.

Authentication is established by constructing the exact same signed session
cookie ``client.session_transaction()`` would produce -- via
``flask_app.session_interface.get_signing_serializer(flask_app)`` -- and
handing it to Playwright's cookie jar. This is not a bypass of the auth
boundary: it is Flask's own signature-verified cookie, built the same way a
real login would leave it, letting the test drive many pages per role
without paying for a real TOTP/form-fill login on each one.

Page coverage is organized into the groups a full audit of every real page
template (`docs/ops/audits/` mapping, 2026-09-23) sorted them into. This file
currently covers Groups A, E, F, G, H, K -- the ~40 pages reachable with no
domain-row setup beyond a freshly-provisioned classroom. Groups B/D/I/J/L
(feature-gated pages, pages needing a real claim/issue/policy row, dead
templates, and the teacher-recovery flow) need per-page FEAT setup and are
tracked separately rather than crammed in here.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

from werkzeug.serving import make_server

from app import app as flask_app
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import User
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.store_products import publish_store_product

REPO_ROOT = Path(__file__).resolve().parent.parent
AXE_SOURCE = (REPO_ROOT / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")

# axe-core rules that are known-inapplicable to a component-level page audit
# rather than a real defect. Kept to an explicit, justified allowlist -- an
# empty list is the default and the goal, not a resting state.
_ACCEPTED_RULE_IDS: set[str] = set()


@pytest.fixture
def wcag_live_server(app):
    """A real HTTP server for the already-configured test Flask app."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _session_cookie(session_dict: dict) -> str:
    """The exact signed cookie value client.session_transaction() would leave."""
    serializer = flask_app.session_interface.get_signing_serializer(flask_app)
    return serializer.dumps(session_dict)


def _authenticated_page(browser, base_url: str, session_dict: dict | None):
    """A fresh browser context, optionally carrying a real, signature-valid
    session cookie (None for a genuinely public/unauthenticated page)."""
    context = browser.new_context(base_url=base_url)
    if session_dict is not None:
        cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
        context.add_cookies([{
            "name": cookie_name,
            "value": _session_cookie(session_dict),
            "url": base_url,
        }])
    return context.new_page()


def _axe_violations(page, url: str) -> list:
    response = page.goto(url, wait_until="networkidle")
    assert response is not None and response.ok, f"Could not load {url} (status {response.status if response else 'no response'})"
    page.add_script_tag(content=AXE_SOURCE)
    result = page.evaluate("""async () => {
        return await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
        });
    }""")
    return [v for v in result["violations"] if v["id"] not in _ACCEPTED_RULE_IDS]


def _teacher_session(client, classroom) -> dict:
    teacher = classroom.teacher_user
    with client.session_transaction() as sess:
        set_canonical_context(
            sess, user_id=teacher.id, class_id=classroom.class_id,
            seat_id=classroom.teacher_seat.id, role="admin",
        )
        # set_canonical_context also writes login_time/last_activity (read by
        # routes like student.dashboard) but deliberately never writes "role"
        # ("kept for call-site compatibility; not written anywhere" -- see
        # its own docstring) -- the real app needs it (RoleScopedSessionInterface,
        # establish_*_session), so add it here rather than hand-picking keys
        # and silently missing whatever else a route later starts reading.
        sess["role"] = "admin"
        return dict(sess)


def _student_session(client, classroom, student) -> dict:
    with client.session_transaction() as sess:
        set_canonical_context(
            sess, user_id=student.user.id, class_id=classroom.class_id,
            seat_id=student.seat.id, role="student",
        )
        sess["role"] = "student"
        return dict(sess)


def _sysadmin_session(username: str) -> dict:
    """Mirrors tests/helpers/operation_routes.seed_sysadmin_session, but
    against a plain dict (that helper writes straight into a test-client
    session, not a signable dict) -- same keys, same shape.
    """
    from app.extensions import db
    from app.feats.base import FEATContext

    result = flask_app.test_cli_runner().invoke(args=["create-sysadmin"], input=f"{username}\n")
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    assert user is not None, "create-sysadmin did not create a sysadmin user"

    nonce = f"nonce-{username}"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"axe-sweep:sysadmin:{username}"):
        user.current_session_nonce = nonce
        db.session.flush()

    return {
        "is_system_admin": True,
        "user_id": user.id,
        "sysadmin_auth_username": username,
        "current_session_nonce": nonce,
        "last_activity": utc_now().isoformat(),
    }


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_across_pages_needing_no_domain_setup(app, client, wcag_live_server):
    """WCAG 2.1 A/AA audit of every page reachable with no more than a
    freshly-provisioned classroom -- Groups A, E, F, G, H, K of the template
    mapping. Runs every page under one browser/session per role rather than
    one test per page (each page needs a real browser+server round trip);
    collects every violation before asserting, so one broken page doesn't
    hide the rest.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_session = _teacher_session(client, classroom)

    # Group G: mint a real hall-pass verification token while the test
    # client's own session is still the teacher's (the route is
    # admin_required) -- must happen before any later _*_session() call
    # overwrites that same client's session cookie for a different role.
    rotate = client.post("/api/hall-pass/verify-token/rotate")
    assert rotate.status_code == 200, rotate.data
    hall_pass_token = rotate.get_json()["token"]

    student_classroom, student = initialize_as_student("ap_csp_p3", client, app)
    student_session = _student_session(client, student_classroom, student)

    sysadmin_session = _sysadmin_session("axe_sweep_sysadmin")

    # (url, session_dict) -- None means genuinely unauthenticated.
    pages: list[tuple[str, dict | None]] = [
        # Group A -- teacher, no extra setup
        ("/admin/account-delete", teacher_session),
        ("/admin/interpretation/", teacher_session),
        ("/admin/class-delete", teacher_session),
        ("/admin/customizations", teacher_session),
        ("/admin/", teacher_session),
        ("/admin/economic-engine", teacher_session),
        ("/admin/feature-settings", teacher_session),
        ("/admin/issues", teacher_session),
        ("/admin/passkey/settings", teacher_session),
        ("/admin/payroll", teacher_session),
        ("/admin/payroll-history", teacher_session),
        ("/admin/select-class-context", teacher_session),
        ("/admin/setup-recovery", teacher_session),
        ("/admin/students", teacher_session),
        ("/admin/help-support", teacher_session),
        ("/admin/banking", teacher_session),
        # Group C -- feature-disabled fallback, reached with zero extra setup
        ("/admin/store", teacher_session),
        # Group E -- student, no extra setup
        ("/student/dashboard", student_session),
        ("/student/payroll", student_session),
        ("/student/transfer", student_session),
        ("/student/add-class", student_session),
        ("/student/select-class-context", student_session),
        ("/student/setup-complete", student_session),
        ("/student/help-support", student_session),
        ("/student/help-support/submit-issue", student_session),
        # Group F -- public, no auth, no setup
        ("/admin/signup", None),
        ("/docs/", None),
        ("/docs/search", None),
        ("/docs/timeline", None),
        ("/docs/user-guides/teacher_manual", None),
        ("/offline", None),
        ("/recovery/lookup", None),
        # Group G -- public, needs a real minted token
        (f"/verify/hallpass/{hall_pass_token}", None),
        # Group H -- sysadmin, no extra setup
        ("/sysadmin/dashboard", sysadmin_session),
        ("/sysadmin/combined-logs", sysadmin_session),
        ("/sysadmin/support", sysadmin_session),
        ("/sysadmin/passkey/settings", sysadmin_session),
    ]

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            failures: dict[str, list] = {}
            for path, session_dict in pages:
                page = _authenticated_page(browser, wcag_live_server, session_dict)
                violations = _axe_violations(page, f"{wcag_live_server}{path}")
                if violations:
                    failures[path] = violations
                page.context.close()

            assert not failures, "\n\n".join(
                f"{path}:\n" + "\n".join(
                    f"  [{v['impact']}] {v['id']}: {v['help']}\n"
                    + "\n".join(f"    - {n['target']}: {n['failureSummary']}" for n in v["nodes"])
                    for v in violations
                )
                for path, violations in failures.items()
            )


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_across_feature_gated_pages(app, client, wcag_live_server):
    """WCAG 2.1 A/AA audit of Group B: pages gated behind a class feature
    that starts OFF by default (hall_pass, insurance, rent, store), plus the
    two admin_edit_* pages that also need a real domain row to reach 200.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    for feature in ("hall_pass", "insurance", "rent", "store"):
        enable_class_feature(class_id=classroom.class_id, feature=feature)

    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"axe-sweep:store-item:{classroom.class_id}",
    ):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            name="Axe Sweep Test Item",
            description="Fixture product for the accessibility sweep.",
            price="5.00",
        )

    teacher_session = _teacher_session(client, classroom)

    pages: list[tuple[str, dict | None]] = [
        ("/admin/hall-pass", teacher_session),
        ("/admin/insurance", teacher_session),
        ("/admin/rent-settings", teacher_session),
        ("/admin/store", teacher_session),
        ("/admin/insurance/new", teacher_session),
        (f"/admin/store/edit/{product.product_lineage_uuid}", teacher_session),
    ]

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            failures: dict[str, list] = {}
            for path, session_dict in pages:
                page = _authenticated_page(browser, wcag_live_server, session_dict)
                violations = _axe_violations(page, f"{wcag_live_server}{path}")
                if violations:
                    failures[path] = violations
                page.context.close()

            assert not failures, "\n\n".join(
                f"{path}:\n" + "\n".join(
                    f"  [{v['impact']}] {v['id']}: {v['help']}\n"
                    + "\n".join(f"    - {n['target']}: {n['failureSummary']}" for n in v["nodes"])
                    for v in violations
                )
                for path, violations in failures.items()
            )
