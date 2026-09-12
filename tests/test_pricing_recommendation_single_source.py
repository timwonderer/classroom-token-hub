"""Every CWI-derived price band has exactly one source (INV-ARC-022 §V.7, §V.9).

The defect these tests hold shut: the same band was derived independently by the
Economic Engine card, the feature settings page, and the warning that judges the
saved value — each with its own rounding schedule. A teacher could type the exact
number the page recommended and be told it was below the recommended minimum.

The invariant is therefore not "the numbers are close" but *the band a teacher is
shown is the band they are judged against*, byte for byte, at every frequency.
"""

import pytest
from decimal import Decimal

from app.utils.economy_balance import EconomyBalanceChecker, PricingTier
from app.utils.economy_policy import (
    POLICY_MODES,
    get_price_recommendation_context,
)


FREQUENCIES = [
    ("monthly", None, None),
    ("weekly", None, None),
    ("biweekly", None, None),
    ("daily", None, None),
    ("custom", 10, "days"),
    ("custom", 3, "weeks"),
    ("custom", 2, "months"),
]

MODES = sorted(POLICY_MODES)


def _checker(mode="default"):
    return EconomyBalanceChecker(user_id=1, policy_mode=mode)


class _RentSettings:
    """Minimal stand-in for the RentSettings columns the checker reads."""

    def __init__(self, amount, frequency_type, custom_value=None, custom_unit=None):
        self.rent_amount = Decimal(str(amount))
        self.frequency_type = frequency_type
        self.custom_frequency_value = custom_value
        self.custom_frequency_unit = custom_unit


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("frequency,custom_value,custom_unit", FREQUENCIES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 412.37, 999.99])
def test_recommended_minimum_is_accepted_as_balanced(
    mode, frequency, custom_value, custom_unit, cwi
):
    """Setting rent to the displayed minimum must not warn that it is below it.

    This is the exact contradiction the teacher hit: the rent page recommended
    $880.51/month, the teacher entered $880.51, and the Economic Engine reported
    it below the recommended minimum — because the threshold was compared
    unquantized while the entered value was quantized to cents.
    """
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_rent_value(
        rent_amount=1.0,
        frequency_type=frequency,
        cwi=cwi,
        custom_frequency_value=custom_value,
        custom_frequency_unit=custom_unit,
    )

    at_minimum = recommendations["min"]
    warnings, _, _ = checker.validate_rent_value(
        rent_amount=at_minimum,
        frequency_type=frequency,
        cwi=cwi,
        custom_frequency_value=custom_value,
        custom_frequency_unit=custom_unit,
    )
    levels = {w["level"] for w in warnings}
    assert "warning" not in levels and "critical" not in levels, (
        f"{mode}/{frequency}: recommended minimum {at_minimum} was rejected: {warnings}"
    )

    at_maximum = recommendations["max"]
    warnings, _, _ = checker.validate_rent_value(
        rent_amount=at_maximum,
        frequency_type=frequency,
        cwi=cwi,
        custom_frequency_value=custom_value,
        custom_frequency_unit=custom_unit,
    )
    levels = {w["level"] for w in warnings}
    assert "warning" not in levels and "critical" not in levels, (
        f"{mode}/{frequency}: recommended maximum {at_maximum} was rejected: {warnings}"
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("frequency,custom_value,custom_unit", FREQUENCIES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 412.37, 999.99])
def test_rent_page_band_matches_the_band_the_warning_quotes(
    mode, frequency, custom_value, custom_unit, cwi
):
    """The settings page and the balance warning must quote one band, not two."""
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_rent_value(
        rent_amount=1.0,
        frequency_type=frequency,
        cwi=cwi,
        custom_frequency_value=custom_value,
        custom_frequency_unit=custom_unit,
    )

    settings = _RentSettings(recommendations["recommended"], frequency, custom_value, custom_unit)
    balance_warnings = checker.check_rent_balance(settings, cwi)
    assert len(balance_warnings) == 1
    warning = balance_warnings[0]

    assert warning.recommended_min == pytest.approx(recommendations["min"]), (
        f"{mode}/{frequency}: warning band min {warning.recommended_min} "
        f"!= page band min {recommendations['min']}"
    )
    assert warning.recommended_max == pytest.approx(recommendations["max"]), (
        f"{mode}/{frequency}: warning band max {warning.recommended_max} "
        f"!= page band max {recommendations['max']}"
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 412.37, 999.99])
def test_engine_card_band_matches_the_rent_page_band(mode, cwi):
    """The Economic Engine card and the rent page must agree to the cent.

    Both render a monthly rent band from the same policy ratio. They previously
    disagreed by 1-2 cents on 75% of CWI values because one quantized the weekly
    band before scaling to monthly and the other scaled first.
    """
    checker = _checker(mode)
    _, page_band, _ = checker.validate_rent_value(
        rent_amount=1.0, frequency_type="monthly", cwi=cwi
    )
    card = get_price_recommendation_context(mode, cwi)

    for key in ("min", "max", "recommended"):
        assert card["rent"][key] == pytest.approx(page_band[key]), (
            f"{mode}@{cwi}: engine card rent {key} {card['rent'][key]} "
            f"!= rent page {key} {page_band[key]}"
        )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_fine_band_honours_the_policy_mode(mode, cwi):
    """Fine validation must read the class's policy mode, not a hardcoded constant.

    ``validate_fine_value`` used ``FINE_MIN_RATIO`` directly, so a class on the
    tight or comfortable policy was judged against the default band while the
    Economic Engine card showed it the band for its actual mode.
    """
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_fine_value(fine_amount=1.0, cwi=cwi)
    card = get_price_recommendation_context(mode, cwi)

    for key in ("min", "max", "recommended"):
        assert recommendations[key] == pytest.approx(card["fine"][key]), (
            f"{mode}@{cwi}: fine {key} {recommendations[key]} != card {card['fine'][key]}"
        )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_fine_at_recommended_minimum_is_accepted(mode, cwi):
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_fine_value(fine_amount=1.0, cwi=cwi)

    for bound in ("min", "max"):
        warnings, _, _ = checker.validate_fine_value(recommendations[bound], cwi)
        levels = {w["level"] for w in warnings}
        assert "warning" not in levels and "critical" not in levels, (
            f"{mode}@{cwi}: fine at recommended {bound} ({recommendations[bound]}) rejected: {warnings}"
        )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_store_tier_band_matches_the_engine_card(mode, cwi):
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_store_item_value(price=1.0, cwi=cwi)
    card = get_price_recommendation_context(mode, cwi)

    for tier in PricingTier:
        page = recommendations["tiers"][tier.value]
        engine = card["store_tiers"][tier.value]
        assert page["min"] == pytest.approx(engine["min"]), f"{mode}@{cwi} {tier.value} min"
        assert page["max"] == pytest.approx(engine["max"]), f"{mode}@{cwi} {tier.value} max"


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_store_item_priced_at_a_tier_boundary_is_accepted(mode, cwi):
    """A price copied from a displayed tier band must land inside that tier."""
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_store_item_value(price=1.0, cwi=cwi)

    for tier in PricingTier:
        band = recommendations["tiers"][tier.value]
        for bound in ("min", "max"):
            warnings, _, _ = checker.validate_store_item_value(band[bound], cwi)
            levels = {w["level"] for w in warnings}
            assert "critical" not in levels, (
                f"{mode}@{cwi}: {tier.value} {bound} ({band[bound]}) rejected: {warnings}"
            )


