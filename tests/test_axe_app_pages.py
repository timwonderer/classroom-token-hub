"""Real WCAG 2.1 A/AA audit of live application pages via axe-core + Playwright.

``test_accessibility.py`` checks a hand-rolled subset of INV-ARC-020's
requirements (labels, alt text, unique IDs, one h1) against server-rendered
HTML with BeautifulSoup -- it cannot see computed CSS, so it has nothing to
say about color contrast, focus visibility, or ARIA validity against actual
roles. ``test_axe_compliance.py`` runs the real axe-core engine, but only
against the 4 static marketing pages in github-pages/, not the application
itself.

This file runs the same axe-core engine against real, authenticated,
server-rendered application pages, provisioned fresh per run via the
hermetic ``app``/``client`` fixtures (SPEC-TEST-001). The shared
browser/session machinery lives in ``tests/helpers/axe_wcag.py`` -- also used
by ``tests/simulated/`` for pages that need a real pre-existing domain row
(a claim, an issue, a recovery-flow row) rather than one built fresh here.

Page coverage is organized into the groups a full audit of every real page
template (`docs/ops/audits/` mapping, 2026-09-23) sorted them into. This file
covers Groups A, B, C, E, F, G, H, K -- the pages reachable with no more than
a freshly-provisioned classroom (Group B needs `enable_class_feature` too).
Groups D/I/J/L (a real claim/issue/policy/recovery-code row, and a few dead
templates) are covered from the persistent simulated-world database instead
-- see tests/simulated/.
"""

from __future__ import annotations

import pytest

from app.feats.base import FEATContext
from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    axe_violations,
    sync_playwright,
    sysadmin_session,
    teacher_session as _build_teacher_session,
    student_session as _build_student_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.store_products import publish_store_product


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
    teacher_session = _build_teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )

    # Group G: mint a real hall-pass verification token while the test
    # client's own session is still the teacher's (the route is
    # admin_required) -- must happen before any later *_session() call
    # overwrites that same client's session cookie for a different role.
    rotate = client.post("/api/hall-pass/verify-token/rotate")
    assert rotate.status_code == 200, rotate.data
    hall_pass_token = rotate.get_json()["token"]

    student_classroom, student = initialize_as_student("ap_csp_p3", client, app)
    student_session = _build_student_session(
        client, user_id=student.user.id, class_id=student_classroom.class_id,
        seat_id=student.seat.id,
    )

    admin_session = sysadmin_session("axe_sweep_sysadmin")

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
        ("/docs/user-guides/teacher_manual", None),
        ("/offline", None),
        ("/recovery/lookup", None),
        # Group G -- public, needs a real minted token
        (f"/verify/hallpass/{hall_pass_token}", None),
        # Group H -- sysadmin, no extra setup
        ("/sysadmin/dashboard", admin_session),
        ("/sysadmin/combined-logs", admin_session),
        ("/sysadmin/support", admin_session),
        ("/sysadmin/passkey/settings", admin_session),
    ]

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            failures: dict[str, list] = {}
            for path, session_dict in pages:
                page = authenticated_page(browser, wcag_live_server, session_dict)
                violations = axe_violations(page, f"{wcag_live_server}{path}")
                if violations:
                    failures[path] = violations
                page.context.close()

            assert_no_violations(failures)


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

    teacher_session = _build_teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )

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
                page = authenticated_page(browser, wcag_live_server, session_dict)
                violations = axe_violations(page, f"{wcag_live_server}{path}")
                if violations:
                    failures[path] = violations
                page.context.close()

            assert_no_violations(failures)
