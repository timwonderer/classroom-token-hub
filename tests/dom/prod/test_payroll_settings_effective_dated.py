"""Effective-dated payroll settings and the derived next payroll date.

Operator ruling 2026-09-30 (DOM-CLASS-003 §VII, DOM-POL-001 §VI.2,
DOM-PROD-001 §XV.3/§XV.5):

* saving settings appends a row; the first is in force at once, a later one at
  the next payroll date, and the latest save for a date wins;
* the next payroll date is derived from payroll_settings and SYSTEM payroll
  events only — a teacher's run and a SYSTEM manual credit never move it, and a
  late scheduled run does not drift it;
* a run spanning two settings records enough to reproduce its amount;
* payroll_settings and payroll_event refuse UPDATE and DELETE at the database,
  except while a class universe is being destroyed.

The clock is pinned as in test_payroll_change_governs_next_cycle.py.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_payroll_event
from app.models import PayrollEvent, PayrollSettings, Transaction
from app.scheduled_tasks import run_automatic_payroll_job
from app.services.context_resolver import CanonicalContext
from app.services.payroll.pricing import SUMMARY_PRICING_KEY, amount_from_summary
from app.services.payroll.schedule import (
    SCHEDULED_OCCURRENCE_KEY,
    derive_next_payroll_date,
    next_payroll_date,
)
from app.services.payroll.settings import (
    current_payroll_setting,
    payroll_setting_effective_at,
    payroll_setting_history,
    pending_payroll_settings,
)
from tests.dom.prod.test_payroll_change_governs_next_cycle import (
    AFTER,
    FIRST_PAY,
    MON,
    _clock,
    _login,
    _payroll_credits,
    _save_rate,
    _utc,
    _work,
)
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _teacher_run(client, classroom, monkeypatch, instant, token):
    with _clock(monkeypatch, instant):
        _login(client, classroom, instant)
        response = client.post("/admin/run_payroll", data={"idempotency_token": token})
        assert response.status_code == 302, response.get_data(as_text=True)


def _configured_class(client, app, monkeypatch):
    """A class whose setting in force has a schedule: first pay date Fri Oct 9,
    biweekly, $60/hour — the class's first setting, so in force at once."""
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    with _clock(monkeypatch, MON):
        _login(client, classroom, MON)
        _save_rate(client, "60.00")
    return classroom


def _events(classroom, **filters):
    return (
        PayrollEvent.query.filter_by(class_id=classroom.class_id, **filters)
        .order_by(PayrollEvent.recorded_at.asc(), PayrollEvent.id.asc())
        .all()
    )


# --------------------------------------------------------------------------- #
# Saving settings                                                              #
# --------------------------------------------------------------------------- #

def test_first_ever_payroll_setting_is_in_force_immediately(client, app, monkeypatch):
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    assert payroll_setting_history(classroom.class_id) == []

    with _clock(monkeypatch, MON):
        _login(client, classroom, MON)
        _save_rate(client, "60.00")

    (row,) = payroll_setting_history(classroom.class_id)
    assert row.effective_date == row.created_at == MON
    assert current_payroll_setting(classroom.class_id, as_of=MON) is row
    assert row.pay_rate == Decimal("1.00000000")


