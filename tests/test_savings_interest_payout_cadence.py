"""Savings interest pays at the cadence the teacher configured.

The payout was keyed by calendar month while its amount was one payout window,
so a class configured for weekly payout earned one week's interest per month:
the first hourly tick of each month paid a week's worth on whatever balance
existed at that moment, and every later tick that month found the key taken.
The student projection meanwhile showed four or five payouts a month, so the
forecast and the runtime disagreed (SPEC-ECON-001 §10).

SPEC-ECON-001 §14.1 has the job resolve the class-local boundary and pay each
payout window that has closed since the last settled one; §8.2 gives each
window one idempotency boundary. These tests drive the real scheduled job,
``run_savings_interest_job``, with the resolver clock pinned, so every instant
is chosen and every class boundary is the class's own (SPEC-TIME-001 §11).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytz

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from app.scheduled_tasks import run_savings_interest_job
from app.services.economic_engine import (
    project_savings_balances,
    savings_interest_for_payout_period,
)
from app.services.ledger_balance_query_service import get_posted_balance
from app.services.ledger_posting_service import create_pending_transaction_idempotent
from app.utils import canonical_temporal_resolver as resolver_module
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction


RATE = Decimal("0.1733")  # the rate five production classes configure


@contextmanager
def _pinned_clock(monkeypatch, instant):
    """Pin the resolver clock, the only one application code reads."""

    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


def _local(tz_name, day, hour=0, minute=0):
    """A class-local wall-clock instant, expressed in UTC."""
    zone = pytz.timezone(tz_name)
    return zone.localize(datetime.combine(day, time(hour, minute))).astimezone(timezone.utc)


def _next_monday(tz_name, *, after_days=3):
    """A class-local Monday comfortably after now, so seats were claimed before it."""
    today = datetime.now(pytz.timezone(tz_name)).date() + timedelta(days=after_days)
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _first_of_next_month(tz_name, *, after_days=3):
    day = datetime.now(pytz.timezone(tz_name)).date() + timedelta(days=after_days)
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def _configure_interest(client, classroom, *, payout, compound="daily", calc="compound"):
    enable_class_feature(class_id=classroom.class_id, feature="banking")
    response = client.post(
        "/admin/banking/settings",
        data={
            "interest_apy": str(RATE * 100),
            "interest_calculation_type": calc,
            "compound_frequency": compound,
            "interest_payout_frequency": payout,
        },
    )
    assert response.status_code == 302, response.data


def _fund_savings(monkeypatch, app, classroom, seat, amount, at):
    with app.app_context(), _pinned_clock(monkeypatch, at):
        key = f"interest-cadence-fund:{uuid4().hex}"
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=key):
            create_ledger_idempotent_transaction(
                idempotency_key=key, seat_id=seat.id, class_id=classroom.class_id,
                amount=Decimal(amount), account_type="savings", type="payroll",
                description="Interest cadence funding",
            )


def _tick(monkeypatch, app, at):
    """One scheduled run of the real job at a chosen instant."""
    with app.app_context(), _pinned_clock(monkeypatch, at):
        run_savings_interest_job()


def _interest_rows(app, classroom, seat):
    with app.app_context():
        return (
            Transaction.query
            .filter(
                Transaction.seat_id == seat.id,
                Transaction.class_id == classroom.class_id,
                Transaction.type == "Interest",
            )
            .order_by(Transaction.timestamp.asc(), Transaction.id.asc())
            .all()
        )


def _run_ticks(monkeypatch, app, tz_name, first_day, last_day, hours=(1, 2)):
    day = first_day
    while day <= last_day:
        for hour in hours:
            _tick(monkeypatch, app, _local(tz_name, day, hour))
        day += timedelta(days=1)


def _one_window(balance, payout):
    return savings_interest_for_payout_period(
        posted_balance=balance, annual_rate=RATE, calculation_type="compound",
        compound_frequency="daily", payout_frequency=payout,
    )


# --------------------------------------------------------------------------- #
# Cadence                                                                      #
# --------------------------------------------------------------------------- #

def test_weekly_payout_pays_every_week_of_a_month(client, app, monkeypatch):
    """Weekly means once per class-local week — four or five times a month."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    month_start = _first_of_next_month(tz_name)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00",
                  _local(tz_name, month_start - timedelta(days=8), 12))

    _run_ticks(monkeypatch, app, tz_name, month_start - timedelta(days=7), next_month - timedelta(days=1))

    zone = pytz.timezone(tz_name)
    in_month = [
        row for row in _interest_rows(app, classroom, seat)
        if month_start <= row.timestamp.astimezone(zone).date() < next_month
    ]
    mondays = sum(
        1 for offset in range((next_month - month_start).days)
        if (month_start + timedelta(days=offset)).weekday() == 0
    )
    assert mondays in (4, 5)
    assert len(in_month) == mondays, (
        f"weekly payout paid {len(in_month)} time(s) in a month with {mondays} week closes"
    )


