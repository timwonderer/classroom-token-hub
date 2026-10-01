"""Savings interest pays at the cadence the teacher configured.

The payout was keyed by calendar month while its amount was one payout window,
so a class configured for weekly payout earned one week's interest per month:
the first hourly tick of each month paid a week's worth on whatever balance
existed at that moment, and every later tick that month found the key taken.
The student projection meanwhile showed four or five payouts a month, so the
forecast and the runtime disagreed (SPEC-ECON-001 §10).

SPEC-ECON-001 §14.1 has the job resolve the class-local boundary and pay each
payout window that has closed since the last settled one; §8.2 gives each
window one idempotency boundary; §9.2 (v1.1, operator ruling 2026-09-30) makes
the amount the daily balance method: each class-local day accrues on its
end-of-day posted balance, and the window's sum is credited, rounded once, when
the window closes. These tests drive the real scheduled job,
``run_savings_interest_job``, with the resolver clock pinned, so every instant
is chosen and every class boundary is the class's own (SPEC-TIME-001 §11).
"""

from __future__ import annotations

import calendar
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

import pytz

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from app.scheduled_tasks import run_savings_interest_job
from app.services.ledger_balance_query_service import get_posted_balance
from app.services.ledger_posting_service import create_pending_transaction_idempotent
from app.utils import canonical_temporal_resolver as resolver_module
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction


RATE = Decimal("0.1733")  # the rate five production classes configure
DAILY_RATE = RATE / Decimal("365")


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


def _cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _daily_compound(balance, days):
    """Hand formula: ``days`` days of daily compounding on a steady balance."""
    return _cents(Decimal(balance) * ((1 + DAILY_RATE) ** days - 1))


def _simple(balance, days):
    return _cents(Decimal(balance) * DAILY_RATE * days)


def _withdraw_savings(monkeypatch, app, classroom, seat, amount, at):
    _fund_savings(monkeypatch, app, classroom, seat, f"-{amount}", at)


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
    assert rows[0].amount == _daily_compound("1000.00", (next_month - month_start).days)


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
    assert rows[0].amount == _daily_compound("1000.00", 7)


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


def test_money_posted_after_the_close_belongs_to_the_next_window(client, app, monkeypatch):
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
    assert [row.amount for row in rows] == [_daily_compound("1000.00", 7)]


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

def _one_month_after(day):
    """Same class-local day next month, clamped (the forecast's month points)."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def _forecast(monkeypatch, app, classroom, seat, at, months):
    from app.services.ledger_interest_service import forecast_savings

    with app.app_context(), _pinned_clock(monkeypatch, at):
        return forecast_savings(seat.id, classroom.class_id, months=months)


def _posted_savings(app, classroom, seat):
    with app.app_context():
        return get_posted_balance(seat.id, classroom.class_id, "savings")


def test_weekly_runtime_matches_the_projection_over_a_month(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit
    forecast = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, monday, 1, 30), months=1)

    checkpoint = _one_month_after(monday)  # the forecast's "Month 1" point
    _run_ticks(monkeypatch, app, tz_name, monday + timedelta(days=1), checkpoint)

    rows = _interest_rows(app, classroom, seat)
    assert rows[0].amount == forecast.next_credit == _daily_compound("1000.00", 7)
    assert len(rows) == sum(
        1 for offset in range(1, (checkpoint - monday).days + 1)
        if (monday + timedelta(days=offset)).weekday() == 0
    )
    assert _posted_savings(app, classroom, seat) == forecast.series[1]


def test_monthly_runtime_matches_the_projection_over_two_months(client, app, monkeypatch):
    """Monthly payout with weekly compounding: accrued interest joins on Mondays."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly", compound="weekly")

    month_start = _first_of_next_month(tz_name)
    month_two = _one_month_after(month_start)
    month_three = _one_month_after(month_two)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, month_start, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, month_start, 1))  # settles the deposit
    forecast = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, month_start, 1, 30), months=2)

    _tick(monkeypatch, app, _local(tz_name, month_two, 1))
    _tick(monkeypatch, app, _local(tz_name, month_two, 2))
    assert _posted_savings(app, classroom, seat) == forecast.series[1]
    _tick(monkeypatch, app, _local(tz_name, month_three, 1))
    _tick(monkeypatch, app, _local(tz_name, month_three, 2))

    assert len(_interest_rows(app, classroom, seat)) == 2
    assert _posted_savings(app, classroom, seat) == forecast.series[2]
    # Weekly compounding inside the month earns less than daily, more than simple.
    days = (month_two - month_start).days
    first = _interest_rows(app, classroom, seat)[0].amount
    assert _simple("1000.00", days) <= first <= _daily_compound("1000.00", days)


# --------------------------------------------------------------------------- #
# Daily balance method (SPEC-ECON-001 §9.2, operator ruling 2026-09-30)        #
# --------------------------------------------------------------------------- #

