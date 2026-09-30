"""One-time payroll correction for incident PROD-PAY-001 (2026-09-28).

The earlier payroll rule dropped the clock-in of a session still running at the
seat's previous payroll, so the rest of that session went unpaid. The correction
reproduces what each earlier-rule run paid, compares it with the time worked in
that run's window, and proposes the difference. A teacher approves; nothing is
posted on the platform's own authority. Each credit is a ``manual_credit`` with
the teacher's seat as actor and mechanism ``SYSTEM``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, PayrollEvent, Transaction
from app.routes import admin as admin_routes
from app.services.context_resolver import CanonicalContext
from app.services.ledger_posting_service import create_pending_transaction
from app.services.payroll import corrections as corrections_module
from app.services.payroll.corrections import (
    CORRECTED,
    NEEDS_REVIEW,
    PROD_PAY_001,
    PROPOSED,
    build_class_correction_proposal,
    correction_key,
)
from app.services.payroll.settings import (
    append_payroll_setting,
    first_payroll_setting,
    pay_rate_per_second,
    payroll_setting_history,
)
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import (
    initialize,
    initialize_as_student,
    initialize_as_teacher,
)

# 10:00 PDT on 2026-09-28; every instant below stays inside that class day.
T0 = datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user_id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id,
        actor_role="teacher",
    )


def _pay_for(cid: str, minutes: int) -> Decimal:
    # One setting per class, as in production: the rate every run was priced at.
    rate = pay_rate_per_second(first_payroll_setting(cid))
    return (Decimal(minutes * 60) * rate).quantize(Decimal("0.01"))


def _attendance(classroom, seat_id: int, *rows) -> None:
    with FEATContext(
        "FEAT-PROD-001", correlation_id=f"att:{uuid4()}", idempotency_key=f"att:{uuid4()}"
    ):
        for status, instant in rows:
            db.session.add(AttendanceSession(
                target_seat_id=seat_id, class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat_id, status=status,
                reason_code="start_work" if status == "active" else "done_for_day",
                timestamp=instant,
            ))
        db.session.flush()


def _legacy_run(classroom, seat_id: int, at: datetime, amount: Decimal) -> None:
    """A payroll event as the earlier rule wrote it: no settlement_rule marker.

    FEAT-PROD-003 derives every payroll amount now, so the historical event and
    its ledger credit are written as they were recorded in production.
    """
    key = f"payroll-cycle:{uuid4()}:seat:{seat_id}"
    correlation_id = f"legacy:{uuid4()}"
    with FEATContext("FEAT-PROD-004", idempotency_key=f"legacy:{uuid4()}"):
        db.session.add(PayrollEvent(
            class_id=classroom.class_id, target_seat_id=seat_id,
            actor_seat_id=classroom.teacher_seat_id, correlation_id=correlation_id,
            idempotency_key=key, policy_uuid=first_payroll_setting(classroom.class_id).policy_uuid,
            mechanism="TEACHER", payroll_event_type="payroll", recorded_at=at,
            summary_json={"source": "class_payroll_settlement", "description": "Payroll based on attendance"},
        ))
        if amount != Decimal("0.00"):
            create_pending_transaction(
                seat_id=seat_id, class_id=classroom.class_id, target_seat_id=seat_id,
                actor_seat_id=classroom.teacher_seat_id, mechanism="teacher", amount=amount,
                account_type="checking", type="payroll",
                description="Payroll based on attendance", idempotency_key=key,
            )
        db.session.flush()


def _incident(classroom, *, underpaid_first_run: Decimal | None = None):
    """Recreate the 2026-09-28 shape with the amounts the earlier rule paid.

    ``working`` was paid 30 min at a run made while still clocked in, clocked out
    20 min later, and the next run paid nothing for those 20 min. ``finished``
    clocked out before the first run and was paid correctly.
    """
    cid = classroom.class_id
    working, finished = classroom.students[0].seat.id, classroom.students[1].seat.id
    _attendance(classroom, working, ("active", _at(0)), ("inactive", _at(50)))
    _attendance(classroom, finished, ("active", _at(0)), ("inactive", _at(20)))
    _legacy_run(classroom, working, _at(30), underpaid_first_run or _pay_for(cid, 30))
    _legacy_run(classroom, finished, _at(30), _pay_for(cid, 20))
    _legacy_run(classroom, working, _at(60), Decimal("0.00"))
    _legacy_run(classroom, finished, _at(60), Decimal("0.00"))
    return working, finished


def _approve(classroom, seat_ids: set[int]) -> list[int]:
    """The route's approval step: plan in the service, post through FEAT-PROD-003."""
    return admin_routes._post_payroll_corrections(_teacher_ctx(classroom), seat_ids)


