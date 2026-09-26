"""Unit tests for the Economic Engine savings-interest and overdraft resolvers.

These resolvers are the canonical source of banking pricing guidance
(SPEC-ECON-003 §4.2 weekly savings target, §4.5 fine band, §5 interest
doubling-time). They are pure functions over (cwi, mode, compound_frequency),
so we exercise them with explicit inputs — no DB scope required. Every number
here is anchored to the spec's reference tables, not invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.economic_engine import (
    resolve_savings,
    resolve_overdraft_fine,
)


# --------------------------------------------------------------------------- #
# Savings interest (SPEC-ECON-003 §4.2, §5)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "mode,rate,target",
    [
        ("tight", Decimal("0.05"), Decimal("5.00")),
        ("default", Decimal("0.10"), Decimal("10.00")),
        ("comfortable", Decimal("0.15"), Decimal("15.00")),
    ],
)
def test_weekly_savings_target_is_mode_fraction_of_cwi(mode, rate, target):
    """§4.2: weekly savings target = CWI × {5,10,15}% by mode."""
    res = resolve_savings(cwi=Decimal("100"), mode=mode, compound_frequency="never")
    assert res.savings_rate == rate
    assert res.weekly_savings_target == target


@pytest.mark.parametrize(
    "mode,years",
    [("tight", Decimal("6")), ("default", Decimal("4")), ("comfortable", Decimal("2"))],
)
def test_simple_interest_ceiling_is_reciprocal_of_doubling_time(mode, years):
    """§5.4 (simple): doubling under A=P(1+r·t) gives r = 1/t.

    tight → 1/6 = 16.6667%, default → 1/4 = 25%, comfortable → 1/2 = 50%.
    """
    res = resolve_savings(cwi=Decimal("100"), mode=mode, compound_frequency="never")
    expected_pct = (Decimal("1") / years * Decimal("100")).quantize(Decimal("0.0001"))
    assert res.max_apy_percent == expected_pct
    assert res.min_doubling_years == years


def test_compound_interest_ceiling_respects_doubling_time():
    """§5.4 (compound): r = n×(2^(1/(n·t))−1).

    default mode (t=4yr), daily compounding (n=365): the ceiling must be strictly
    below the simple-interest ceiling (compounding reaches 2× faster for equal APR),
    and match the closed-form value to 4 dp.
    """
    res = resolve_savings(cwi=Decimal("100"), mode="default", compound_frequency="daily")
    # Closed form: 365 × (2^(1/1460) − 1) ≈ 0.173328 → 17.3328%
    assert res.max_apy_percent == Decimal("17.3328")
    # Compounding ceiling is below the 25% simple ceiling for the same mode.
    simple = resolve_savings(cwi=Decimal("100"), mode="default", compound_frequency="never")
    assert res.max_apy_percent < simple.max_apy_percent


def test_savings_recommendation_is_none_currency_without_cwi():
    """Without a CWI the target is undefined, but the interest ceiling still resolves."""
    res = resolve_savings(cwi=None, mode="default", compound_frequency="never")
    assert res.weekly_savings_target is None
    assert res.max_apy_percent == Decimal("25.0000")


def test_savings_rejects_unknown_compound_frequency():
    with pytest.raises(ValueError):
        resolve_savings(cwi=Decimal("100"), mode="default", compound_frequency="hourly")


# --------------------------------------------------------------------------- #
# Overdraft / internal fine (SPEC-ECON-003 §4.5, §4.5.1)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "mode,lower,upper",
    [
        ("tight", Decimal("5.00"), Decimal("10.00")),
        ("default", Decimal("5.00"), Decimal("12.00")),
        ("comfortable", Decimal("7.00"), Decimal("15.00")),
    ],
)
def test_overdraft_flat_fee_band_matches_fine_row(mode, lower, upper):
    """§4.5 / §8: overdraft flat fee reuses the fine band × CWI."""
    res = resolve_overdraft_fine(cwi=Decimal("100"), mode=mode)
    assert res.flat_fee_lower == lower
    assert res.flat_fee_upper == upper


@pytest.mark.parametrize(
    "mode,tiers",
    [
        ("tight", (Decimal("7.00"), Decimal("12.50"), Decimal("18.00"))),
        ("default", (Decimal("5.00"), Decimal("10.00"), Decimal("15.00"))),
        ("comfortable", (Decimal("4.00"), Decimal("8.00"), Decimal("12.00"))),
    ],
)
def test_overdraft_progressive_schedule_matches_spec_table(mode, tiers):
    """§4.5.1: progressive tier schedule as fractions of CWI."""
    res = resolve_overdraft_fine(cwi=Decimal("100"), mode=mode)
    assert res.progressive_fees == tiers


@pytest.mark.parametrize("mode", ["tight", "default", "comfortable"])
def test_progressive_tiers_are_not_clamped_to_the_generic_fine_band(mode):
    """§4.5.1: the tier schedule is self-contained, not a subdivision of §4.5.

    The two tables disagree on purpose — escalation bites hardest under ``tight``
    while the generic band rises toward ``comfortable`` — so a reader can mistake
    that for a transcription error and "fix" it by clamping the tiers into the
    band. That would silently flatten repeat-occurrence pressure. This test fails
    if anyone does, by asserting the overhang that clamping would remove.
    """
    res = resolve_overdraft_fine(cwi=Decimal("100"), mode=mode)
    lower, upper = res.flat_fee_lower, res.flat_fee_upper

    # Every mode has at least one tier outside the generic band, though which end
    # differs: tight and default overshoot the ceiling (12.5/18 vs 10, 15 vs 12),
    # while comfortable undershoots the floor (4 vs 7). Clamping to the band is
    # exactly what would erase these, so assert the escape rather than a fixed end.
    outside = [t for t in res.progressive_fees if t < lower or t > upper]
    assert outside, (
        f"{mode}: every progressive tier {res.progressive_fees} now fits inside "
        f"the generic fine band ({lower}-{upper}) — §4.5.1 forbids clamping."
    )

    # And the schedule must still escalate monotonically.
    assert list(res.progressive_fees) == sorted(res.progressive_fees)


def test_overdraft_recommendation_currency_is_none_without_cwi():
    res = resolve_overdraft_fine(cwi=None, mode="default")
    assert res.flat_fee_lower is None
    assert res.flat_fee_upper is None
    assert res.progressive_fees is None
    # Rate fractions are always available (do not depend on CWI).
    assert res.fine_rate_lower == Decimal("0.05")
    assert res.fine_rate_upper == Decimal("0.12")
