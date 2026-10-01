"""SPEC-ECON-001 conformance for the canonical savings accrual engine.

These are pure-function tests on the single authoritative accrual engine
(`app.services.economic_engine`) that both the runtime payout and the UI
projection consume. They pin the daily balance method (§9.2, operator ruling
2026-09-30):

  * each day accrues ``earning base × r / 365`` on its end-of-day posted balance
  * §4.1 simple: accrued interest never joins the base
  * §6.2 daily compounding: accrued interest joins every day; weekly/monthly
    compounding: it joins at the marked boundary days inside the window
  * §5.3 rounding happens once, when the window is credited
  * §10 projection == runtime (both call the same accrual)
  * §11 no hidden default APY: an unset rate accrues nothing / projects flat
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.economic_engine import (
    SAVINGS_DAYS_PER_YEAR,
    ProjectedSavingsDay,
    SavingsAccrualDay,
    _COMPOUND_FREQ_PER_YEAR,
    accrue_daily_interest,
    credit_savings_interest,
    project_savings_balances,
)

RATE = Decimal("0.1733")
DAILY = RATE / Decimal("365")


def _days(balances, rate=RATE, capitalize_on=()):
    return [
        SavingsAccrualDay(end_of_day_balance=Decimal(b), annual_rate=rate, capitalizes=i in capitalize_on)
        for i, b in enumerate(balances)
    ]


def _credit(days, calc="compound", freq="daily"):
    return credit_savings_interest(
        accrue_daily_interest(days=days, calculation_type=calc, compound_frequency=freq)
    )


# ---------------------------------------------------------------------------
# §5.2 — 365-day year, leap years included
# ---------------------------------------------------------------------------


def test_day_count_is_365_and_the_ceiling_uses_the_same_constant():
    """One named day count feeds accrual and the daily-compounding ceiling."""
    assert SAVINGS_DAYS_PER_YEAR == Decimal("365")
    assert _COMPOUND_FREQ_PER_YEAR["daily"] == SAVINGS_DAYS_PER_YEAR


def test_a_leap_year_of_days_earns_366_365ths_of_the_rate():
    """Each of a leap year's 366 days earns r/365, so the year earns r × 366/365."""
    accrued = accrue_daily_interest(
        days=_days(["1000.00"] * 366), calculation_type="simple", compound_frequency="never"
    )
    # 1000 × 0.1733 × 366/365 = 173.77; a 366-day year would give exactly 173.30.
    assert credit_savings_interest(accrued) == Decimal("173.77")


# ---------------------------------------------------------------------------
# §11 — no hidden default APY
# ---------------------------------------------------------------------------


def test_unconfigured_rate_accrues_nothing():
    assert _credit(_days(["100.00"] * 7, rate=None)) == Decimal("0.00")


def test_unconfigured_rate_projects_flat_line():
    window = [ProjectedSavingsDay(end_of_day_balance=None, annual_rate=None)] * 7
    series = project_savings_balances(
        posted_balance=Decimal("50.00"), windows=[window] * 4, checkpoints=[2, 4],
        calculation_type="compound", compound_frequency="daily",
    )
    assert series == [Decimal("50.00")] * 3


def test_zero_and_negative_balances_accrue_nothing():
    assert _credit(_days(["0.00", "-25.00", "0.00"])) == Decimal("0.00")


# ---------------------------------------------------------------------------
# Daily balance method, hand-computed (r = 17.33%, daily rate r/365)
# ---------------------------------------------------------------------------


def test_simple_week_is_seven_days_of_daily_rate():
    # 1000 × 0.1733/365 × 7 = 3.32356… -> 3.32
    assert _credit(_days(["1000.00"] * 7), calc="simple", freq="never") == Decimal("3.32")


def test_daily_compound_week_matches_closed_form():
    # 1000 × ((1 + 0.1733/365)^7 − 1) = 3.32829… -> 3.33
    assert _credit(_days(["1000.00"] * 7)) == Decimal("3.33")


def test_compound_never_equals_simple():
    days = _days(["250.00"] * 30)
    assert _credit(days, calc="simple", freq="daily") == _credit(days, calc="compound", freq="never")


def test_each_day_earns_on_its_own_end_of_day_balance():
    # Money for one day of seven earns one day: 1000 × 0.1733/365 = 0.4748 -> 0.47
    assert _credit(_days(["0.00"] * 6 + ["1000.00"])) == Decimal("0.47")