def test_a_save_during_an_open_cycle_takes_effect_on_the_next_payroll_date(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    in_force = current_payroll_setting(classroom.class_id, as_of=MON)

    later = MON + timedelta(hours=1)
    with _clock(monkeypatch, later):
        _login(client, classroom, later)
        _save_rate(client, "600.00")

    pending = pending_payroll_settings(classroom.class_id, as_of=later)
    assert [row.effective_date for row in pending] == [FIRST_PAY]
    assert current_payroll_setting(classroom.class_id, as_of=later) is in_force
    assert payroll_setting_effective_at(classroom.class_id, FIRST_PAY) is pending[0]


def test_two_saves_before_the_same_boundary_the_last_one_wins(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    for minutes, rate in ((60, "600.00"), (120, "120.00")):
        instant = MON + timedelta(minutes=minutes)
        with _clock(monkeypatch, instant):
            _login(client, classroom, instant)
            _save_rate(client, rate)

    history = payroll_setting_history(classroom.class_id)
    # Both saves are kept, both dated to the boundary; neither was rewritten.
    assert [row.effective_date for row in history[:2]] == [FIRST_PAY, FIRST_PAY]
    assert payroll_setting_effective_at(classroom.class_id, FIRST_PAY).pay_rate == Decimal("2.00000000")
    (pending,) = pending_payroll_settings(classroom.class_id, as_of=MON + timedelta(hours=3))
    assert pending.pay_rate == Decimal("2.00000000")


def test_payroll_page_discloses_the_setting_in_force_and_the_pending_one(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    later = MON + timedelta(hours=1)
    with _clock(monkeypatch, later):
        _login(client, classroom, later)
        _save_rate(client, "600.00")
        page = client.get("/admin/payroll").get_data(as_text=True)

    assert "In effect now:" in page and "$1.00/minute ($60.00/hour)" in page
    assert 'data-testid="pending-payroll-setting"' in page
    assert "$10.00/minute ($600.00/hour)" in page


# --------------------------------------------------------------------------- #
# The derived next payroll date                                                #
# --------------------------------------------------------------------------- #

def test_derive_next_payroll_date_forms(app):
    """The three forms fall out of the anchored sequence (SPEC-TIME-001 §IX.12).
    FIRST_PAY is Fri Oct 9 2026 00:00 PDT; the class is in Los Angeles."""
    cid = provision_classroom("chemistry_p1", with_payroll_settings=False).class_id

    def derive(last, schedule="biweekly", first=FIRST_PAY):
        return derive_next_payroll_date(
            class_id=cid, first_pay_date=first, pay_schedule_type=schedule,
            last_system_occurrence=last,
        )

    # 1. No SYSTEM run: first_pay_date, whether ahead or already due.
    assert derive(None) == FIRST_PAY
    # 2. The last SYSTEM run was the one on first_pay_date.
    assert derive(FIRST_PAY) == FIRST_PAY + timedelta(days=14)
    # 3. Any later SYSTEM run, across a DST change: local midnight is kept.
    assert derive(_utc(2026, 10, 23, 7, 0)) == _utc(2026, 11, 6, 8, 0)  # 00:00 PST after Nov 1
    # A late run's recorded instant (no occurrence recorded) still lands on the
    # anchored grid: the first boundary strictly after it.
    assert derive(_utc(2026, 10, 23, 9, 30)) == _utc(2026, 11, 6, 8, 0)
    # Monthly is a calendar month from the anchor, not 30 days.
    assert derive(FIRST_PAY, schedule="monthly") == _utc(2026, 11, 9, 8, 0)


def test_a_scheduled_run_advances_the_date_from_its_occurrence_without_drift(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    seat_id = classroom.students[0].seat.id
    _work(classroom, seat_id, MON + timedelta(minutes=5), 15)
    assert next_payroll_date(classroom.class_id, as_of=MON) == FIRST_PAY

    # The job runs 50 minutes late; the next date is counted from the occurrence.
    late = FIRST_PAY + timedelta(minutes=50)
    with _clock(monkeypatch, late):
        run_automatic_payroll_job()

    (event,) = _events(classroom, payroll_event_type="payroll")
    assert event.mechanism == "SYSTEM"
    assert event.summary_json[SCHEDULED_OCCURRENCE_KEY] == FIRST_PAY.isoformat()
    assert next_payroll_date(classroom.class_id, as_of=late) == FIRST_PAY + timedelta(days=14)


def test_a_teacher_run_does_not_move_the_next_payroll_date(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    seat_id = classroom.students[0].seat.id
    _work(classroom, seat_id, MON + timedelta(minutes=5), 15)

    _teacher_run(client, classroom, monkeypatch, MON + timedelta(minutes=30), "teacher")

    (event,) = _events(classroom, payroll_event_type="payroll")
    assert event.mechanism == "TEACHER"
    assert SCHEDULED_OCCURRENCE_KEY not in (event.summary_json or {})
    assert next_payroll_date(classroom.class_id, as_of=MON + timedelta(hours=1)) == FIRST_PAY


def test_a_system_manual_credit_does_not_move_the_next_payroll_date(client, app, monkeypatch):
    """PROD-PAY-001 corrections are manual credits recorded as SYSTEM; they must
    not be read as a scheduled payroll run."""
    classroom = _configured_class(client, app, monkeypatch)
    seat_id = classroom.students[0].seat.id
    ctx = CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id, actor_role="teacher",
    )
    instant = MON + timedelta(hours=1)
    with _clock(monkeypatch, instant):
        record_payroll_event(
            ctx=ctx, target_seat_id=seat_id, payroll_event_type="manual_credit",
            correlation_id=str(uuid4()), idempotency_key=f"credit:{uuid4()}",
            mechanism="SYSTEM", amount=Decimal("3.00"),
            summary_json={"description": "System-computed credit"},
        )

    (credit,) = _events(classroom, payroll_event_type="manual_credit")
    assert credit.mechanism == "SYSTEM"
    assert next_payroll_date(classroom.class_id, as_of=instant) == FIRST_PAY


# --------------------------------------------------------------------------- #
# Reproducibility across two settings                                          #
# --------------------------------------------------------------------------- #

def test_a_run_spanning_two_settings_is_reproducible_from_recorded_inputs(client, app, monkeypatch):
    classroom = _configured_class(client, app, monkeypatch)
    seat_id = classroom.students[0].seat.id
    _work(classroom, seat_id, MON + timedelta(minutes=5), 15)          # under $1/min
    with _clock(monkeypatch, MON + timedelta(minutes=30)):
        _login(client, classroom, MON + timedelta(minutes=30))
        _save_rate(client, "600.00")                                   # $10/min from Oct 9
    _work(classroom, seat_id, AFTER, 15)                               # under $10/min
    # No run happens over the boundary, so one teacher run settles both.
    with _clock(monkeypatch, AFTER + timedelta(minutes=30)):
        _login(client, classroom, AFTER + timedelta(minutes=30))
        response = client.post("/admin/run_payroll", data={"idempotency_token": "span"})
        assert response.status_code == 302

    (event,) = _events(classroom, payroll_event_type="payroll")
    pricing = event.summary_json[SUMMARY_PRICING_KEY]
    r1 = payroll_setting_effective_at(classroom.class_id, MON)
    r2 = payroll_setting_effective_at(classroom.class_id, FIRST_PAY)
    assert [(p["policy_uuid"], p["seconds"], p["pay_rate_per_minute"]) for p in pricing] == [
        (r1.policy_uuid, 900, "1.00000000"),
        (r2.policy_uuid, 900, "10.00000000"),
    ]
    # The latest-closing session's setting names the event.
    assert event.policy_uuid == r2.policy_uuid
    # Recomputed from the recorded inputs alone, it equals what was posted.
    assert amount_from_summary(pricing) == Decimal("165.00")
    assert _payroll_credits(classroom, seat_id) == [Decimal("165.00")]


# --------------------------------------------------------------------------- #
# FEAT-PROD-003 provenance                                                     #
# --------------------------------------------------------------------------- #

def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id, actor_role="teacher",
    )


def test_payroll_event_policy_is_resolved_by_pricing_not_supplied(app):
    classroom = provision_classroom("chemistry_p1")
    setting = current_payroll_setting(classroom.class_id)
    with pytest.raises(ValueError, match="caller-supplied policy_uuid"):
        record_payroll_event(
            ctx=_teacher_ctx(classroom), target_seat_id=classroom.students[0].seat.id,
            payroll_event_type="payroll", correlation_id=str(uuid4()),
            idempotency_key=f"p:{uuid4()}", mechanism="TEACHER",
            policy_uuid=setting.policy_uuid,
        )
    db.session.rollback()


def test_manual_credit_provenance_must_be_a_setting_of_the_class(app):
    classroom = provision_classroom("chemistry_p1")
    other = provision_classroom("ap_csp_p3")
    foreign = current_payroll_setting(other.class_id)
    with pytest.raises(ValueError, match="owned by the current class"):
        record_payroll_event(
            ctx=_teacher_ctx(classroom), target_seat_id=classroom.students[0].seat.id,
            payroll_event_type="manual_credit", correlation_id=str(uuid4()),
            idempotency_key=f"m:{uuid4()}", mechanism="SYSTEM",
            policy_uuid=foreign.policy_uuid, amount=Decimal("1.00"),
        )
    db.session.rollback()


# --------------------------------------------------------------------------- #
# Append-only at the database                                                  #
# --------------------------------------------------------------------------- #

def _refused(statement, params):
    with pytest.raises(DBAPIError, match="append-only"):
        db.session.execute(text(statement), params)
        db.session.flush()
    db.session.rollback()


def _seed_payroll_event(classroom):
    seat_id = classroom.students[0].seat.id
    record_payroll_event(
        ctx=_teacher_ctx(classroom), target_seat_id=seat_id,
        payroll_event_type="manual_credit", correlation_id=str(uuid4()),
        idempotency_key=f"seed:{uuid4()}", mechanism="TEACHER", amount=Decimal("1.00"),
        summary_json={"description": "seed"},
    )
    return PayrollEvent.query.filter_by(class_id=classroom.class_id).one()


def test_payroll_settings_update_is_refused_by_the_database(app):
    classroom = provision_classroom("chemistry_p1")
    row = current_payroll_setting(classroom.class_id)
    _refused("UPDATE payroll_settings SET pay_rate = 9 WHERE policy_uuid = :u", {"u": row.policy_uuid})


def test_payroll_settings_update_is_refused_by_the_orm(app):
    classroom = provision_classroom("chemistry_p1")
    row = current_payroll_setting(classroom.class_id)
    with pytest.raises(ValueError, match="append-only"):
        with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"edit:{uuid4()}"):
            row.pay_rate = Decimal("9")
            db.session.flush()
    db.session.rollback()


def test_payroll_settings_delete_is_refused_outside_class_destruction(app):
    classroom = provision_classroom("chemistry_p1")
    row = current_payroll_setting(classroom.class_id)
    _refused("DELETE FROM payroll_settings WHERE policy_uuid = :u", {"u": row.policy_uuid})


def test_payroll_event_update_and_delete_are_refused(app):
    classroom = provision_classroom("chemistry_p1")
    event = _seed_payroll_event(classroom)
    _refused("UPDATE payroll_event SET summary_json = '{}' WHERE id = :i", {"i": event.id})
    _refused("DELETE FROM payroll_event WHERE id = :i", {"i": event.id})


def test_class_universe_destruction_may_delete_payroll_rows(app):
    classroom = provision_classroom("chemistry_p1")
    event = _seed_payroll_event(classroom)
    row = current_payroll_setting(classroom.class_id)
    db.session.execute(text("SET LOCAL cth.class_universe_destroying = 'on'"))
    db.session.execute(text("DELETE FROM payroll_event WHERE id = :i"), {"i": event.id})
    db.session.execute(text("DELETE FROM payroll_settings WHERE policy_uuid = :u"), {"u": row.policy_uuid})
    db.session.rollback()