def test_average_weeks_per_month_has_one_definition():
    """The month-length constant must not be redefined per module.

    Two definitions existed (4.3482142857142856 and a truncated 4.348214285714),
    plus a third copy inside FREQUENCY_WEEK_MULTIPLIERS.
    """
    from app.utils import economy_policy

    assert (
        EconomyBalanceChecker.AVERAGE_WEEKS_PER_MONTH
        is economy_policy.AVERAGE_WEEKS_PER_MONTH
    )
    assert (
        economy_policy.FREQUENCY_WEEK_MULTIPLIERS["monthly"]
        is economy_policy.AVERAGE_WEEKS_PER_MONTH
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("frequency,custom_value,custom_unit", FREQUENCIES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 412.37, 999.99])
def test_rebalance_preview_proposes_the_band_the_page_recommends(
    mode, frequency, custom_value, custom_unit, cwi
):
    """What Apply writes must equal what the rent page recommends.

    The preview scaled the already-rounded weekly recommendation into the
    teacher's cadence, so the amount the button wrote could land a cent away
    from the amount the page quoted — a disagreement with consequences, since
    one of the two becomes the saved rent.
    """
    from app.routes.admin import _build_rebalance_preview

    checker = _checker(mode)
    settings = _RentSettings("0.01", frequency, custom_value, custom_unit)
    items = _build_rebalance_preview(None, "class-1", checker, cwi, settings, [])

    expected = checker.rent_band(cwi, frequency, custom_value, custom_unit)["recommended"]
    rent_item = next(item for item in items if item["key"] == "rent")
    assert Decimal(rent_item["change"]["new_value"]) == expected