def test_a_sunday_night_deposit_earns_one_day_not_a_week(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    sunday = monday + timedelta(days=6)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, sunday, 22))
    _tick(monkeypatch, app, _local(tz_name, sunday, 23))  # posts before the day ends
    _tick(monkeypatch, app, _local(tz_name, sunday + timedelta(days=1), 1))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [_daily_compound("1000.00", 1)]
    assert rows[0].amount == Decimal("0.47")


def test_a_last_day_withdrawal_still_earns_the_six_prior_days(client, app, monkeypatch):
    """Withdrawing everything on Sunday keeps Monday-Saturday's interest.

    Weeks are Monday-start (SPEC-TIME-001 §11), so Sunday is the last day and
    Monday through Saturday are the six days before it.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    sunday = monday + timedelta(days=6)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))
    _withdraw_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, sunday, 10))
    _tick(monkeypatch, app, _local(tz_name, sunday, 11))
    _tick(monkeypatch, app, _local(tz_name, sunday + timedelta(days=1), 1))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [_daily_compound("1000.00", 6)]
    assert rows[0].amount == Decimal("2.85")


def test_a_mid_week_deposit_earns_only_its_days(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    thursday = monday + timedelta(days=3)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, thursday, 9))
    _tick(monkeypatch, app, _local(tz_name, thursday, 10))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 1))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [_daily_compound("1000.00", 4)]
    assert rows[0].amount == Decimal("1.90")


def test_daily_compound_and_simple_weeks_match_hand_computed_values(client, app, monkeypatch):
    """1000 at 17.33% for 7 days: compound (1+r/365)^7-1 = 3.33, simple 7r/365 = 3.32."""
    compound_class = initialize_as_teacher("chemistry_p1", client, app)
    _configure_interest(client, compound_class, payout="weekly", compound="daily", calc="compound")
    simple_class = initialize_as_teacher("ap_csp_p3", client, app)
    _configure_interest(client, simple_class, payout="weekly", calc="simple")

    tz_name = compound_class.economy.class_timezone
    monday = _next_monday(tz_name)
    for classroom in (compound_class, simple_class):
        _fund_savings(monkeypatch, app, classroom, classroom.students[0].seat, "1000.00",
                      _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 1))

    compound_rows = _interest_rows(app, compound_class, compound_class.students[0].seat)
    simple_rows = _interest_rows(app, simple_class, simple_class.students[0].seat)
    assert [row.amount for row in compound_rows] == [Decimal("3.33")]
    assert [row.amount for row in simple_rows] == [Decimal("3.32")]


def test_monthly_window_accrues_only_the_days_money_was_held(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly")

    month_start = _first_of_next_month(tz_name)
    next_month = _one_month_after(month_start)
    deposit_day = month_start + timedelta(days=15)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, deposit_day, 9))
    _tick(monkeypatch, app, _local(tz_name, deposit_day, 10))
    _tick(monkeypatch, app, _local(tz_name, next_month, 1))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [
        _daily_compound("1000.00", (next_month - deposit_day).days)
    ]


def test_a_leap_year_february_accrues_29_days_at_rate_over_365(client, app, monkeypatch):
    """SPEC-ECON-001 §5.2 (v1.2): the daily rate is r/365 in every year, leap years too.

    February 2028 has 29 days. Each of them, February 29 included, earns
    ``balance × r / 365``: 1000 × 0.1733 × 29/365 = 13.77. A 366-day year would
    pay 13.73. The payout job and the forecast must agree on 13.77.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly", calc="simple")

    february = datetime(2028, 2, 1).date()
    march = datetime(2028, 3, 1).date()
    assert calendar.isleap(february.year)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, february, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, february, 1))  # settles the deposit
    forecast = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, february, 1, 30), months=1)
    _tick(monkeypatch, app, _local(tz_name, march, 1))

    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [_simple("1000.00", 29)] == [Decimal("13.77")]
    assert forecast.next_credit == Decimal("13.77")


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


# --------------------------------------------------------------------------- #
# Run-time independence and cadence changes                                    #
# --------------------------------------------------------------------------- #

def _compound_with_credits(principal, credits, days):
    """Hand replay: each earlier credit joins the base from its window's close."""
    return _daily_compound(Decimal(principal) + sum(credits, Decimal("0")), days)