def _corrections(cid: str):
    return PayrollEvent.query.filter_by(class_id=cid, payroll_event_type="manual_credit").all()


def test_PROD_PAY_001__proposes_exactly_the_unpaid_time(app):
    classroom = initialize("chemistry_p1", app)
    working, finished = _incident(classroom)

    proposal = build_class_correction_proposal(classroom.class_id)

    (row,) = proposal.rows
    assert row.seat_id == working
    assert row.status == PROPOSED
    assert row.unpaid_seconds == 20 * 60
    assert row.amount == _pay_for(classroom.class_id, 20)
    assert finished not in {r.seat_id for r in proposal.rows}


def test_PROD_PAY_001__approval_posts_a_system_calculated_credit_under_the_teacher(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    working, finished = _incident(classroom)

    paid = _approve(classroom, {working, finished})

    assert paid == [working]
    (event,) = _corrections(cid)
    assert event.target_seat_id == working
    assert event.actor_seat_id == classroom.teacher_seat_id
    assert event.mechanism == "SYSTEM"
    assert event.idempotency_key == correction_key(PROD_PAY_001, cid, working)
    assert event.summary_json["incident"] == "PROD-PAY-001"
    # Provenance: the class's payroll setting that priced the corrected run.
    assert event.policy_uuid == first_payroll_setting(cid).policy_uuid
    (credit,) = Transaction.query.filter_by(
        class_id=cid, seat_id=working, type="manual_payment"
    ).all()
    assert Decimal(credit.amount) == _pay_for(cid, 20)
    assert credit.description == PROD_PAY_001.ledger_description

    # The student now shows as corrected, and a second approval pays nobody.
    (row,) = build_class_correction_proposal(cid).rows
    assert row.status == CORRECTED
    assert _approve(classroom, {working}) == []
    assert len(_corrections(cid)) == 1


def test_PROD_PAY_001__an_excluded_student_is_not_paid(app):
    classroom = initialize("chemistry_p1", app)
    working, _finished = _incident(classroom)

    assert _approve(classroom, set()) == []
    assert _corrections(classroom.class_id) == []
    (row,) = build_class_correction_proposal(classroom.class_id).rows
    assert row.seat_id == working and row.status == PROPOSED


def test_PROD_PAY_001__a_replay_that_disagrees_with_the_ledger_needs_review(app):
    """If the replay cannot reproduce what was paid, the amount is not trusted."""
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    working, _finished = _incident(classroom, underpaid_first_run=_pay_for(cid, 31))

    (row,) = build_class_correction_proposal(cid).rows
    assert row.seat_id == working
    assert row.status == NEEDS_REVIEW
    assert _approve(classroom, {working}) == []
    assert _corrections(cid) == []


def test_PROD_PAY_001__review_page_is_a_pure_read_and_shows_the_banner(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    _incident(classroom)
    events_before = PayrollEvent.query.count()
    ledger_before = Transaction.query.count()

    page = client.get("/admin/payroll/correction")
    payroll_page = client.get("/admin/payroll")

    assert page.status_code == 200
    assert b"Payroll correction" in page.data
    assert b"Your teacher account will be recorded as the approving actor" in page.data
    assert payroll_page.status_code == 200
    assert b"Payroll correction needs your review" in payroll_page.data
    assert PayrollEvent.query.count() == events_before
    assert Transaction.query.count() == ledger_before


def test_PROD_PAY_001__submitted_amounts_are_ignored(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = classroom.class_id
    enable_class_feature(class_id=cid, feature="payroll")
    working, _finished = _incident(classroom)

    response = client.post(
        "/admin/payroll/correction",
        data={"seat_ids": [str(working)], "amount": "9999.00", f"amount_{working}": "9999.00"},
    )

    assert response.status_code == 302
    (credit,) = Transaction.query.filter_by(class_id=cid, seat_id=working, type="manual_payment").all()
    assert Decimal(credit.amount) == _pay_for(cid, 20)
    assert b"Payroll correction needs your review" not in client.get("/admin/payroll").data


def test_PROD_PAY_001__a_teacher_cannot_correct_another_class(client):
    app = client.application
    other = initialize("ap_csp_p3", app)
    other_working, _ = _incident(other)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")

    client.post("/admin/payroll/correction", data={"seat_ids": [str(other_working)]})

    assert _corrections(other.class_id) == []
    (row,) = build_class_correction_proposal(other.class_id).rows
    assert row.status == PROPOSED


def test_PROD_PAY_001__a_student_cannot_open_the_review(client):
    app = client.application
    initialize_as_student("chemistry_p1", client, app)

    response = client.get("/admin/payroll/correction")

    assert response.status_code in (302, 403)


def test_PROD_PAY_001__closed_incident_hides_the_review(client, monkeypatch):
    app = client.application
    initialize_as_teacher("chemistry_p1", client, app)
    monkeypatch.setattr(admin_routes, "incident_is_open", lambda incident: False)

    assert client.get("/admin/payroll/correction").status_code == 404


def test_PROD_PAY_001__overlapping_approvals_skip_the_student_already_paid(app, monkeypatch):
    """Two approvals at once plan the same students; the later one skips, not fails."""
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    working, _finished = _incident(classroom)
    second = classroom.students[2].seat.id
    _attendance(classroom, second, ("active", _at(0)), ("inactive", _at(50)))
    _legacy_run(classroom, second, _at(30), _pay_for(cid, 30))
    _legacy_run(classroom, second, _at(60), Decimal("0.00"))

    # The other request planned both students before this one posted either.
    stale_plan = corrections_module.plan_class_corrections(
        ctx=_teacher_ctx(classroom), seat_ids={working, second}
    )
    assert _approve(classroom, {working}) == [working]
    monkeypatch.setattr(admin_routes, "plan_class_corrections", lambda **_kwargs: stale_plan)

    assert _approve(classroom, {working, second}) == [second]
    assert sorted(e.target_seat_id for e in _corrections(cid)) == sorted([working, second])


def test_PROD_PAY_001__banner_check_is_cached_until_an_approval(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    working, _finished = _incident(classroom)
    builds = []
    real_build = corrections_module.build_class_correction_proposal

    def counting_build(class_id, **kwargs):
        builds.append(class_id)
        return real_build(class_id, **kwargs)

    monkeypatch.setattr(corrections_module, "build_class_correction_proposal", counting_build)

    assert corrections_module.class_has_pending_correction(cid) is True
    assert corrections_module.class_has_pending_correction(cid) is True
    assert len(builds) == 1

    _approve(classroom, {working})

    assert corrections_module.class_has_pending_correction(cid) is False


def test_PROD_PAY_001__results_are_unchanged_when_the_setting_predates_the_runs(app):
    """Production's shape: each class has exactly one payroll setting, recorded
    before the incident's runs (2026-09-28). Resolving the rate per run through
    the effective-dated resolver must give the amount the single rate gave."""
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    cid = classroom.class_id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"setting:{cid}"):
        # $1.50/minute, the production rate, in force from before the first run.
        append_payroll_setting(
            class_id=cid,
            settings_data={
                "pay_rate": Decimal("1.5"), "payroll_frequency_days": 14,
                "pay_schedule_type": "biweekly", "rounding_mode": "up",
            },
            effective_date=T0 - timedelta(hours=1), created_at=T0 - timedelta(hours=1),
        )
    (setting,) = payroll_setting_history(cid)

    working, finished = _incident(classroom)
    (row,) = build_class_correction_proposal(cid).rows

    assert row.seat_id == working and row.status == PROPOSED
    assert row.unpaid_seconds == 20 * 60
    assert row.amount == Decimal("30.00")  # 20 minutes at $1.50
    assert _approve(classroom, {working, finished}) == [working]
    (event,) = _corrections(cid)
    assert event.policy_uuid == setting.policy_uuid
