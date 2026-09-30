"""Payroll schedule rules (operator rulings 2026-09-30).

* Every setting anchors a schedule: a save without a first pay date is refused
  and nothing is recorded; the database refuses a row without one.
* The schedule is weekly, biweekly or monthly; anything else is refused by the
  route, the service and the database.
* Pay frequency is derived from the schedule type through the anchored
  recurrence (SPEC-TIME-001 §IX.12), never stored as a number of days: the
  economy page shows the cadence and the real length of the current period, so
  a February period (28 days) differs from a March one (31).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollSettings
from app.services.payroll.settings import append_payroll_setting, payroll_setting_history
from tests.dom.prod.test_payroll_change_governs_next_cycle import _clock, _login, _utc
from tests.helpers.class_domain import (
    enable_class_feature,
    update_expected_weekly_hours,
    update_payroll_settings,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

DEC_20 = _utc(2026, 12, 20, 18, 0)   # 10:00 PST
FEB_15 = _utc(2027, 2, 15, 18, 0)
MAR_15 = _utc(2027, 3, 15, 17, 0)    # 10:00 PDT


def _flashes(client):
    with client.session_transaction() as sess:
        return sess.pop("_flashes", [])


def test_a_save_without_a_first_pay_date_is_refused_and_nothing_is_recorded(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    with _clock(monkeypatch, DEC_20):
        _login(client, classroom, DEC_20)
        response = update_payroll_settings(
            client, settings_mode="simple", simple_pay_rate="15.00", simple_frequency="monthly",
        )

    assert response.status_code == 302
    assert ("error", "Choose the first payday. Payroll settings need a first pay date.") in _flashes(client)
    assert payroll_setting_history(classroom.class_id) == []


@pytest.mark.parametrize("schedule", ["daily", "custom", "fortnightly"])
def test_a_schedule_other_than_weekly_biweekly_or_monthly_is_refused(client, app, monkeypatch, schedule):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    with _clock(monkeypatch, DEC_20):
        _login(client, classroom, DEC_20)
        update_payroll_settings(
            client, settings_mode="advanced", adv_pay_amount="0.25", adv_time_unit="minutes",
            adv_pay_schedule=schedule, adv_custom_schedule_value="10",
            adv_first_pay_date="2027-01-01",
        )

    assert any(category == "error" for category, _ in _flashes(client))
    assert payroll_setting_history(classroom.class_id) == []


@pytest.mark.parametrize("schedule", ["weekly", "biweekly", "monthly"])
def test_saving_a_named_schedule_stores_only_the_schedule_and_its_anchor(client, app, monkeypatch, schedule):
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    with _clock(monkeypatch, DEC_20):
        _login(client, classroom, DEC_20)
        update_payroll_settings(
            client, settings_mode="simple", simple_pay_rate="15.00",
            simple_frequency=schedule, simple_first_pay_date="2027-01-01",
        )

    (row,) = payroll_setting_history(classroom.class_id)
    assert row.pay_schedule_type == schedule
    assert row.first_pay_date == _utc(2027, 1, 1, 8, 0)  # 00:00 PST
    # No day count exists to store (DOM-POL-001A §V.F).
    assert not hasattr(row, "payroll_frequency_days")


def test_the_service_refuses_a_missing_anchor_or_an_unsupported_schedule(app):
    classroom = initialize("chemistry_p1", app, with_payroll_settings=False)
    base = {"pay_rate": Decimal("1"), "pay_schedule_type": "monthly", "rounding_mode": "down"}
    for data, message in (
        (base, "first pay date"),
        ({**base, "first_pay_date": DEC_20, "pay_schedule_type": "daily"}, "weekly, biweekly or monthly"),
    ):
        with pytest.raises(ValueError, match=message):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"bad:{uuid4()}"):
                append_payroll_setting(
                    class_id=classroom.class_id, settings_data=data,
                    effective_date=DEC_20, created_at=DEC_20,
                )
        db.session.rollback()


@pytest.mark.parametrize("field,value,constraint", [
    ("first_pay_date", None, "first_pay_date"),
    ("pay_schedule_type", "custom", "ck_payroll_settings_schedule_type"),
])
def test_the_database_refuses_a_row_without_an_anchor_or_with_an_unsupported_schedule(app, field, value, constraint):
    classroom = initialize("chemistry_p1", app, with_payroll_settings=False)
    row = dict(
        class_id=classroom.class_id, pay_rate=Decimal("1"), pay_schedule_type="monthly",
        rounding_mode="down", first_pay_date=DEC_20, effective_date=DEC_20, created_at=DEC_20,
    )
    row[field] = value
    with pytest.raises(IntegrityError, match=constraint):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"db:{uuid4()}"):
            db.session.add(PayrollSettings(**row))
            db.session.flush()
    db.session.rollback()


def test_economy_page_shows_the_cadence_and_the_real_period_length(client, app, monkeypatch):
    """Monthly anchored on Jan 1: the February period is 28 days, March's 31.
    The page never states a month as 30 days."""
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    with _clock(monkeypatch, DEC_20):
        _login(client, classroom, DEC_20)
        update_payroll_settings(
            client, settings_mode="simple", simple_pay_rate="60.00",
            simple_frequency="monthly", simple_first_pay_date="2027-01-01",
        )
        update_expected_weekly_hours(client, "5")

    pages = {}
    for label, instant in (("feb", FEB_15), ("mar", MAR_15)):
        with _clock(monkeypatch, instant):
            _login(client, classroom, instant)
            response = client.get("/admin/economic-engine")
            assert response.status_code == 200
            pages[label] = response.get_data(as_text=True)

    assert "Payroll schedule: monthly; the current pay period is 28 days (Feb 01 to Mar 01)" in pages["feb"]
    assert "Payroll schedule: monthly; the current pay period is 31 days (Mar 01 to Apr 01)" in pages["mar"]
    assert "30 days" not in pages["feb"] + pages["mar"]
