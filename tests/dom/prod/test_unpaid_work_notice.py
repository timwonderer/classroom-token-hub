"""The one-time notice for work recorded before a class's first payroll setting.

DOM-PROD-001 §XV.6 (1.7) and DOM-CLASS-001 §VII.1 (3.6), owner rulings 2026-10-01.

The notice is a bootstrap guard, not a payroll-health warning. It shows to the
class's teacher exactly when all three hold:

1. the class has no payroll setting (``payroll_settings`` is append-only, so once
   the first one exists the notice can never apply again);
2. a claimed student seat of that class has work: a session in progress or one
   already completed;
3. the class's teacher has not dismissed it (``classes.unpaid_work_notice_acknowledged_at``).

Dismissing goes through FEAT-CLASS-008 as an explicit CSRF-protected POST. It
records that the teacher saw the notice; it never claims the condition still
holds, so a dismissal from a stale tab after payroll setup is recorded too.

Negative cases carry a positive control, so each test fails on a build that has
no notice at all rather than passing by coincidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import event

from app.extensions import db
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, ClassEconomy, Seat
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now
from tests.dom.identity.helpers import (
    admin_delete_class,
    admin_set_current_class,
    valid_destruction_gate,
)
from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    axe_violations,
    sync_playwright,
    teacher_session as build_teacher_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.class_domain import put_payroll_setting_in_force
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

NOTICE_ID = "unpaid-work-notice"
HEADING = "Students are working, but payroll hasn't been set up yet."
BODY = "These hours will be paid at your first rate once you set up payroll."
DISMISS_URL = "/admin/notices/unpaid-work/dismiss"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _record_completed_work(classroom, seat_id: int, *, minutes: int = 30) -> None:
    """One closed Start Work session, finished an hour ago."""
    end = utc_now() - timedelta(hours=1)
    start = end - timedelta(minutes=minutes)
    ctx = _teacher_ctx(classroom)
    record_attendance_session(
        ctx=ctx, status="active", target_seat_id=seat_id, mechanism="teacher",
        reason="Teacher tap-in", reference_time_utc=start,
        idempotency_key=f"test:unpaid:active:{classroom.class_id}:{seat_id}:{start.isoformat()}",
    )
    record_attendance_session(
        ctx=ctx, status="inactive", target_seat_id=seat_id, mechanism="teacher",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY, reference_time_utc=end,
        idempotency_key=f"test:unpaid:inactive:{classroom.class_id}:{seat_id}:{end.isoformat()}",
    )


def _start_work(classroom, seat_id: int) -> None:
    """A Start Work session still open now."""
    start = utc_now() - timedelta(minutes=5)
    record_attendance_session(
        ctx=_teacher_ctx(classroom), status="active", target_seat_id=seat_id,
        mechanism="teacher", reason="Teacher tap-in", reference_time_utc=start,
        idempotency_key=f"test:unpaid:open:{classroom.class_id}:{seat_id}:{start.isoformat()}",
    )


def _create_first_payroll_setting(classroom) -> None:
    """The class's first payroll setting, in force now."""
    put_payroll_setting_in_force(
        classroom.class_id,
        pay_rate=Decimal("0.50"),
        pay_schedule_type="biweekly",
        first_pay_date=utc_now() + timedelta(days=365),
    )


def _unclaim(classroom, student) -> None:
    from app.feats.identity_feat import unclaim_student_seat

    seat = db.session.get(Seat, student.seat.id)
    unclaim_student_seat(
        canonical_context=_teacher_ctx(classroom),
        seat_id=seat.id,
        expected_generation=seat.claim_generation,
        first_name=student.first_name,
        last_name=student.last_name,
        correlation_id=f"test-unclaim-{seat.id}",
        idempotency_key=f"test:unclaim:{seat.id}",
    )
    db.session.expire_all()
    assert db.session.get(Seat, student.seat.id).user_id is None


def _notice(response):
    assert response.status_code == 200, response.status_code
    return BeautifulSoup(response.data, "html.parser").find(id=NOTICE_ID)


def _acknowledged_at(class_id: str):
    db.session.expire_all()
    return db.session.get(ClassEconomy, class_id).unpaid_work_notice_acknowledged_at


def _dismiss(client, class_id: str, *, next_page: str = "dashboard"):
    return client.post(DISMISS_URL, data={"class_id": class_id, "next": next_page})


