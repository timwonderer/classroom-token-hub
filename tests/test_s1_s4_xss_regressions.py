"""Regression tests for S1/S4 (student-to-teacher and teacher-to-student
stored script injection, audit 2026-10-10).

S1 — hall-pass destination is free text (no enum check against the class's
configured pass types) and was rendered unescaped in two places: the
teacher's hall-pass history table (``templates/admin_hall_pass.html``, via
``tbody.innerHTML``) and the student's own dashboard server-state blob
(``templates/student_dashboard.html``, ``attendance_state_json|safe``).
Either lets a student-controlled string execute as script -- in the
teacher's session after approval, or in the student's own session
immediately.

S4 — ``nl2br_filter`` (``app/__init__.py``) wrapped a teacher's raw
announcement text in ``Markup(...)`` with no escaping, so an announcement
executed script in every student's dashboard in that class.

Each test below was confirmed to fail against the pre-fix code (see PR
description / commit history) before asserting the fixed behavior, per
``.claude/rules/testing.md`` Pattern 6 and Mistake 6a.
"""
from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

from app import nl2br_filter
from app.feats.base import FEATContext
from app.services.entitlement_service import grant_hall_passes
from tests.helpers.axe_wcag import authenticated_page, sync_playwright, teacher_session, wcag_live_server  # noqa: F401
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.test_live_test_round2_regressions import _seed_hall_pass_policy

MARKER = "__S1_S4_XSS_FIRED__"
PAYLOAD = f'<img src=x onerror="window.{MARKER}=true">'


# ---------------------------------------------------------------------------
# S4 — nl2br_filter must escape before introducing <br> markup
# ---------------------------------------------------------------------------

def test_nl2br_filter_escapes_html_before_adding_br_tags():
    rendered = str(nl2br_filter(f"line one\n{PAYLOAD}\nline two"))
    assert "<img" not in rendered, "a literal <img> tag must not survive escaping"
    assert "&lt;img" in rendered, "the payload must still be visible as escaped text"
    # The filter's own markup must still be real <br> tags, not escaped.
    assert rendered.count("<br>") == 2


def test_nl2br_filter_none_is_unchanged():
    assert str(nl2br_filter(None)) == ''


# ---------------------------------------------------------------------------
# S4 — announcement message cannot execute in the student dashboard
# ---------------------------------------------------------------------------

def test_announcement_payload_is_escaped_on_student_dashboard(client, app):
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.services.announcement_service import create_class_announcement

    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        with FEATContext("FEAT-SUP-002", idempotency_key="s4-regression:create"):
            create_class_announcement(
                created_by_seat_id=classroom.teacher_seat_id,
                class_id=classroom.class_id,
                title="Heads up",
                message=PAYLOAD,
                priority="normal",
                is_active=True,
                expires_at=None,
            )
        db.session.commit()

    resp = client.get("/student/dashboard")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<img src=x onerror=" not in html, "announcement payload executed unescaped"
    soup = BeautifulSoup(html, "html.parser")
    announcement_text = soup.find(id=lambda i: i and i.startswith("policy-announcement-"))
    assert announcement_text is not None
    assert "<img" not in str(announcement_text.find("img") or "")


# ---------------------------------------------------------------------------
# S1 — hall-pass destination cannot execute via the student dashboard's
# serverState blob
# ---------------------------------------------------------------------------

def test_hall_pass_destination_is_escaped_in_student_dashboard_server_state(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _seed_hall_pass_policy(classroom.class_id)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
            grant_hall_passes(student.seat, 1, correlation_id="corr-s1-dash")

    r = client.post("/api/tap", json={"action": "start_work", "pin": student.pin})
    assert r.status_code == 200, r.data
    r = client.post("/api/hall-pass/request", json={"destination": PAYLOAD, "pin": student.pin})
    assert r.status_code == 200, r.data

    resp = client.get("/student/dashboard")
    html = resp.get_data(as_text=True)
    assert "<img src=x onerror=" not in html, "destination executed unescaped in serverState"

    # The JS reads serverState via .textContent + JSON.parse(); confirm the
    # *decoded* value still round-trips correctly so the fix didn't corrupt data.
    soup = BeautifulSoup(html, "html.parser")
    server_state_tag = soup.find(id="serverState")
    assert server_state_tag is not None
    state = json.loads(server_state_tag.get_text())
    assert state["hall_pass"]["reason"] == PAYLOAD


# ---------------------------------------------------------------------------
# S1 — hall-pass destination cannot execute in the teacher's history view
# (the full authenticated chain: student request -> teacher approval ->
# teacher opens /admin/hall-pass -> loads history tab)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sync_playwright is None, reason="needs Playwright + Chromium")
def test_hall_pass_destination_cannot_execute_in_teacher_history_view(app, client, wcag_live_server):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _seed_hall_pass_policy(classroom.class_id)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
            grant_hall_passes(student.seat, 1, correlation_id="corr-s1-hist")

    login_student(client, student)
    r = client.post("/api/tap", json={"action": "start_work", "pin": student.pin})
    assert r.status_code == 200, r.data
    r = client.post("/api/hall-pass/request", json={"destination": PAYLOAD, "pin": student.pin})
    assert r.status_code == 200, r.data
    req_id = r.get_json()["hall_pass"]["id"]

    login_teacher(client, classroom)
    r = client.post(f"/api/hall-pass/request/{req_id}/approve")
    assert r.status_code == 200, r.data

    # The API still returns the raw string -- the fix is in rendering, not
    # storage/serialization, so this must still hold.
    hist = client.get("/api/hall-pass/history").get_json()
    assert hist["records"][0]["reason"] == PAYLOAD

    sess = teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        try:
            page = authenticated_page(browser, wcag_live_server, sess)
            page.goto("/admin/hall-pass", wait_until="networkidle")
            page.click("#history-tab")
            page.click("button[onclick='loadHistory()']")
            page.wait_for_timeout(1500)
            fired = page.evaluate(f"window.{MARKER} === true")
            # The destination must still be visible to the teacher as plain text.
            row_text = page.inner_text("#historyTableBody")
        finally:
            browser.close()

    assert not fired, "S1 regression: payload executed in the teacher's hall-pass history view"
    assert "onerror" in row_text, "destination should render as literal text, not disappear"
