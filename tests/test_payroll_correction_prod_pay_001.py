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
import json
import os
import subprocess
import sys
from uuid import UUID

import pytest
from flask_migrate import upgrade
from decimal import Decimal

from app.extensions import db
from app.models import ClassEconomy, IdentityProfile, PayrollEvent, Seat, Transaction, User
from app.routes import admin as admin_routes
from app.services.context_resolver import CanonicalContext
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
    first_payroll_setting,
    pay_rate_per_second,
    payroll_setting_history,
)
from tests.helpers.canonical_classroom import ProvisionedClassroom, ProvisionedStudent, login_student, login_teacher
from tests.helpers.class_domain import enable_class_feature

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


@pytest.fixture(autouse=True)
def historical_incident_sources(app, request, tmp_path):
    """Create genuine predecessor inputs, then migrate forward without signing them."""
    from tests.dom.prod.test_historical_v1_assessment import PREDECESSOR, REPOSITORY
    assert db.engine.url.drivername.startswith("postgresql")
    assert "test" in (db.engine.url.database or "")
    source = tmp_path / "predecessor"
    source.mkdir()
    archive = tmp_path / "predecessor.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", PREDECESSOR], cwd=REPOSITORY,
                       stdout=stream, check=True)
    subprocess.run(["tar", "-xf", str(archive), "-C", str(source)], check=True)
    db.session.remove()
    environment = dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"],
                       PYTHONPATH=str(source), INCIDENT_FIXTURE_MODE=getattr(request, "param", "normal"))
    created = subprocess.run([sys.executable, "-c", PREDECESSOR_INCIDENT], cwd=source,
                             env=environment, text=True, capture_output=True, timeout=90)
    assert created.returncode == 0, created.stdout[-4000:] + created.stderr[-4000:]
    records = json.loads(next(line.partition("=")[2] for line in created.stdout.splitlines()
                             if line.startswith("INCIDENT_SOURCES=")))
    upgrade()
    classrooms = {}
    for record in records:
        students = []
        for student in record["students"]:
            user = db.session.get(User, UUID(student.pop("user_id")))
            seat = db.session.get(Seat, student.pop("seat_id"))
            profile = db.session.get(IdentityProfile, student.pop("profile_id"))
            students.append(ProvisionedStudent(user=user, seat=seat, profile=profile,
                user_id=user.id, seat_id=seat.id, **student))
        teacher = db.session.get(User, UUID(record["teacher_user_id"]))
        classrooms[record["key"]] = ProvisionedClassroom(
            economy=db.session.get(ClassEconomy, record["class_id"]),
            class_id=record["class_id"], teacher_user=teacher,
            teacher_seat=db.session.get(Seat, record["teacher_seat_id"]),
            teacher_user_id=teacher.id, teacher_seat_id=record["teacher_seat_id"],
            students=students,
        )
        for credit in record["credits"]:
            row = db.session.get(Transaction, credit["id"])
            assert [str(row.amount), row.posting_sequence, row.lineage_event_id,
                    row.lineage_token, row.lineage_version] == credit["evidence"]
        assert all(row.lineage_event_id is None for row in PayrollEvent.query.filter_by(
            class_id=record["class_id"]).all())
    yield classrooms


def _incident(classroom, *, underpaid_first_run=None):
    # All inputs were recorded under predecessor rules before the forward upgrade.
    # This function resolves their stable seats, never retrofits current evidence.
    working = classroom.students[0].seat.id
    if underpaid_first_run is not None:
        original = Transaction.query.filter_by(class_id=classroom.class_id,
            seat_id=working, type="payroll").one()
        assert original.amount == underpaid_first_run
    return working, classroom.students[1].seat.id


