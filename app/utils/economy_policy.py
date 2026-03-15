from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
from flask import has_app_context


POLICY_MODE_DEFAULT = "default"
TIER_WAITING_PERIOD_DAYS = {
    1: 7,
    2: 5,
    3: 3,
}
TRANSACTION_DEFAULTS = {
    "non_tiered": {
        "weekly_premium_rate": Decimal("0.08"),
        "coverage_percent": Decimal("0.70"),
        "weekly_cap_multiplier": Decimal("3.0"),
        "waiting_period_days": 5,
    },
    "tiers": {
        1: {
            "weekly_premium_rate": Decimal("0.05"),
            "coverage_percent": Decimal("0.50"),
            "weekly_cap_multiplier": Decimal("2.0"),
            "period_cap_multiplier": Decimal("6.0"),
            "tier_multiplier": Decimal("1.0"),
            "waiting_period_days": 7,
        },
        2: {
            "weekly_premium_rate": Decimal("0.08"),
            "coverage_percent": Decimal("0.70"),
            "weekly_cap_multiplier": Decimal("3.0"),
            "period_cap_multiplier": Decimal("8.0"),
            "tier_multiplier": Decimal("1.4"),
            "waiting_period_days": 5,
        },
        3: {
            "weekly_premium_rate": Decimal("0.11"),
            "coverage_percent": Decimal("0.90"),
            "weekly_cap_multiplier": Decimal("4.0"),
            "period_cap_multiplier": Decimal("10.0"),
            "tier_multiplier": Decimal("1.8"),
            "waiting_period_days": 3,
        },
    },
}
VARIABLE_MONETARY_RISK_FACTORS = {
    "tight": Decimal("0.20"),
    "default": Decimal("0.15"),
    "comfortable": Decimal("0.12"),
}

