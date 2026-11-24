"""SPEC-ECON-001 §4.1: simple interest must not compound at payout frequency.

Regression tests for issue #1646 (KD-1). Before the fix, once a payout window
was credited, the credit became part of the posted savings balance, and every
later day's earning base was that posted balance for every calculation type
(§9.2) -- so under simple interest, credited interest silently earned interest
in later windows, drifting toward compounding at the payout frequency.

The fix: simple interest's daily earning base is a principal-only series --
every previously credited interest dollar excluded -- reconstructed from the
ledger exactly as the full posted-balance series is, just filtering out rows
tagged as savings-interest credits (type="Interest",
idempotency_key.startswith("savings-interest:...")). No new persisted state.

These drive the real scheduled job (``run_savings_interest_job``) and the real
forecast (``forecast_savings``), with the resolver clock pinned, mirroring
``tests/test_savings_interest_payout_cadence.py``.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

import pytz

from app.feats.base import FEATContext
from app.models import Transaction
from app.scheduled_tasks import run_savings_interest_job
from app.utils import canonical_temporal_resolver as resolver_module
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import (
    compensate_ledger_posted_transaction,
    create_ledger_idempotent_transaction,
    settle_ledger_balances,
)

RATE = Decimal("0.1733")
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
    zone = pytz.timezone(tz_name)
    return zone.localize(datetime.combine(day, time(hour, minute))).astimezone(timezone.utc)


def _next_monday(tz_name, *, after_days=3):
    today = datetime.now(pytz.timezone(tz_name)).date() + timedelta(days=after_days)
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _configure_interest(client, classroom, *, payout, compound="never", calc="simple"):
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
        key = f"simple-noncompound-fund:{uuid4().hex}"
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=key):
            create_ledger_idempotent_transaction(
                idempotency_key=key, seat_id=seat.id, class_id=classroom.class_id,
                amount=Decimal(amount), account_type="savings", type="payroll",
                description="Simple-interest non-compounding test funding",
            )


def _tick(monkeypatch, app, at):
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


def _cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _simple(balance, days):
    return _cents(Decimal(balance) * DAILY_RATE * days)


def _daily_compound(balance, days):
    return _cents(Decimal(balance) * ((1 + DAILY_RATE) ** days - 1))


def _forecast(monkeypatch, app, classroom, seat, at, months):
    from app.services.ledger_interest_service import forecast_savings

    with app.app_context(), _pinned_clock(monkeypatch, at):
        return forecast_savings(seat.id, classroom.class_id, months=months)


# --------------------------------------------------------------------------- #
# Runtime: simple interest across multiple payout windows                     #
# --------------------------------------------------------------------------- #

def test_simple_interest_window_two_excludes_window_one_credited_interest(client, app, monkeypatch):
    """Window 2's credit must equal principal x rate x days, not
    (principal + window-1 interest) x rate x days (SPEC-ECON-001 §4.1)."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit

    week_two_close = monday + timedelta(days=14)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2

    expected_each_window = _simple("1000.00", 7)
    assert rows[0].amount == expected_each_window
    # Before the fix this would be ("1000.00" + window-1 interest) x rate x 7,
    # i.e. strictly greater than the first window's credit.
    assert rows[1].amount == expected_each_window


def test_simple_interest_stays_flat_across_three_windows(client, app, monkeypatch):
    """Three consecutive weekly windows on an unchanged balance all credit the
    same amount under simple interest -- no drift toward compounding."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "500.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))

    week_three_close = monday + timedelta(days=21)
    _tick(monkeypatch, app, _local(tz_name, week_three_close, 0, 30))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 3
    expected = _simple("500.00", 7)
    assert [row.amount for row in rows] == [expected, expected, expected]


def test_simple_interest_withdrawal_still_reduces_the_earning_base(client, app, monkeypatch):
    """Principal is not a frozen opening balance: an ordinary withdrawal between
    windows still lowers window 2's earning base, exactly as it did before this
    fix -- only credited interest is excluded from the base."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    week_two_start = monday + timedelta(days=7)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))
    # Withdraw half, right at the start of window two (after window one closes).
    _fund_savings(monkeypatch, app, classroom, seat, "-500.00", _local(tz_name, week_two_start, 0, 10))
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 0, 20))

    week_two_close = week_two_start + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2
    assert rows[0].amount == _simple("1000.00", 7)
    assert rows[1].amount == _simple("500.00", 7)