PREDECESSOR_INCIDENT = r"""
import json, os
from sqlalchemy import text
from flask_migrate import upgrade
from app import app, db
from app.models import Transaction
from app.feats.base import FEATContext
from app.services.payroll.settings import append_payroll_setting
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.canonical_classroom import provision_classroom
from tests.test_payroll_correction_prod_pay_001 import _incident, _attendance, _legacy_run, _at, _pay_for, T0
from datetime import timedelta
from decimal import Decimal
with app.app_context():
    assert 'test' in db.engine.url.database
    with db.engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    upgrade()
    mode = os.environ['INCIDENT_FIXTURE_MODE']
    keys = ['ap_csp_p3', 'chemistry_p1'] if mode == 'foreign_class' else ['chemistry_p1']
    records = []
    for key in keys:
        custom_setting = mode == 'prior_setting'
        classroom = provision_classroom(key, with_payroll_settings=not custom_setting)
        if custom_setting:
            with FEATContext('FEAT-CLASS-005', idempotency_key='incident:original-setting'):
                append_payroll_setting(class_id=classroom.class_id,
                    settings_data={'pay_rate': Decimal('1.5'), 'first_pay_date': T0-timedelta(hours=1),
                                   'pay_schedule_type': 'biweekly'},
                    effective_date=T0-timedelta(hours=1), created_at=T0-timedelta(hours=1))
        _incident(classroom, underpaid_first_run=_pay_for(classroom.class_id, 31)
                  if mode == 'mismatch' else None)
        if mode == 'overlap':
            second = classroom.students[2].seat.id
            _attendance(classroom, second, ('active', _at(0)), ('inactive', _at(50)))
            _legacy_run(classroom, second, _at(30), _pay_for(classroom.class_id, 30))
            _legacy_run(classroom, second, _at(60), Decimal('0.00'))
        # The historical writer assigns sequences on lawful reconciliation;
        # settle through that original command before the current forward gate.
        with FEATContext('FEAT-LED-003', idempotency_key='incident:original-reconcile:' + key):
            for student in classroom.students:
                settle_balances(student.seat.id, classroom.class_id)
        students = []
        for student in classroom.students:
            students.append({name: getattr(student, name) for name in
                ('user_id','seat_id','first_name','last_name','chosen_word','username','pin','passphrase')} |
                {'profile_id': student.profile.id})
        records.append(dict(key=key, class_id=classroom.class_id,
            teacher_user_id=classroom.teacher_user_id, teacher_seat_id=classroom.teacher_seat_id,
            students=students, credits=[dict(id=row.id,
                evidence=[str(row.amount), row.posting_sequence, row.lineage_event_id,
                          row.lineage_token, row.lineage_version])
                for row in Transaction.query.filter_by(class_id=classroom.class_id).all()]))
    db.session.commit()
    print('INCIDENT_SOURCES=' + json.dumps(records, default=str))
"""


def _approve(classroom, seat_ids: set[int]) -> list[int]:
    """The route's approval step: plan in the service, post through FEAT-PROD-003."""
    return admin_routes._post_payroll_corrections(_teacher_ctx(classroom), seat_ids)


def _corrections(cid: str):
    return PayrollEvent.query.filter_by(class_id=cid, payroll_event_type="manual_credit").all()


def test_PROD_PAY_001__proposes_exactly_the_unpaid_time(app, historical_incident_sources):
    classroom = historical_incident_sources["chemistry_p1"]
    working, finished = _incident(classroom)

    proposal = build_class_correction_proposal(classroom.class_id)

    (row,) = proposal.rows
    assert row.seat_id == working
    assert row.status == PROPOSED
    assert row.unpaid_seconds == 20 * 60
    assert row.amount == _pay_for(classroom.class_id, 20)
    assert finished not in {r.seat_id for r in proposal.rows}


def test_PROD_PAY_001__approval_posts_a_system_calculated_credit_under_the_teacher(app, historical_incident_sources):
    classroom = historical_incident_sources["chemistry_p1"]
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


def test_PROD_PAY_001__an_excluded_student_is_not_paid(app, historical_incident_sources):
    classroom = historical_incident_sources["chemistry_p1"]
    working, _finished = _incident(classroom)

    assert _approve(classroom, set()) == []
    assert _corrections(classroom.class_id) == []
    (row,) = build_class_correction_proposal(classroom.class_id).rows
    assert row.seat_id == working and row.status == PROPOSED


@pytest.mark.parametrize("historical_incident_sources", ["mismatch"], indirect=True)
def test_PROD_PAY_001__a_replay_that_disagrees_with_the_ledger_needs_review(app, historical_incident_sources):
    """If the replay cannot reproduce what was paid, the amount is not trusted."""
    classroom = historical_incident_sources["chemistry_p1"]
    cid = classroom.class_id
    working, _finished = _incident(classroom, underpaid_first_run=_pay_for(cid, 31))

    (row,) = build_class_correction_proposal(cid).rows
    assert row.seat_id == working
    assert row.status == NEEDS_REVIEW
    assert _approve(classroom, {working}) == []
    assert _corrections(cid) == []