def test_weekly_compounding_joins_the_base_only_at_the_boundary():
    """Interest accrued in days 0-6 starts earning at day 7, not before."""
    balances = ["1000.00"] * 14
    got = accrue_daily_interest(
        days=_days(balances, capitalize_on=(7,)),
        calculation_type="compound", compound_frequency="weekly",
    )
    first_week = Decimal("1000") * DAILY * 7
    expected = first_week + (Decimal("1000") + first_week) * DAILY * 7
    assert abs(got - expected) < Decimal("1e-20")


def test_rounding_happens_once_per_window():
    # Each day's 10 × 0.1733/365 = 0.0047 would round to 0.00 alone; the sum rounds once.
    accrued = accrue_daily_interest(
        days=_days(["10.00"] * 30), calculation_type="simple", compound_frequency="never"
    )
    assert abs(accrued - Decimal("10") * DAILY * 30) < Decimal("1e-20")
    assert credit_savings_interest(accrued) == Decimal("0.14")


def test_a_day_accrues_at_its_own_rate():
    days = [
        SavingsAccrualDay(end_of_day_balance=Decimal("1000"), annual_rate=Decimal("0.1733")),
        SavingsAccrualDay(end_of_day_balance=Decimal("1000"), annual_rate=None),
        SavingsAccrualDay(end_of_day_balance=Decimal("1000"), annual_rate=Decimal("0.0365")),
    ]
    got = accrue_daily_interest(days=days, calculation_type="simple", compound_frequency="never")
    expected = Decimal("1000") * Decimal("0.1733") / 365 + Decimal("1000") * Decimal("0.0365") / 365
    assert abs(got - expected) < Decimal("1e-20")


def test_unsupported_compound_frequency_raises():
    with pytest.raises(ValueError):
        accrue_daily_interest(
            days=_days(["500.00"]), calculation_type="compound", compound_frequency="quarterly"
        )


# ---------------------------------------------------------------------------
# §10 — projection == runtime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("calc,freq", [
    ("simple", "never"),
    ("compound", "daily"),
    ("compound", "weekly"),
    ("compound", "monthly"),
])
def test_projection_first_window_equals_runtime_credit(calc, freq):
    window = [ProjectedSavingsDay(end_of_day_balance=None, annual_rate=RATE)] * 31
    series = project_savings_balances(
        posted_balance=Decimal("300.00"), windows=[window], checkpoints=[1],
        calculation_type=calc, compound_frequency=freq,
    )
    runtime = _credit(_days(["300.00"] * 31), calc=calc, freq=freq)
    assert series[1] - series[0] == runtime


def test_projection_capitalizes_each_window():
    """A credited window joins every day of the next window's balance."""
    window = [ProjectedSavingsDay(end_of_day_balance=None, annual_rate=RATE)] * 7
    series = project_savings_balances(
        posted_balance=Decimal("1000.00"), windows=[window] * 3, checkpoints=[1, 2, 3],
        calculation_type="compound", compound_frequency="daily",
    )
    balance = Decimal("1000.00")
    expected = [balance]
    for _ in range(3):
        balance += _credit(_days([balance] * 7))
        expected.append(balance)
    assert series == expected


def test_projection_uses_known_end_of_day_balances():
    """Days already ended in the open window use their real balances."""
    window = (
        [ProjectedSavingsDay(end_of_day_balance=Decimal("0"), annual_rate=RATE)] * 3
        + [ProjectedSavingsDay(end_of_day_balance=None, annual_rate=RATE)] * 4
    )
    series = project_savings_balances(
        posted_balance=Decimal("1000.00"), windows=[window], checkpoints=[1],
        calculation_type="compound", compound_frequency="daily",
    )
    assert series[1] - series[0] == _credit(_days(["0"] * 3 + ["1000.00"] * 4))


def test_higher_compound_frequency_earns_more():
    days = _days(["1000.00"] * 31, capitalize_on=(7, 14, 21, 28))
    daily = accrue_daily_interest(days=days, calculation_type="compound", compound_frequency="daily")
    weekly = accrue_daily_interest(days=days, calculation_type="compound", compound_frequency="weekly")
    simple = accrue_daily_interest(days=days, calculation_type="simple", compound_frequency="never")
    assert daily > weekly > simple
