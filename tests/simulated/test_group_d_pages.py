"""WCAG 2.1 A/AA audit of Group D: pages that need a real, already-existing
domain row (an insurance claim mid-review, a filed issue, an active policy, a
specific student's detail view, an announcement in edit mode) rather than one
built fresh in a hermetic test run. See tests/simulated/conftest.py for why
this directory runs against a persistent, production-sourced world instead of
the per-test-run schema tests/test_axe_app_pages.py uses for Groups A/B/C/E-H.

The anchor for most of this file is the one class in the simulated world that
already owns an issue, both insurance claims, and one hall-pass log: "Rabbit
Hole 101" (class_id 6135423f-80cf-43ec-9ce3-4e05ffb98fad), with teacher seat 1
(user_id 1) and student seat 3 / "Jordan Lee" (user_id 4). Those ids were
found by querying the world directly (see docs/ops/audits/ for the mapping
that sorted every template into a group) rather than hand-assembled -- this
file only supplies session/auth wiring and page-specific IDs, exactly as
tests/test_axe_app_pages.py does for the hermetic groups.
"""

from __future__ import annotations

import re

import pytest

from app.models import Announcement
from app.utils.opaque_refs import make_opaque_ref
from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    axe_violations,
    sync_playwright,
    teacher_session as _build_teacher_session,
    student_session as _build_student_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.support_domain import create_class_announcement

CLASS_ID = "6135423f-80cf-43ec-9ce3-4e05ffb98fad"
TEACHER_USER_ID = 1
TEACHER_SEAT_ID = 1
STUDENT_USER_ID = 4
STUDENT_SEAT_ID = 3
STUDENT_PUBLIC_ID = "a8eff5cf-ac8a-41a9-9ab4-2c40c22515da"
CLAIM_ID = "22a04194-19f6-4a0b-813b-7569019d3c10"
ISSUE_ID = 1
# The entitlement backing this policy for seat 3 (hpent_Fjx8DFhYIabfFF8sHRMdJQ)
# has a GRANTED event with no CONSUMED/EXPIRED/REVOKED terminal event, i.e. it
# is still active coverage -- required for student.file_claim to render a form
# instead of redirecting with a flash ("you don't hold active coverage").
POLICY_UUID = "a5a7e107-3e16-4eb0-bc11-a900887fcd44"


def _find_or_create_announcement(client) -> int:
    """The world had zero announcements for this class as of 2026-09-23.
    Query first; only create (through the real admin route, as a real
    teacher submission) when nothing matches -- contributing the row back to
    the persistent world for next time, per this directory's own convention.
    """
    existing = Announcement.query.filter_by(class_id=CLASS_ID).first()
    if existing is not None:
        return existing.id

    response = create_class_announcement(
        client,
        title="Group D Accessibility Fixture Announcement",
        message="Seeded by tests/simulated/test_group_d_pages.py so the "
        "announcement-edit page has a real row to render.",
        priority="normal",
        is_active=True,
    )
    assert response.status_code == 200, response.data

    created = Announcement.query.filter_by(class_id=CLASS_ID).first()
    assert created is not None, "announcement_create did not persist a row"
    return created.id


def _scrape_student_detail_url(client) -> str:
    """The student-detail route requires a server-signed ``nav`` token minted
    per-request by the admin.students page itself (app/routes/admin.py's
    ``student_detail_url`` template global) -- it cannot be hand-built, so we
    make a real GET request as the teacher and scrape the real link out of
    the rendered HTML, exactly as a browser would follow it.
    """
    response = client.get("/admin/students")
    assert response.status_code == 200, response.data
    html = response.get_data(as_text=True)
    match = re.search(
        r'href="(/admin/students/' + re.escape(STUDENT_PUBLIC_ID) + r'\?nav=[^"]+)"',
        html,
    )
    assert match is not None, "could not find a nav-token link for the target student"
    return match.group(1).replace("&amp;", "&")


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_across_group_d_pages(app, client, wcag_live_server):
    """WCAG 2.1 A/AA audit of Group D: admin_process_claim, admin_view_issue,
    sysadmin_view_issue, student_file_claim, student_view_policy,
    admin_announcement_form (edit mode), and student_detail.
    """
    teacher_session = _build_teacher_session(
        client, user_id=TEACHER_USER_ID, class_id=CLASS_ID, seat_id=TEACHER_SEAT_ID,
    )

    announcement_id = _find_or_create_announcement(client)
    student_detail_path = _scrape_student_detail_url(client)
    # admin.view_issue accepts either a plain numeric id or the encrypted
    # opaque ref; sysadmin.view_issue accepts only the opaque ref (its own
    # _resolve_issue_id_from_ref has no digit-string fast path) -- use the
    # opaque form for both so one ref works everywhere.
    issue_ref = make_opaque_ref("issue", ISSUE_ID)

    # sysadmin_session isn't needed here: sysadmin_view_issue is reachable
    # with a plain sysadmin session dict the same way tests/test_axe_app_pages.py
    # builds one, but this file's teacher/student anchor class already
    # supplies everything else -- build it locally to avoid a second helper
    # import cycle.
    from tests.helpers.axe_wcag import sysadmin_session as _build_sysadmin_session

    admin_session = _build_sysadmin_session("axe_sweep_group_d_sysadmin")

    student_session = _build_student_session(
        client, user_id=STUDENT_USER_ID, class_id=CLASS_ID, seat_id=STUDENT_SEAT_ID,
    )

    pages: list[tuple[str, dict | None]] = [
        (f"/admin/insurance/claim/{CLAIM_ID}", teacher_session),
        (f"/admin/issues/{issue_ref}", teacher_session),
        (student_detail_path, teacher_session),
        (f"/admin/announcements/edit/{announcement_id}", teacher_session),
        (f"/sysadmin/issues/{issue_ref}", admin_session),
        (f"/student/insurance/claim/{POLICY_UUID}", student_session),
        (f"/student/insurance/policy/{POLICY_UUID}", student_session),
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