def test_reversed_interest_credit_does_not_reduce_simple_interest_principal(client, app, monkeypatch):
    """A reversed interest credit must cancel out of the principal-only series,
    not reduce it further (#1646 follow-up, CodeRabbit finding on PR #1833).

    Window one's credit is already excluded from the principal-only base. Its
    reversal undoes that exact credit, so the pair's net effect on principal
    must be zero: window two's earning base stays the untouched $1000.00
    deposit. Before this fix the reversal (tagged as an ordinary, non-interest
    row) subtracted the reversed interest from principal a second time, so
    window two underpaid.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit

    week_two_start = monday + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 0, 30))  # credits window one

    window_one_credit = _interest_rows(app, classroom, seat)[0]
    assert window_one_credit.amount == _simple("1000.00", 7)

    # Reverse window one's credit and settle the reversal itself from WITHIN
    # window two (not at window two's own close tick), so it genuinely
    # participates in window two's own earning-base computation instead of
    # landing after every day window two accrues over.
    reverse_at = _local(tz_name, week_two_start, 2)
    with app.app_context(), _pinned_clock(monkeypatch, reverse_at):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"1646-reverse:{seat.id}"):
            compensate_ledger_posted_transaction(
                window_one_credit,
                description="Reverse window-one interest credit for #1646 regression",
                idempotency_key=f"1646-reverse-tx:{seat.id}",
            )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"1646-reverse-settle:{seat.id}"):
            settle_ledger_balances(seat.id, classroom.class_id)

    week_two_close = week_two_start + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))  # credits window two

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2
    # Before the fix: strictly less than this, since the reversal's negative
    # amount was double-counted against principal.
    assert rows[1].amount == _simple("1000.00", 7)


def test_withdrawal_draining_credited_interest_does_not_leave_negative_principal(client, app, monkeypatch):
    """Withdrawing the full balance (principal plus credited interest) and then
    redepositing new principal must not leave a phantom negative principal
    offset baked into the earning base (Codex finding on PR #1833, #1646
    follow-up).

    Before this fix, the withdrawal's full face value was subtracted from the
    principal-only series even though part of it was credited interest -- money
    that was never principal to begin with -- so the series went permanently
    negative by that amount, and a later deposit the same size as the original
    principal was credited as if it were short by exactly the interest that
    had been withdrawn.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit

    week_two_start = monday + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 0, 30))  # credits window one

    window_one_credit = _interest_rows(app, classroom, seat)[0]

    # Drain the whole posted balance -- principal plus the credited interest
    # -- then deposit fresh principal the same size as the original.
    drain_amount = Decimal("1000.00") + window_one_credit.amount
    _fund_savings(
        monkeypatch, app, classroom, seat, f"-{drain_amount}",
        _local(tz_name, week_two_start, 2),
    )
    _fund_savings(
        monkeypatch, app, classroom, seat, "1000.00",
        _local(tz_name, week_two_start, 2, 10),
    )
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 2, 20))  # settles both

    week_two_close = week_two_start + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))  # credits window two

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2
    # Before the fix: strictly less than this, short by exactly
    # window_one_credit.amount, since the withdrawal's face value (principal
    # + interest) was fully subtracted from the principal-only series.
    assert rows[1].amount == _simple("1000.00", 7)


def test_savings_ledger_history_independent_of_database_row_order(client, app, monkeypatch):
    """_savings_ledger's reconstructed history must not depend on the order
    Postgres happens to return same-instant rows in (Codex finding on PR
    #1833, #1646 follow-up).

    ``settle_balances`` gives every row it settles in one pass the same
    ``posted_at``, and the underlying query carries no ``ORDER BY``, so two
    rows sharing a timestamp can come back in either order. The interest-pool
    walk in ``_end_of_day_balances`` is order-dependent for such ties (a
    withdrawal processed before vs. after a same-instant deposit draws a
    different amount from the pool), so the sort that builds ``history`` must
    use a deterministic tie-breaker (``posting_sequence``) rather than
    whatever order the rows arrived in.
    """
    from app.services import ledger_interest_service as svc

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit

    week_two_start = monday + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 0, 30))  # credits window one

    window_one_credit = _interest_rows(app, classroom, seat)[0]
    drain_amount = Decimal("1000.00") + window_one_credit.amount
    # Both settle in the SAME _tick call below, so settle_balances stamps both
    # with the identical posted_at -- the exact tie this finding is about.
    _fund_savings(
        monkeypatch, app, classroom, seat, f"-{drain_amount}",
        _local(tz_name, week_two_start, 2),
    )
    _fund_savings(
        monkeypatch, app, classroom, seat, "1000.00",
        _local(tz_name, week_two_start, 2, 10),
    )
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 2, 20))  # settles both, same posted_at

    with app.app_context():
        rows = (
            Transaction.query
            .filter(
                Transaction.seat_id == seat.id,
                Transaction.class_id == classroom.class_id,
                Transaction.account_type == "savings",
            )
            .all()
        )
        assert len(rows) >= 4

        class _FakeFilter:
            def __init__(self, data):
                self._data = data

            def all(self):
                return self._data

        class _FakeQuery:
            def __init__(self, data):
                self._data = data

            def filter(self, *args, **kwargs):
                return _FakeFilter(self._data)

        monkeypatch.setattr(svc.Transaction, "query", _FakeQuery(rows))
        forward = svc._savings_ledger(seat.id, classroom.class_id, "weekly")

        monkeypatch.setattr(svc.Transaction, "query", _FakeQuery(list(reversed(rows))))
        backward = svc._savings_ledger(seat.id, classroom.class_id, "weekly")

    assert forward.history == backward.history