def test_catch_up_after_a_scheduler_gap_pays_what_timely_ticks_pay(client, app, monkeypatch):
    """Windows 2..N of a catch-up include the credits for windows 1..N-1 (§14.1)."""
    timely = initialize_as_teacher("chemistry_p1", client, app)
    _configure_interest(client, timely, payout="weekly")
    gapped = initialize_as_teacher("ap_csp_p3", client, app)
    _configure_interest(client, gapped, payout="weekly")

    tz_name = timely.economy.class_timezone
    monday = _next_monday(tz_name)
    for classroom in (timely, gapped):
        _fund_savings(monkeypatch, app, classroom, classroom.students[0].seat, "100000.00",
                      _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles both deposits
    forecast = _forecast(monkeypatch, app, timely, timely.students[0].seat,
                         _local(tz_name, monday, 1, 30), months=1)

    # The timely class is ticked every Monday; the other only after three weeks.
    for week in (1, 2):
        with app.app_context(), _pinned_clock(monkeypatch, _local(tz_name, monday + timedelta(days=7 * week), 1)):
            from app.services.ledger_interest_service import apply_savings_interest
            from app.models import Seat
            with FEATContext("FEAT-LED-001", idempotency_key=f"timely:{uuid4().hex}"):
                apply_savings_interest(db.session.get(Seat, timely.students[0].seat.id))
        _tick_settlement_only(monkeypatch, app, _local(tz_name, monday + timedelta(days=7 * week), 2))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=21), 1))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=21), 2))

    timely_amounts = [row.amount for row in _interest_rows(app, timely, timely.students[0].seat)]
    gapped_amounts = [row.amount for row in _interest_rows(app, gapped, gapped.students[0].seat)]
    assert len(gapped_amounts) == 3
    assert gapped_amounts == timely_amounts
    expected = []
    for _ in range(3):
        expected.append(_compound_with_credits("100000.00", expected, 7))
    assert gapped_amounts == expected
    assert gapped_amounts[0] == forecast.next_credit


def _tick_settlement_only(monkeypatch, app, at):
    from app.scheduled_tasks import run_ledger_settlement_job

    with app.app_context(), _pinned_clock(monkeypatch, at):
        run_ledger_settlement_job()


def test_a_credit_compounds_from_the_next_window_whatever_settlement_does(client, app, monkeypatch):
    """A credit left pending for two days still earns from the next window's first day."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "100000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 1))  # credits week 1
    # No run on Monday or Tuesday: the week-1 credit settles only on Wednesday.
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=9), 10))
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=14), 1))

    first, second = [row.amount for row in _interest_rows(app, classroom, seat)]
    assert first == _daily_compound("100000.00", 7)
    assert second == _compound_with_credits("100000.00", [first], 7)


def _first_month_not_starting_monday(tz_name):
    month = _first_of_next_month(tz_name)
    while _one_month_after(month).weekday() == 0 or month.weekday() == 0:
        month = _one_month_after(month)
    return month


def test_weekly_to_monthly_pays_the_straddling_month_from_the_last_paid_week(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly")

    month_start = _first_month_not_starting_monday(tz_name)
    next_month = _one_month_after(month_start)
    first_monday = month_start + timedelta(days=(7 - month_start.weekday()) % 7)
    second_monday = first_monday + timedelta(days=7)
    _fund_savings(monkeypatch, app, classroom, seat, "100000.00", _local(tz_name, month_start, 0, 30))
    _run_ticks(monkeypatch, app, tz_name, month_start, second_monday)

    _configure_interest(client, classroom, payout="monthly")
    _run_ticks(monkeypatch, app, tz_name, second_monday + timedelta(days=1), next_month)

    rows = _interest_rows(app, classroom, seat)
    weekly = [row.amount for row in rows if ":weekly:" in row.idempotency_key]
    monthly = [row for row in rows if ":monthly:" in row.idempotency_key]
    assert weekly == [
        _daily_compound("100000.00", (first_monday - month_start).days),
        _compound_with_credits("100000.00", weekly[:1], 7),
    ]
    assert [row.idempotency_key.rsplit(":", 2)[-2:] for row in monthly] == [["monthly", f"{month_start:%Y-%m}"]]
    assert monthly[0].amount == _compound_with_credits(
        "100000.00", weekly, (next_month - second_monday).days
    )


def test_monthly_to_weekly_pays_the_straddling_week_from_the_month_end(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="monthly")

    month_start = _first_month_not_starting_monday(tz_name)
    next_month = _one_month_after(month_start)
    _fund_savings(monkeypatch, app, classroom, seat, "100000.00", _local(tz_name, month_start, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, month_start, 1))
    _tick(monkeypatch, app, _local(tz_name, next_month, 1))  # credits the month
    _tick(monkeypatch, app, _local(tz_name, next_month, 2))

    _configure_interest(client, classroom, payout="weekly")
    following_monday = next_month + timedelta(days=(7 - next_month.weekday()) % 7)
    _run_ticks(monkeypatch, app, tz_name, next_month + timedelta(days=1), following_monday)

    rows = _interest_rows(app, classroom, seat)
    month_credit = rows[0].amount
    assert rows[0].idempotency_key.endswith(f":monthly:{month_start:%Y-%m}")
    week_start = following_monday - timedelta(days=7)
    assert [row.idempotency_key.rsplit(":", 1)[-1] for row in rows[1:]] == [week_start.isoformat()]
    assert rows[1].amount == _compound_with_credits(
        "100000.00", [month_credit], (following_monday - next_month).days
    )