def test_PROD_PAY_001__review_page_is_a_pure_read_and_shows_the_banner(client, historical_incident_sources):
    app = client.application
    classroom = historical_incident_sources["chemistry_p1"]
    login_teacher(client, classroom)
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


def test_PROD_PAY_001__submitted_amounts_are_ignored(client, historical_incident_sources):
    app = client.application
    classroom = historical_incident_sources["chemistry_p1"]
    login_teacher(client, classroom)
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


@pytest.mark.parametrize("historical_incident_sources", ["foreign_class"], indirect=True)
def test_PROD_PAY_001__a_teacher_cannot_correct_another_class(client, historical_incident_sources):
    app = client.application
    other = historical_incident_sources["ap_csp_p3"]
    other_working, _ = _incident(other)
    classroom = historical_incident_sources["chemistry_p1"]
    login_teacher(client, classroom)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")

    client.post("/admin/payroll/correction", data={"seat_ids": [str(other_working)]})

    assert _corrections(other.class_id) == []
    (row,) = build_class_correction_proposal(other.class_id).rows
    assert row.status == PROPOSED


def test_PROD_PAY_001__a_student_cannot_open_the_review(client, historical_incident_sources):
    app = client.application
    login_student(client, historical_incident_sources["chemistry_p1"].students[0])

    response = client.get("/admin/payroll/correction")

    assert response.status_code in (302, 403)


def test_PROD_PAY_001__closed_incident_hides_the_review(client, monkeypatch, historical_incident_sources):
    app = client.application
    login_teacher(client, historical_incident_sources["chemistry_p1"])
    monkeypatch.setattr(admin_routes, "incident_is_open", lambda incident: False)

    assert client.get("/admin/payroll/correction").status_code == 404


@pytest.mark.parametrize("historical_incident_sources", ["overlap"], indirect=True)
def test_PROD_PAY_001__overlapping_approvals_skip_the_student_already_paid(app, monkeypatch, historical_incident_sources):
    """Two approvals at once plan the same students; the later one skips, not fails."""
    classroom = historical_incident_sources["chemistry_p1"]
    cid = classroom.class_id
    working, _finished = _incident(classroom)
    second = classroom.students[2].seat.id
    assert PayrollEvent.query.filter_by(class_id=cid, target_seat_id=second).count() == 2

    # The other request planned both students before this one posted either.
    stale_plan = corrections_module.plan_class_corrections(
        ctx=_teacher_ctx(classroom), seat_ids={working, second}
    )
    assert _approve(classroom, {working}) == [working]
    monkeypatch.setattr(admin_routes, "plan_class_corrections", lambda **_kwargs: stale_plan)

    assert _approve(classroom, {working, second}) == [second]
    assert sorted(e.target_seat_id for e in _corrections(cid)) == sorted([working, second])


def test_PROD_PAY_001__banner_check_is_cached_until_an_approval(app, monkeypatch, historical_incident_sources):
    classroom = historical_incident_sources["chemistry_p1"]
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


@pytest.mark.parametrize("historical_incident_sources", ["prior_setting"], indirect=True)
def test_PROD_PAY_001__results_are_unchanged_when_the_setting_predates_the_runs(app, historical_incident_sources):
    """Production's shape: each class has exactly one payroll setting, recorded
    before the incident's runs (2026-09-28). Resolving the rate per run through
    the effective-dated resolver must give the amount the single rate gave."""
    classroom = historical_incident_sources["chemistry_p1"]
    cid = classroom.class_id
    (setting,) = payroll_setting_history(cid)

    working, finished = _incident(classroom)
    (row,) = build_class_correction_proposal(cid).rows

    assert row.seat_id == working and row.status == PROPOSED
    assert row.unpaid_seconds == 20 * 60
    assert row.amount == Decimal("30.00")  # 20 minutes at $1.50
    assert _approve(classroom, {working, finished}) == [working]
    (event,) = _corrections(cid)
    assert event.policy_uuid == setting.policy_uuid
