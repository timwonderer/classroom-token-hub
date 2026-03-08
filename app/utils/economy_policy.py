from __future__ import annotations

from typing import Any, Dict, Optional
from flask import has_app_context


POLICY_MODE_DEFAULT = "default"

POLICY_MODES: Dict[str, Dict[str, Any]] = {
    "tight": {
        "label": "Tight",
        "summary": "More budgeting pressure",
        "description": "A leaner economy with less surplus and more deliberate spending.",
        "ratios": {
            "rent_weekly": {"min": 0.70, "max": 0.80, "recommended": 0.75},
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
    },
    "default": {
        "label": "Default",
        "summary": "Balanced economy",
        "description": "The standard baseline with moderate pressure and stable survival margins.",
        "ratios": {
            "rent_weekly": {"min": 0.60, "max": 0.75, "recommended": 0.675},
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
    },
    "comfortable": {
        "label": "Comfortable",
        "summary": "More breathing room",
        "description": "A more forgiving economy with lower fixed pressure and larger student margin.",
        "ratios": {
            "rent_weekly": {"min": 0.50, "max": 0.65, "recommended": 0.575},
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
    },
}


def normalize_policy_mode(value: Optional[str]) -> str:
    mode = (value or POLICY_MODE_DEFAULT).strip().lower()
    return mode if mode in POLICY_MODES else POLICY_MODE_DEFAULT


def get_policy_profile(mode: Optional[str]) -> Dict[str, Any]:
    return POLICY_MODES[normalize_policy_mode(mode)]


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

    if row is None:
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
