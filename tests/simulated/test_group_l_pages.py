"""WCAG 2.1 A/AA audit of Group L: ``student_verify_recovery.html``, the most
complex single setup in the accessibility template mapping. Reaching it needs
the full Group J chain (see tests/simulated/test_group_j_pages.py's own
docstring for why this provisions its own fresh teacher/classroom rather than
reusing the shared "teacher_alice" fixture) PLUS a specific seat-scoped
``student_recovery_codes`` row, then a real student session logged in as
*exactly* the seat FEAT-IDEN-103's ``select_class_recipients`` randomly chose
-- any other seat in the same class gets a 404 (get_recovery_code_for_seat
scopes strictly by seat_id).

This file drives begin_attempt -> select_class_recipients directly at the
FEAT layer (unlike Group J, which exercises the real HTTP form once for that
page's own audit) since the page under test here is downstream of both and
gains nothing from re-proving the HTTP entry point a second time.
"""

from __future__ import annotations

import secrets

import pytest

from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    axe_violations,
    sync_playwright,
    student_session as _build_student_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.canonical_classroom import _provision_roster_seat
from tests.helpers.canonical_identities import CLASSROOMS


def _provision_recovery_classroom_and_select(app):
    """Fresh teacher + 4 claimed students (own unique teacher per run -- see
    test_group_j_pages.py's docstring), then drive FEAT-IDEN-103's
    begin_attempt -> select_class_recipients for real so a genuine
    student_recovery_codes row exists to load student_verify_recovery.html
    against. Returns (student_dict, code_id) for the randomly-selected seat.
    """
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.feats.teacher_recovery_feat import begin_attempt, select_class_recipients
    from app.services.classroom_setup import create_class, create_student_user_for_seat, create_teacher
    from app.utils.username_generation import build_username
    from app.utils.join_code import generate_join_code

    roster = CLASSROOMS["chemistry_p1"]["roster"]
    teacher_username = f"teacher.axe-group-l.{secrets.token_hex(6)}"

    with app.app_context():
        join_code = generate_join_code()
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"axe-sweep:group-l:{teacher_username}"):
            teacher_user = create_teacher(teacher_username)
            economy = create_class(
                teacher_user.id, join_code=join_code,
                display_name="Group L Accessibility Fixture", section="Recovery",
                class_timezone="America/Los_Angeles",
            )
            students = []
            for row in roster:
                seat = _provision_roster_seat(economy.class_id, row)
                username = build_username(row["chosen_word"], seat.roster_fingerprint or "")
                student_user = create_student_user_for_seat(
                    seat, username=username, pin=row["pin"], passphrase=row["passphrase"],
                )
                students.append({"seat_id": seat.id, "user_id": student_user.id, "username": username})
        db.session.commit()

        result = begin_attempt(
            pairs=[(join_code, s["username"]) for s in students],
            correlation_id="axe-sweep:group-l", idempotency_key="axe-sweep:group-l:begin",
        )
        db.session.commit()
        assert result is not None, "begin_attempt rejected the freshly-provisioned pairs"

        ok = select_class_recipients(
            request_id=result["id"], attempt_nonce=result["nonce"], class_id=economy.class_id,
            correlation_id="axe-sweep:group-l", idempotency_key="axe-sweep:group-l:select-class",
        )
        db.session.commit()
        assert ok, "select_class_recipients rejected the freshly-started attempt"

        from app.extensions import db as _db
        codes = _db.metadata.tables["student_recovery_codes"]
        rows = _db.session.execute(
            _db.select(codes).where(
                codes.c.recovery_request_id == result["id"], codes.c.class_id == economy.class_id,
            )
        ).all()
        assert len(rows) == 2, f"expected 2 randomly-selected recipients, got {len(rows)}"

        selected_seat_ids = {row.seat_id for row in rows}
        student = next(s for s in students if s["seat_id"] in selected_seat_ids)
        code_row = next(row for row in rows if row.seat_id == student["seat_id"])

        return economy.class_id, student, code_row.id


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_on_student_verify_recovery(app, wcag_live_server):
    """WCAG 2.1 A/AA audit of student_verify_recovery.html, loaded as the
    real seat FEAT-IDEN-103 selected -- any other seat 404s by design.
    """
    class_id, student, code_id = _provision_recovery_classroom_and_select(app)

    with app.test_client() as client:
        session_dict = _build_student_session(
            client, user_id=student["user_id"], class_id=class_id, seat_id=student["seat_id"],
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            page = authenticated_page(browser, wcag_live_server, session_dict)
            url = f"{wcag_live_server}/student/verify-recovery/{code_id}"
            violations = axe_violations(page, url)
            page.context.close()

            assert_no_violations({url: violations} if violations else {})