def test_monthly_payout_pays_once_a_month(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly")

    month_start = _first_of_next_month(tz_name)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, month_start, 0, 30))

    _run_ticks(monkeypatch, app, tz_name, month_start, next_month + timedelta(days=2))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 1
    assert rows[0].idempotency_key.endswith(f":monthly:{month_start:%Y-%m}")
    assert rows[0].description == "Monthly Savings Interest"
    assert rows[0].amount == _one_window(Decimal("1000.00"), "monthly")


def test_nothing_is_paid_before_the_window_closes(client, app, monkeypatch):
    """A window is paid once it has closed (§14.1), not at the first tick in it."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 9))

    _run_ticks(monkeypatch, app, tz_name, monday, monday + timedelta(days=6), hours=(10, 23))
    assert _interest_rows(app, classroom, seat) == []

    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 0, 30))
    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 1
    assert rows[0].idempotency_key.endswith(f":weekly:{monday.isoformat()}")
    assert rows[0].amount == _one_window(Decimal("1000.00"), "weekly")


def test_hourly_ticks_pay_a_window_once(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 9))

    _tick(monkeypatch, app, _local(tz_name, monday, 10))  # settles the deposit
    close = monday + timedelta(days=7)
    for hour in range(0, 24):
        _tick(monkeypatch, app, _local(tz_name, close, hour, 15))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 1
    assert rows[0].status == TransactionStatus.POSTED


def test_base_is_the_posted_balance_when_the_window_closed(client, app, monkeypatch):
    """Money posted after the close belongs to the next window, not this one."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    close = monday + timedelta(days=7)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 9))
    _tick(monkeypatch, app, _local(tz_name, monday, 10))  # settles the deposit
    # Deposited after the window closed but before the first tick that pays it.
    _fund_savings(monkeypatch, app, classroom, seat, "500.00", _local(tz_name, close, 0, 5))
    _tick(monkeypatch, app, _local(tz_name, close, 0, 10))
    _tick(monkeypatch, app, _local(tz_name, close, 1, 10))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [_one_window(Decimal("1000.00"), "weekly")]


# --------------------------------------------------------------------------- #
# Class time                                                                   #
# --------------------------------------------------------------------------- #

def test_weekly_windows_close_at_class_local_monday_midnight(client, app, monkeypatch):
    """Tokyo's Monday midnight is Sunday 15:00 UTC; a UTC calendar would miss it."""
    classroom = initialize_as_teacher("tz_tokyo_p1", client, app)
    tz_name = classroom.economy.class_timezone
    assert tz_name == "Asia/Tokyo"
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    close = monday + timedelta(days=7)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 9))
    _tick(monkeypatch, app, _local(tz_name, monday, 10))

    # 23:30 Sunday in Tokyo is still inside the window.
    _tick(monkeypatch, app, _local(tz_name, close - timedelta(days=1), 23, 30))
    assert _interest_rows(app, classroom, seat) == []

    # 00:30 Monday in Tokyo — a Sunday on the UTC calendar — closes it.
    first_after_close = _local(tz_name, close, 0, 30)
    assert first_after_close.weekday() == 6  # Sunday in UTC
    _tick(monkeypatch, app, first_after_close)
    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 1
    assert rows[0].idempotency_key.endswith(f":weekly:{monday.isoformat()}")


def test_monthly_windows_close_at_class_local_month_end(client, app, monkeypatch):
    classroom = initialize_as_teacher("tz_tokyo_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly")

    month_start = _first_of_next_month(tz_name)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, month_start, 9))
    _tick(monkeypatch, app, _local(tz_name, month_start, 10))

    _tick(monkeypatch, app, _local(tz_name, next_month - timedelta(days=1), 23, 30))
    assert _interest_rows(app, classroom, seat) == []

    # 00:30 on the 1st in Tokyo is still the previous month in UTC.
    _tick(monkeypatch, app, _local(tz_name, next_month, 0, 30))
    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 1
    assert rows[0].idempotency_key.endswith(f":monthly:{month_start:%Y-%m}")


# --------------------------------------------------------------------------- #
# Projection agreement (SPEC-ECON-001 §10)                                     #
# --------------------------------------------------------------------------- #