POLICY_MODES: Dict[str, Dict[str, Any]] = {
    "tight": {
        "label": "Tight",
        "summary": "More budgeting pressure",
        "description": "A leaner economy with less surplus and more deliberate spending.",
        "ratios": {
            "rent_weekly": {"min": 2.25, "max": 2.75, "recommended": 2.50},
            "utilities_weekly": {"min": 0.07, "max": 0.12, "recommended": 0.095},
            "insurance_weekly": {"min": 0.06, "max": 0.14, "recommended": 0.09},
            "insurance_coverage_multiplier": {"min": 2.5, "max": 4.0, "recommended": 3.25},
            "insurance_period_cap_multiplier": {"min": 5.0, "max": 8.0, "recommended": 6.5},
            "insurance_waiting_period_days": {"min": 10, "max": 14, "recommended": 10},
            "fine_weekly": {"min": 0.07, "max": 0.18, "recommended": 0.11},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.04},
                "premium": {"min": 0.04, "max": 0.12},
                "luxury": {"min": 0.12, "max": 0.24},
            },
            "savings_weekly": {"min": 0.05, "target": 0.05},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.07,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
    "default": {
        "label": "Default",
        "summary": "Balanced economy",
        "description": "The standard baseline with moderate pressure and stable survival margins.",
        "ratios": {
            "rent_weekly": {"min": 2.00, "max": 2.50, "recommended": 2.25},
            "utilities_weekly": {"min": 0.05, "max": 0.10, "recommended": 0.075},
            "insurance_weekly": {"min": 0.05, "max": 0.12, "recommended": 0.08},
            "insurance_coverage_multiplier": {"min": 3.0, "max": 5.0, "recommended": 4.0},
            "insurance_period_cap_multiplier": {"min": 6.0, "max": 10.0, "recommended": 8.0},
            "insurance_waiting_period_days": {"min": 7, "max": 7, "recommended": 7},
            "fine_weekly": {"min": 0.05, "max": 0.15, "recommended": 0.10},
            "store_tiers": {
                "basic": {"min": 0.01, "max": 0.03},
                "standard": {"min": 0.02, "max": 0.05},
                "premium": {"min": 0.05, "max": 0.15},
                "luxury": {"min": 0.15, "max": 0.30},
            },
            "savings_weekly": {"min": 0.10, "target": 0.10},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.06,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
    "comfortable": {
        "label": "Comfortable",
        "summary": "More breathing room",
        "description": "A more forgiving economy with lower fixed pressure and larger student margin.",
        "ratios": {
            "rent_weekly": {"min": 1.75, "max": 2.25, "recommended": 2.00},
            "utilities_weekly": {"min": 0.04, "max": 0.08, "recommended": 0.06},
            "insurance_weekly": {"min": 0.04, "max": 0.10, "recommended": 0.07},
            "insurance_coverage_multiplier": {"min": 4.0, "max": 6.0, "recommended": 5.0},
            "insurance_period_cap_multiplier": {"min": 8.0, "max": 12.0, "recommended": 10.0},
            "insurance_waiting_period_days": {"min": 3, "max": 7, "recommended": 5},
            "fine_weekly": {"min": 0.04, "max": 0.12, "recommended": 0.08},
            "store_tiers": {
                "basic": {"min": 0.02, "max": 0.04},
                "standard": {"min": 0.03, "max": 0.06},
                "premium": {"min": 0.06, "max": 0.18},
                "luxury": {"min": 0.18, "max": 0.35},
            },
            "savings_weekly": {"min": 0.15, "target": 0.175},
        },
        "insurance_transaction_defaults": {
            "base_rate": 0.05,
            "non_tiered": {"coverage_percent": 0.50},
            "tiers": {
                1: {"coverage_percent": 0.50, "period_cap_multiplier": 6.0, "waiting_period_days": 7},
                2: {"coverage_percent": 0.70, "period_cap_multiplier": 8.0, "waiting_period_days": 5},
                3: {"coverage_percent": 0.90, "period_cap_multiplier": 10.0, "waiting_period_days": 3},
            },
        },
    },
}


def normalize_policy_mode(value: Optional[str]) -> str:
    mode = (value or POLICY_MODE_DEFAULT).strip().lower()
    return mode if mode in POLICY_MODES else POLICY_MODE_DEFAULT


def get_policy_profile(mode: Optional[str]) -> Dict[str, Any]:
    return POLICY_MODES[normalize_policy_mode(mode)]


def get_transaction_coverage_default(mode: Optional[str]) -> Decimal:
    return TRANSACTION_DEFAULTS["non_tiered"]["coverage_percent"]


def get_tier_waiting_period_days(tier_rank: Optional[int]) -> int:
    try:
        normalized_rank = int(tier_rank) if tier_rank is not None else None
    except (TypeError, ValueError):
        normalized_rank = None
    return int(TIER_WAITING_PERIOD_DAYS.get(normalized_rank, TRANSACTION_DEFAULTS["non_tiered"]["waiting_period_days"]))


def get_variable_monetary_risk_factor(mode: Optional[str]) -> Decimal:
    return VARIABLE_MONETARY_RISK_FACTORS.get(normalize_policy_mode(mode), VARIABLE_MONETARY_RISK_FACTORS[POLICY_MODE_DEFAULT])


def get_transaction_tier_defaults(
    mode: Optional[str],
    tier_rank: int,
    cwi: Optional[Decimal] = None,
    *,
    base_premium: Optional[Decimal] = None,
    billing_weeks: int = 1,
) -> Dict[str, Any]:
    tier_defaults = TRANSACTION_DEFAULTS["tiers"].get(int(tier_rank), TRANSACTION_DEFAULTS["non_tiered"])
    weekly_premium_rate = Decimal(str(tier_defaults["weekly_premium_rate"]))
    coverage_percent = Decimal(str(tier_defaults["coverage_percent"]))
    weekly_cap_multiplier = Decimal(str(tier_defaults["weekly_cap_multiplier"]))
    period_cap_multiplier = Decimal(str(tier_defaults.get("period_cap_multiplier", weekly_cap_multiplier)))
    tier_multiplier = Decimal(str(tier_defaults.get("tier_multiplier", "1.0")))
    resolved_premium = None
    if base_premium is not None:
        resolved_premium = Decimal(str(base_premium)).quantize(Decimal("0.01"))
    elif cwi is not None:
        resolved_premium = (Decimal(str(cwi)) * weekly_premium_rate).quantize(Decimal("0.01"))
    weekly_cap = None
    max_payout_per_period = None
    normalized_weeks = max(int(billing_weeks or 1), 1)
    if resolved_premium is not None:
        weekly_cap = (resolved_premium * weekly_cap_multiplier).quantize(Decimal("0.01"))
        max_payout_per_period = (weekly_cap * Decimal(str(normalized_weeks))).quantize(Decimal("0.01"))

    return {
        "weekly_premium_rate": weekly_premium_rate,
        "base_premium": resolved_premium,
        "coverage_percent": coverage_percent,
        "tier_multiplier": tier_multiplier,
        "period_cap_multiplier": period_cap_multiplier,
        "weekly_cap_multiplier": weekly_cap_multiplier,
        "weekly_cap": weekly_cap,
        "billing_weeks": normalized_weeks,
        "waiting_period_days": int(tier_defaults["waiting_period_days"]),
        "premium": resolved_premium,
        "max_payout_per_period": max_payout_per_period,
    }


def get_feature_settings_row(teacher_id: int, block: Optional[str] = None, create: bool = False):
    if not has_app_context():
        return None

    from app.extensions import db
    from app.models import FeatureSettings

    normalized_block = block.strip().upper() if block else None

    row = None
    if normalized_block:
        row = FeatureSettings.query.filter_by(
            teacher_id=teacher_id,
            block=normalized_block,
        ).first()

    if row is None and (not normalized_block or not create):
        row = FeatureSettings.query.filter_by(
            teacher_id=teacher_id,
            block=None,
        ).first()

    if row is None and create:
        row = FeatureSettings(
            teacher_id=teacher_id,
            block=normalized_block,
        )
        db.session.add(row)
        db.session.flush()

    return row


def get_active_policy_mode(teacher_id: int, block: Optional[str] = None) -> str:
    if not has_app_context():
        return POLICY_MODE_DEFAULT

    row = get_feature_settings_row(teacher_id, block=block, create=False)
    if not row:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(row, "economy_policy_mode", POLICY_MODE_DEFAULT))