# --------------------------------------------------------------------------- #
# Sanity: compound interest is unaffected by the fix                          #
# --------------------------------------------------------------------------- #

def test_compound_interest_still_compounds_across_windows(client, app, monkeypatch):
    """Daily compounding still folds window 1's credited interest into window
    2's base -- the fix must not touch the compound paths."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="daily", calc="compound")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))

    week_two_close = monday + timedelta(days=14)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))

    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2
    assert rows[0].amount == _daily_compound("1000.00", 7)
    # Window two's earning base is 1000 + window-one's credited interest.
    expected_window_two = _daily_compound(Decimal("1000.00") + rows[0].amount, 7)
    assert rows[1].amount == expected_window_two
    assert rows[1].amount > rows[0].amount


def test_simple_and_compound_diverge_on_identical_balances(client, app, monkeypatch):
    """Two seats, same balance, same rate, same cadence, differing only in
    ``interest_calculation_type``: simple stays flat window-to-window while
    compound's second window strictly outpaces its first."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone

    # Compound settings apply at the class level, so run the simple seat under
    # its own config, snapshot its rows, then reconfigure the class compound
    # and run an identically-funded second seat through the same tick shape.
    simple_seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, simple_seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))
    week_two_close = monday + timedelta(days=14)
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 30))
    simple_rows = _interest_rows(app, classroom, simple_seat)
    assert len(simple_rows) == 2
    assert simple_rows[1].amount == simple_rows[0].amount

    compound_seat = classroom.students[1].seat
    _configure_interest(client, classroom, payout="weekly", compound="daily", calc="compound")
    _fund_savings(monkeypatch, app, classroom, compound_seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 2))
    _tick(monkeypatch, app, _local(tz_name, week_two_close, 0, 45))
    compound_rows = _interest_rows(app, classroom, compound_seat)
    assert len(compound_rows) == 2
    assert compound_rows[1].amount > compound_rows[0].amount
    assert compound_rows[1].amount > simple_rows[1].amount


# --------------------------------------------------------------------------- #
# Forecast (SPEC-ECON-001 §10): projection must match runtime, not compound    #
# --------------------------------------------------------------------------- #

def test_forecast_simple_interest_does_not_compound_across_projected_windows(client, app, monkeypatch):
    """The projected series for simple interest must stay flat per window,
    exactly like the runtime path above -- not just for the first window.

    Mirrors ``test_weekly_runtime_matches_the_projection_over_a_month``: after
    each window closes and is credited by the real job, re-forecast the next
    (still-open) window and confirm its projected credit equals the first
    window's -- the forecast must not compound either.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")
    week = _simple("1000.00", 7)

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit

    forecast_window_one = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, monday, 1, 30), months=0)
    assert forecast_window_one.next_credit == week

    window_two_start = monday + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, window_two_start, 0, 30))  # credits window one
    forecast_window_two = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, window_two_start, 1), months=0)
    assert forecast_window_two.next_credit == week

    window_three_start = window_two_start + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, window_three_start, 0, 30))  # credits window two
    forecast_window_three = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, window_three_start, 1), months=0)
    assert forecast_window_three.next_credit == week

    _tick(monkeypatch, app, _local(tz_name, window_three_start + timedelta(days=7), 0, 30))
    rows = _interest_rows(app, classroom, seat)
    assert [row.amount for row in rows] == [week, week, week]


def test_forecast_next_credit_matches_runtime_for_simple_interest_second_window(client, app, monkeypatch):
    """``forecast_savings().next_credit`` for the already-open second window
    must equal what the runtime job actually posts for it."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", compound="never", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))

    week_two_start = monday + timedelta(days=7)
    _tick(monkeypatch, app, _local(tz_name, week_two_start, 0, 30))  # credits window one

    forecast = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, week_two_start, 1), months=0)
    assert forecast.next_credit == _simple("1000.00", 7)

    _tick(monkeypatch, app, _local(tz_name, week_two_start + timedelta(days=7), 0, 30))
    rows = _interest_rows(app, classroom, seat)
    assert len(rows) == 2
    assert rows[1].amount == forecast.next_credit

