"""Teacher pages evaluate and display class time — INV-ARC-015 §VII, §X.2.

Each test is placed in a class whose calendar day differs from UTC's at the
instant under test (Tokyo, UTC+9) or whose clocks change inside the interval
(Los Angeles), so a UTC shortcut produces a visibly different answer.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytz

import app.utils.canonical_temporal_resolver as resolver_module
from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollSettings
from app.scheduled_tasks import _advance_local_calendar_days
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@contextmanager
def _pinned_clock(monkeypatch, instant):
    """Pins the resolver's clock, the only one application code reads, so a row
    stamped by ``default=utc_now`` gets a chosen instant. Ledger rows cannot be
    re-dated afterwards (database immutability triggers)."""

    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


# --------------------------------------------------------------------------- #
# Banking transaction date filter                                              #
# --------------------------------------------------------------------------- #

# 08:00 on Sep 26 in Tokyo is 23:00 on Sep 25 in UTC.
TOKYO_MORNING = _utc(2026, 9, 25, 23, 0)


def _banking_page(client, day):
    return client.get(
        f"/admin/banking?start_date={day}&end_date={day}"
    ).get_data(as_text=True)


def test_INV_ARC_015__banking_date_filter_selects_the_class_day(client, app, monkeypatch):
    classroom = initialize_as_teacher("tz_tokyo_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="banking")
        with _pinned_clock(monkeypatch, TOKYO_MORNING):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"fund:{uuid4().hex}", seat_id=student.seat.id,
                    class_id=classroom.class_id, amount=Decimal("12.34"),
                    account_type="checking", type="payroll",
                    description="Tokyo morning deposit",
                )
        db.session.commit()

    assert "Tokyo morning deposit" in _banking_page(client, "2026-09-26")
    assert "Tokyo morning deposit" not in _banking_page(client, "2026-09-25")


# --------------------------------------------------------------------------- #
# Payroll page: next payroll date                                              #
# --------------------------------------------------------------------------- #

# 00:00 PST on Mon Mar 2 2026; US DST starts Sun Mar 8.
FIRST_PAY = _utc(2026, 3, 2, 8, 0)


def test_INV_ARC_015__payroll_page_shows_the_schedulers_next_run(client, app):
    """The page shows the cursor the automatic-payroll job runs on. It used to
    recompute first_pay + N × 14 × 24h, which after the March change lands at
    01:00 PDT — not a time the job ever runs payroll."""
    classroom = initialize_as_teacher("tz_pacific_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="payroll")
        # What the job stores after running the first payday (scheduled_tasks).
        next_run = _advance_local_calendar_days(
            FIRST_PAY, 14, SimpleNamespace(class_id=classroom.class_id)
        )
        assert next_run == _utc(2026, 3, 16, 7, 0)  # 00:00 PDT, Mar 16
        with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{classroom.class_id}"):
            settings = PayrollSettings.query.filter_by(class_id=classroom.class_id).first()
            if settings is None:
                settings = PayrollSettings(class_id=classroom.class_id, pay_rate=0.25)
                db.session.add(settings)
            settings.availability_state = "IN_USE"
            settings.next_payroll_date = next_run  # the mutable schedule cursor
        db.session.commit()

    page = client.get("/admin/payroll").get_data(as_text=True)
    assert "Mar 16, 2026, 12:00 AM PDT" in page


# --------------------------------------------------------------------------- #
# Economy analysis windows                                                     #
# --------------------------------------------------------------------------- #

def test_INV_ARC_015__economy_analysis_windows_are_class_calendar_periods(client, app):
    """The windows were Sunday-start weeks in a hardcoded America/Los_Angeles;
    they are the resolver's Monday-start week and calendar month, in class time."""
    classroom = initialize_as_teacher("tz_tokyo_p1", client, app)
    db.session.commit()

    response = client.post("/admin/api/economy/analyze", json={"expected_weekly_hours": 5})
    assert response.status_code == 200, response.get_data(as_text=True)
    schedule = response.get_json()["analysis_schedule"]

    assert schedule["refresh_timezone"] == "Asia/Tokyo"
    tokyo = pytz.timezone("Asia/Tokyo")
    week_start = datetime.fromisoformat(schedule["weekly_window_start_at"]).astimezone(tokyo)
    next_week = datetime.fromisoformat(schedule["next_weekly_refresh_at"]).astimezone(tokyo)
    month_start = datetime.fromisoformat(schedule["monthly_window_start_at"]).astimezone(tokyo)
    assert (week_start.weekday(), week_start.hour, week_start.minute) == (0, 0, 0)
    assert (next_week.date() - week_start.date()).days == 7 and next_week.hour == 0
    assert (month_start.day, month_start.hour) == (1, 0)


def test_class_day_bounds_are_the_class_days_own_midnights(app):
    """The helper the banking filter uses, pinned directly."""
    from app.routes.admin import _class_day_bounds_utc
    from tests.helpers.classroom_initializer import initialize

    classroom = initialize("tz_tokyo_p1", app)
    with app.app_context():
        assert _class_day_bounds_utc("2026-09-26", classroom.class_id) == (
            _utc(2026, 9, 25, 15, 0), _utc(2026, 9, 26, 15, 0),
        )
