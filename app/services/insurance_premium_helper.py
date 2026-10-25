"""Economic Engine Helper data for the insurance authoring form (SPEC-ECON-003 §4.4.8, §4.9).

Read-only: resolves the class's CWI, economic mode and rent, and the Engine's
recommended premium per tier and billing frequency, as plain currency figures the
form embeds. The form's script then reports the teacher's typed premium against
them — position in the band, INCOME_SHARE, REMAINING_AFTER rent, and (monetary
products) PROTECTION_TRADEOFF — without a round trip. Nothing here is persisted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.models import _quantize_currency
from app.services import economic_engine as ee
from app.services.class_configuration_query_service import get_rent_settings, is_feature_enabled

# Authoring-time week-equivalent per billing frequency. MONTHLY uses the fixed 30-day
# authoring normalization of SPEC-ECON-003 §4.4.8; it never defines a billing period.
_AUTHORING_DAYS = {"WEEKLY": 7, "MONTHLY": 30}


def build_insurance_premium_helper(class_id: str) -> Optional[dict]:
    """Helper inputs for ``class_id``, or ``None`` without a positive CWI."""
    base = ee.resolve_base(class_id)
    if not base.has_cwi:  # a zero or negative pay rate yields a CWI no share can be taken of
        return None

    band = ee._PREMIUM_BANDS[base.economy_policy_mode]
    frequencies = {}
    for frequency, days in _AUTHORING_DAYS.items():
        week_equiv = Decimal(days) / Decimal(7)
        income = base.cwi * week_equiv
        frequencies[frequency] = {
            "income": float(_quantize_currency(income)),
            "band_min": float(_quantize_currency(income * band["lower"])),
            "band_max": float(_quantize_currency(income * band["upper"])),
            "recommended": {
                tier: float(ee.resolve_insurance(
                    product=ee.TRANSACTION,
                    tier=tier,
                    coverage_period=frequency.lower(),
                    covered_calendar_days=None if frequency == "WEEKLY" else days,
                    cwi=base.cwi,
                    mode=base.economy_policy_mode,
                ).period_premium)
                for tier in ee.INSURANCE_TIERS
            },
        }

    rent = None
    # A retained settings row is not a current expense while rent is switched off.
    rent_settings = get_rent_settings(class_id) if is_feature_enabled(class_id, "rent") else None
    if rent_settings is not None and rent_settings.rent_amount is not None:
        from app.utils.economy_balance import EconomyBalanceChecker

        weekly_rent = EconomyBalanceChecker(None, policy_mode=base.economy_policy_mode, class_id=class_id)._normalize_to_weekly(
            Decimal(str(rent_settings.rent_amount)),
            rent_settings.frequency_type,
            rent_settings.custom_frequency_value,
            getattr(rent_settings, "custom_frequency_unit", None),
        )
        # Rent billed at the policy's own frequency is a fixed amount per period, like the premium:
        # show what students are charged, not a 30-day rescaling of it.
        rent = {
            frequency: float(_quantize_currency(
                Decimal(str(rent_settings.rent_amount))
                if rent_settings.frequency_type == frequency.lower()
                else weekly_rent * Decimal(days) / Decimal(7)
            ))
            for frequency, days in _AUTHORING_DAYS.items()
        }

    return {
        "cwi": float(base.cwi),
        "mode": base.economy_policy_mode,
        "band_rate": [float(band["lower"]), float(band["upper"])],
        "frequencies": frequencies,
        "rent": rent,
    }