@contextmanager
def _captured_writes():
    """Every INSERT/UPDATE/DELETE the database is sent while the block runs."""
    writes: list[str] = []

    def _before(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield writes
    finally:
        event.remove(engine, "before_cursor_execute", _before)


# --------------------------------------------------------------------------
# 1–4: when the notice shows
# --------------------------------------------------------------------------

def test_DOM_PROD_001_XV6__shown_with_no_setting_and_completed_work(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)

    for page in ("/admin/", "/admin/payroll"):
        notice = _notice(client.get(page))
        assert notice is not None, f"{page} does not show the notice"
        text = notice.get_text(" ", strip=True)
        assert HEADING in text
        # Q1: pre-setup work stays payable at the first configured rate.
        assert BODY in text
        link = notice.find("a", string=lambda s: s and "Set up payroll" in s)
        assert link is not None and link["href"].startswith("/admin/payroll")
        form = notice.find("form")
        assert form is not None and form["method"].lower() == "post"
        assert form["action"] == DISMISS_URL
        button = form.find("button", attrs={"type": "submit"})
        assert button is not None and button.get_text(strip=True) == "Dismiss"


def test_DOM_PROD_001_XV6__shown_with_no_setting_and_an_active_session(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)

    assert _notice(client.get("/admin/")) is not None
    assert _notice(client.get("/admin/payroll")) is not None


def test_DOM_PROD_001_XV6__no_notice_without_work(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)

    assert _notice(client.get("/admin/")) is None
    assert _notice(client.get("/admin/payroll")) is None

    # Control: the same class shows it once a student works.
    _start_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None


def test_DOM_PROD_001_XV6__never_shown_once_a_payroll_setting_exists(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None  # control

    _create_first_payroll_setting(classroom)

    assert _acknowledged_at(classroom.class_id) is None
    assert _notice(client.get("/admin/")) is None
    assert _notice(client.get("/admin/payroll")) is None
    # More work after setup does not bring it back.
    _start_work(classroom, classroom.students[1].seat.id)
    assert _notice(client.get("/admin/")) is None


# --------------------------------------------------------------------------
# 5–7: dismissal
# --------------------------------------------------------------------------

def test_FEAT_CLASS_008__dismiss_records_the_acknowledgement_and_hides_it_for_a_new_client(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None

    response = _dismiss(client, classroom.class_id, next_page="payroll")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")

    assert _acknowledged_at(classroom.class_id) is not None
    assert _notice(client.get("/admin/")) is None
    assert _notice(client.get("/admin/payroll")) is None

    other = app.test_client()
    login_teacher(other, classroom)
    assert _notice(other.get("/admin/")) is None
    assert _notice(other.get("/admin/payroll")) is None


def test_FEAT_CLASS_008__dismissing_twice_keeps_the_first_timestamp(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None

    assert _dismiss(client, classroom.class_id).status_code == 302
    first = _acknowledged_at(classroom.class_id)
    assert first is not None

    second = _dismiss(client, classroom.class_id)
    assert second.status_code == 302
    assert second.headers["Location"].endswith("/admin/")
    assert _acknowledged_at(classroom.class_id) == first


def test_FEAT_CLASS_008__a_stale_dismissal_after_setup_is_recorded_without_error(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None  # the tab the teacher left open

    _create_first_payroll_setting(classroom)
    response = _dismiss(client, classroom.class_id)

    assert response.status_code == 302
    assert _acknowledged_at(classroom.class_id) is not None
    assert _notice(client.get("/admin/")) is None


def test_FEAT_CLASS_008__dismiss_is_post_only_and_redirects_only_to_known_pages(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None

    assert client.get(DISMISS_URL).status_code == 405
    assert _acknowledged_at(classroom.class_id) is None

    response = _dismiss(client, classroom.class_id, next_page="https://evil.example/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/")


# --------------------------------------------------------------------------
# 8–9: class isolation and unclaimed seats
# --------------------------------------------------------------------------

def test_DOM_PROD_001_XV6__dismissing_one_class_does_not_hide_another(client, app):
    other_class = initialize("ap_csp_p3", app, with_payroll_settings=False)
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    assert other_class.teacher_user.id == classroom.teacher_user.id
    _record_completed_work(classroom, classroom.students[0].seat.id)
    _record_completed_work(other_class, other_class.students[0].seat.id)

    assert _notice(client.get("/admin/")) is not None
    assert _dismiss(client, classroom.class_id).status_code == 302
    assert _notice(client.get("/admin/")) is None

    assert admin_set_current_class(client, other_class.class_id).status_code == 200
    assert _notice(client.get("/admin/")) is not None
    assert _notice(client.get("/admin/payroll")) is not None
    assert _acknowledged_at(other_class.class_id) is None


def test_DOM_PROD_001_XV6__work_in_another_class_does_not_show_it_here(client, app):
    other_class = initialize("ap_csp_p3", app, with_payroll_settings=False)
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(other_class, other_class.students[0].seat.id)

    assert _notice(client.get("/admin/")) is None
    assert admin_set_current_class(client, other_class.class_id).status_code == 200
    assert _notice(client.get("/admin/")) is not None  # control


def test_DOM_IDEN_002_item2__unclaimed_seat_work_does_not_show_it(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    unclaimed = classroom.students[0]
    _record_completed_work(classroom, unclaimed.seat.id)
    _unclaim(classroom, unclaimed)

    assert _notice(client.get("/admin/")) is None
    assert _notice(client.get("/admin/payroll")) is None

    # Control: a claimed seat's work does show it.
    _start_work(classroom, classroom.students[1].seat.id)
    assert _notice(client.get("/admin/")) is not None


# --------------------------------------------------------------------------
# 10: GET purity
# --------------------------------------------------------------------------

def test_INV_ARC_007__rendering_the_notice_writes_nothing(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    client.get("/admin/")  # warm caches outside the measured window

    for page in ("/admin/", "/admin/payroll"):
        with _captured_writes() as writes:
            response = client.get(page)
        assert _notice(response) is not None
        assert writes == [], f"GET {page} wrote: {writes}"
    assert _acknowledged_at(classroom.class_id) is None


# --------------------------------------------------------------------------
# 11–12: CSRF, ownership, students
# --------------------------------------------------------------------------

def test_FEAT_CLASS_008__dismiss_without_a_csrf_token_is_refused(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)
    page = client.get("/admin/")
    assert _notice(page) is not None

    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    response = _dismiss(client, classroom.class_id)
    assert response.status_code in (400, 302)
    assert _acknowledged_at(classroom.class_id) is None

    # Control: the token the page rendered is accepted.
    token = BeautifulSoup(client.get("/admin/").data, "html.parser").find(id=NOTICE_ID).find(
        "input", attrs={"name": "csrf_token"}
    )["value"]
    accepted = client.post(DISMISS_URL, data={
        "csrf_token": token, "class_id": classroom.class_id, "next": "dashboard",
    })
    assert accepted.status_code == 302
    assert _acknowledged_at(classroom.class_id) is not None


def test_FEAT_CLASS_008__a_teacher_of_another_class_cannot_dismiss_it(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)
    assert _notice(client.get("/admin/")) is not None  # control

    intruder_class = initialize("biology_block_a", app, with_payroll_settings=False)
    assert intruder_class.teacher_user.id != classroom.teacher_user.id
    intruder = app.test_client()
    login_teacher(intruder, intruder_class)

    response = _dismiss(intruder, classroom.class_id)
    assert response.status_code in (302, 400, 403)
    assert _acknowledged_at(classroom.class_id) is None
    assert _acknowledged_at(intruder_class.class_id) is None
    assert _notice(client.get("/admin/")) is not None


def test_FEAT_CLASS_008__the_feat_refuses_a_seat_that_is_not_the_class_teacher(app):
    from app.feats.class_configuration import execute_acknowledge_unpaid_work_notice

    classroom = initialize("chemistry_p1", app, with_payroll_settings=False)
    intruder_class = initialize("biology_block_a", app, with_payroll_settings=False)

    refusals = {
        "another class's teacher": CanonicalContext(
            user_id=intruder_class.teacher_user.id, class_id=classroom.class_id,
            seat_id=intruder_class.teacher_seat.id, actor_role="teacher",
        ),
        "a student of the class": CanonicalContext(
            user_id=classroom.students[0].user.id, class_id=classroom.class_id,
            seat_id=classroom.students[0].seat.id, actor_role="student",
        ),
        "the owner with a seat from another class": CanonicalContext(
            user_id=classroom.teacher_user.id, class_id=classroom.class_id,
            seat_id=intruder_class.teacher_seat.id, actor_role="teacher",
        ),
    }
    for label, ctx in refusals.items():
        result = execute_acknowledge_unpaid_work_notice(
            canonical_context=ctx, class_id=classroom.class_id,
        )
        assert not result.success, label
        assert _acknowledged_at(classroom.class_id) is None, label

    # Control: the class's own teacher seat is accepted.
    result = execute_acknowledge_unpaid_work_notice(
        canonical_context=_teacher_ctx(classroom), class_id=classroom.class_id,
    )
    assert result.success
    assert _acknowledged_at(classroom.class_id) is not None


def test_DOM_PROD_001_XV6__students_never_see_or_dismiss_it(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    student = classroom.students[0]
    _record_completed_work(classroom, student.seat.id)
    assert _notice(client.get("/admin/")) is not None  # control: the teacher sees it

    student_client = app.test_client()
    login_student(student_client, student)
    for page in ("/student/dashboard", "/student/payroll"):
        response = student_client.get(page, follow_redirects=True)
        assert response.status_code == 200
        assert NOTICE_ID.encode() not in response.data
        assert b"payroll hasn" not in response.data

    response = _dismiss(student_client, classroom.class_id)
    assert response.status_code in (302, 403)
    assert _acknowledged_at(classroom.class_id) is None


# --------------------------------------------------------------------------
# 13: removal with an acknowledgement present
# --------------------------------------------------------------------------

def _class_delete_phrase(class_id: str) -> str:
    class_row = db.session.get(ClassEconomy, class_id)
    label = (class_row.display_name or "").strip() or class_row.join_code
    return f"DELETE {label}".upper()


def test_INV_ARC_013__an_acknowledged_class_can_be_destroyed(client, app):
    sibling = initialize("ap_csp_p3", app, with_payroll_settings=False)
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _dismiss(client, classroom.class_id).status_code == 302
    assert _acknowledged_at(classroom.class_id) is not None

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(ClassEconomy, sibling.class_id) is not None


def test_INV_ARC_013__the_last_acknowledged_class_and_its_teacher_can_be_destroyed(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _record_completed_work(classroom, classroom.students[0].seat.id)
    assert _dismiss(client, classroom.class_id).status_code == 302
    teacher_seat_id = classroom.teacher_seat.id

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json().get("account_deleted") is True
    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(Seat, teacher_seat_id) is None


# --------------------------------------------------------------------------
# Accessibility of the rendered notice (INV-ARC-020, SOP-TEST-002)
# --------------------------------------------------------------------------

def test_INV_ARC_020__the_notice_is_a_labelled_region_with_a_real_form(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)

    for page in ("/admin/", "/admin/payroll"):
        soup = BeautifulSoup(client.get(page).data, "html.parser")
        notice = soup.find(id=NOTICE_ID)
        assert notice is not None
        # Static on load: not a live region that interrupts a screen reader.
        assert notice.get("role") not in {"alert", "status"}
        assert notice.find_parent(attrs={"role": "alert"}) is None
        heading = soup.find(id=notice["aria-labelledby"])
        assert heading is not None and heading.get_text(strip=True) == HEADING
        assert heading.name in {"h2", "h3"}
        # The only payroll-setup alert on the page: the setup helper card is not
        # a second, competing alert.
        assert soup.find(string=lambda s: s and "No payroll settings yet" in s) is None
        assert len(soup.find_all(string=lambda s: s and HEADING in s)) == 1


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_INV_ARC_020__axe_finds_no_violations_with_the_notice_shown(app, client, wcag_live_server):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    _start_work(classroom, classroom.students[0].seat.id)
    session_dict = build_teacher_session(
        client, user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
    )
    failures = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            # "/admin/payroll#settings" is where "Set up payroll" lands: the
            # Settings tab opens, so its setup helper card is audited too.
            for path in ("/admin/", "/admin/payroll", "/admin/payroll#settings"):
                page = authenticated_page(browser, wcag_live_server, session_dict)
                violations = axe_violations(page, path)
                assert page.locator(f"#{NOTICE_ID}").count() == 1, path
                if path.endswith("#settings"):
                    assert page.locator("#settings").is_visible(), "Set up payroll did not open the Settings tab"
                    assert page.locator("#settings").get_by_text("Set up payroll").count() >= 1
                if violations:
                    failures[path] = violations
                page.context.close()
        finally:
            browser.close()
    assert_no_violations(failures)