def test_weekly_runtime_matches_the_projection_over_a_month(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _run_ticks(monkeypatch, app, tz_name, monday, monday + timedelta(days=28))

    projection = project_savings_balances(
        posted_balance=Decimal("1000.00"), annual_rate=RATE, calculation_type="compound",
        compound_frequency="daily", payout_frequency="weekly", months=1,
    )
    assert len(_interest_rows(app, classroom, seat)) == 4
    with app.app_context():
        assert get_posted_balance(seat.id, classroom.class_id, "savings") == projection[1]


def test_monthly_runtime_matches_the_projection_over_two_months(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly", compound="weekly")

    month_start = _first_of_next_month(tz_name)
    month_two = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_three = (month_two.replace(day=28) + timedelta(days=4)).replace(day=1)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, month_start, 9))
    _tick(monkeypatch, app, _local(tz_name, month_start, 10))  # settles the deposit
    for day in (month_two, month_three):
        _tick(monkeypatch, app, _local(tz_name, day, 1))
        _tick(monkeypatch, app, _local(tz_name, day, 2))

    projection = project_savings_balances(
        posted_balance=Decimal("1000.00"), annual_rate=RATE, calculation_type="compound",
        compound_frequency="weekly", payout_frequency="monthly", months=2,
    )
    assert len(_interest_rows(app, classroom, seat)) == 2
    with app.app_context():
        assert get_posted_balance(seat.id, classroom.class_id, "savings") == projection[2]


# --------------------------------------------------------------------------- #
# Transition from month-keyed payouts                                          #
# --------------------------------------------------------------------------- #

def test_a_window_paid_under_the_month_key_is_not_paid_again(client, app, monkeypatch):
    """Production paid one week of interest keyed ``:YYYY-MM`` inside a week.

    That row is the payment for the configured-cadence window it was posted in;
    the window-keyed job must not pay that window a second time, and must pay
    the next one.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 9))
    legacy_at = _local(tz_name, monday + timedelta(days=1), 10)
    with app.app_context(), _pinned_clock(monkeypatch, legacy_at):
        with FEATContext("FEAT-LED-001", idempotency_key=f"legacy:{uuid4().hex}"):
            create_pending_transaction_idempotent(
                idempotency_key=(
                    f"savings-interest:{classroom.class_id}:{seat.id}:{legacy_at:%Y-%m}"
                ),
                seat_id=seat.id, class_id=classroom.class_id, target_seat_id=seat.id,
                actor_seat_id=seat.id, mechanism="self", amount=Decimal("3.34"),
                account_type="savings", type="Interest",
                description="Monthly Savings Interest",
            )

    _run_ticks(monkeypatch, app, tz_name, monday + timedelta(days=2), monday + timedelta(days=14))

    keys = [row.idempotency_key for row in _interest_rows(app, classroom, seat)]
    assert keys == [
        f"savings-interest:{classroom.class_id}:{seat.id}:{legacy_at:%Y-%m}",
        f"savings-interest:{classroom.class_id}:{seat.id}:weekly:{(monday + timedelta(days=7)).isoformat()}",
    ]


# --------------------------------------------------------------------------- #
# Class isolation                                                              #
# --------------------------------------------------------------------------- #

def test_two_classes_pay_on_their_own_cadences(client, app, monkeypatch):
    weekly_class = initialize_as_teacher("chemistry_p1", client, app)
    _configure_interest(client, weekly_class, payout="weekly")
    monthly_class = initialize_as_teacher("ap_csp_p3", client, app)
    _configure_interest(client, monthly_class, payout="monthly")

    tz_name = weekly_class.economy.class_timezone
    assert monthly_class.economy.class_timezone == tz_name
    weekly_seat = weekly_class.students[0].seat
    monthly_seat = monthly_class.students[0].seat

    month_start = _first_of_next_month(tz_name)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    for classroom, seat in ((weekly_class, weekly_seat), (monthly_class, monthly_seat)):
        _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, month_start, 0, 30))

    _run_ticks(monkeypatch, app, tz_name, month_start, next_month)

    weekly_rows = _interest_rows(app, weekly_class, weekly_seat)
    monthly_rows = _interest_rows(app, monthly_class, monthly_seat)
    assert len(weekly_rows) >= 4
    assert all(":weekly:" in row.idempotency_key for row in weekly_rows)
    assert all(row.idempotency_key.startswith(f"savings-interest:{weekly_class.class_id}:") for row in weekly_rows)
    assert len(monthly_rows) == 1
    assert monthly_rows[0].idempotency_key == (
        f"savings-interest:{monthly_class.class_id}:{monthly_seat.id}:monthly:{month_start:%Y-%m}"
    )
