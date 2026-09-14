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

from app.services.store.form_contract import resolve_store_form_contract
from app.utils.economy_balance import EconomicRole, EconomyBalanceChecker
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

    ``validate_fine_value`` used a class-level fallback constant directly, so a
    class on the tight or comfortable policy was judged against the default band
    while the Economic Engine card showed it the band for its actual mode.
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
def test_store_role_band_matches_the_engine_card(mode, cwi):
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_store_item_value(price=1.0, cwi=cwi)
    card = get_price_recommendation_context(mode, cwi)

    for role in EconomicRole:
        page = recommendations["roles"][role.value]
        engine = card["store_roles"][role.value]
        assert page["min"] == pytest.approx(engine["min"]), f"{mode}@{cwi} {role.value} min"
        assert page["max"] == pytest.approx(engine["max"]), f"{mode}@{cwi} {role.value} max"


@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_store_role_bands_do_not_vary_by_policy_mode(cwi):
    """SPEC-ECON-003 §4.7's role table has no policy-mode axis."""
    bands = [
        _checker(mode).validate_store_item_value(price=1.0, cwi=cwi)[1]["roles"]
        for mode in MODES
    ]
    assert all(band == bands[0] for band in bands), f"role bands diverged across modes @{cwi}"


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_store_item_priced_at_its_role_boundary_is_within_range(mode, cwi):
    """A price copied from a displayed role band must read as inside that band."""
    checker = _checker(mode)
    _, recommendations, _ = checker.validate_store_item_value(price=1.0, cwi=cwi)

    for role in EconomicRole:
        band = recommendations["roles"][role.value]
        for bound in ("min", "max"):
            warnings, _, _ = checker.validate_store_item_value(
                band[bound], cwi, economic_role=role.value
            )
            levels = {w["level"] for w in warnings}
            assert "warning" not in levels and "critical" not in levels, (
                f"{mode}@{cwi}: {role.value} {bound} ({band[bound]}) read as out of range: {warnings}"
            )


@pytest.mark.parametrize("cwi", [100.00, 337.50])
def test_store_price_outside_its_role_band_stays_valid(cwi):
    """SPEC-ECON-003 §4.7: an out-of-band price is reported, never rejected."""
    checker = _checker("default")
    _, recommendations, _ = checker.validate_store_item_value(price=1.0, cwi=cwi)
    necessity_max = recommendations["roles"]["necessity"]["max"]

    warnings, _, _ = checker.validate_store_item_value(
        necessity_max * 3, cwi, economic_role="necessity"
    )
    levels = {w["level"] for w in warnings}
    assert "critical" not in levels, f"out-of-band necessity price was rejected: {warnings}"
    assert "warning" in levels, f"out-of-band necessity price went unreported: {warnings}"


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 300.01, 999.99])
def test_collective_goal_guidance_quotes_currency_from_the_policy_band(mode, cwi):
    """The goal-amount hint must price the §4.6 band, not restate the ratio.

    A teacher types a goal in dollars. This surface previously rendered only
    "1×–8× CWI" — a ratio no policy mode defines, and one that left the teacher
    doing the arithmetic. Both halves are asserted here: the dollar endpoints
    must equal ``cwi × band`` read from ``POLICY_MODES``, and the ratio must
    still be shown, because that is what Rebalance re-derives the goal from.
    """
    band = POLICY_MODES[mode]["ratios"]["collective_goal"]
    contract = resolve_store_form_contract(
        item_type="collective",
        rent_linked=False,
        direct_purchase=True,
        rent_prevents_purchase_when_late=False,
        collective_goal_band=band,
        cwi=cwi,
    )
    guidance = next(
        field.label
        for section in contract.sections
        for field in section.fields
        if field.name == "collective_goal_guidance"
    )

    expected = (
        f"Recommended range: ${cwi * band['min']:,.2f}–${cwi * band['max']:,.2f} "
        f"({band['min']:g}×–{band['max']:g}× CWI)."
    )
    assert guidance == expected, f"{mode}@{cwi}: {guidance!r}"
    # The currency half is the point; a ratio-only string must not pass.
    assert "$" in guidance


@pytest.mark.parametrize("mode", MODES)
def test_collective_goal_guidance_without_a_cwi_admits_it(mode):
    """No pay rate configured means no dollar band exists to quote.

    The honest answer is to say the CWI is missing. Silently falling back to a
    bare ratio reads like the recommendation itself, which is how the drifted
    1×–8× text survived unnoticed.
    """
    band = POLICY_MODES[mode]["ratios"]["collective_goal"]
    contract = resolve_store_form_contract(
        item_type="collective",
        rent_linked=False,
        direct_purchase=True,
        rent_prevents_purchase_when_late=False,
        collective_goal_band=band,
        cwi=None,
    )
    guidance = next(
        field.label
        for section in contract.sections
        for field in section.fields
        if field.name == "collective_goal_guidance"
    )
    assert "$" not in guidance
    assert "pay rate" in guidance
    assert f"{band['min']:g}×–{band['max']:g}× CWI" in guidance


def test_collective_goal_guidance_band_is_not_restated_in_the_store_service():
    """The form must carry no collective-goal band of its own.

    The regression: ``form_contract`` held ``{'min': 1.0, 'max': 8.0}``, so the
    range a teacher read while naming a goal was not the range the engine judged
    it against. An omitted band must resolve policy authority's default mode.
    """
    from app.utils.economy_policy import POLICY_MODE_DEFAULT

    default_band = POLICY_MODES[POLICY_MODE_DEFAULT]["ratios"]["collective_goal"]
    omitted = resolve_store_form_contract(
        item_type="collective",
        rent_linked=False,
        direct_purchase=True,
        rent_prevents_purchase_when_late=False,
        cwi=100.0,
    )
    explicit = resolve_store_form_contract(
        item_type="collective",
        rent_linked=False,
        direct_purchase=True,
        rent_prevents_purchase_when_late=False,
        collective_goal_band=default_band,
        cwi=100.0,
    )

    def _guidance(contract):
        return next(
            field.label
            for section in contract.sections
            for field in section.fields
            if field.name == "collective_goal_guidance"
        )

    assert _guidance(omitted) == _guidance(explicit)


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


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("cwi", [100.00, 337.50, 999.99])
def test_overdraft_fine_band_is_the_same_band_the_fine_page_shows(mode, cwi):
    """The Economic Engine and the settings page must derive fines from one table.

    They used to hold separate per-mode fine dictionaries, which had already
    drifted: the engine judged an overdraft fee against tight 7%-18% while the
    settings page recommended tight 5%-10% for the same class.
    """
    from app.services.economic_engine import resolve_overdraft_fine

    page = _checker(mode).fine_band(cwi)
    engine = resolve_overdraft_fine(cwi=Decimal(str(cwi)), mode=mode)

    assert engine.flat_fee_lower == page["min"], f"{mode}@{cwi} fine minimum"
    assert engine.flat_fee_upper == page["max"], f"{mode}@{cwi} fine maximum"


@pytest.mark.parametrize("mode", MODES)
def test_savings_target_has_one_source(mode):
    """The interest ceiling and the teacher-facing savings target share a rate."""
    from app.services.economic_engine import _SAVINGS_RATES

    assert _SAVINGS_RATES[mode] == Decimal(
        str(POLICY_MODES[mode]["ratios"]["savings_weekly"]["target"])
    )
