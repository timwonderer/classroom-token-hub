from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from flask import has_app_context


POLICY_MODE_DEFAULT = "default"
FREQUENCY_WEEK_MULTIPLIERS = {
    "daily": Decimal("0.142857142857"),
    "weekly": Decimal("1.0"),
    "biweekly": Decimal("2.0"),
    "monthly": Decimal("4.348214285714"),
    "semester": Decimal("18.0"),
    "yearly": Decimal("52.0"),
}
FEATURE_FLAGS = {
    "payroll",
    "insurance",
    "banking",
    "rent",
    "hall_pass",
    "store",
}

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


def convert_weekly_amount_to_frequency(value: Optional[Decimal], frequency: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None

    normalized_frequency = (frequency or "weekly").strip().lower()
    multiplier = FREQUENCY_WEEK_MULTIPLIERS.get(normalized_frequency, FREQUENCY_WEEK_MULTIPLIERS["weekly"])
    return (Decimal(str(value)) * multiplier).quantize(Decimal("0.01"))


def get_insurance_premium_recommendation(
    mode: Optional[str],
    cwi: Optional[Decimal],
    *,
    frequency: str = "weekly",
) -> Optional[Dict[str, Any]]:
    """
    Shared premium guidance for insurance pricing.

    This helper is the backend source for the values shown in economy-health style
    recommendations and insurance setup/edit guidance. It follows the policy-mode
    profile ratios, which in turn implement the documented economics contract:
    - docs/FEATURES/ECONOMY/FEAT-ECON-001_Policy_Mode_and_Rebalancer.md
    - docs/DOMAINS/ECONOMY_DESIGN/DOM-ECON-002_Economy_Specification.md
    """
    if cwi is None:
        return None

    profile = get_policy_profile(mode)
    insurance_weekly = profile.get("ratios", {}).get("insurance_weekly", {})
    cwi_decimal = Decimal(str(cwi)).quantize(Decimal("0.01"))
    weekly_min = (cwi_decimal * Decimal(str(insurance_weekly.get("min", 0.05)))).quantize(Decimal("0.01"))
    weekly_max = (cwi_decimal * Decimal(str(insurance_weekly.get("max", 0.12)))).quantize(Decimal("0.01"))
    weekly_recommended = (
        cwi_decimal * Decimal(str(insurance_weekly.get("recommended", 0.08)))
    ).quantize(Decimal("0.01"))

    return {
        "frequency": (frequency or "weekly").strip().lower(),
        "cwi": cwi_decimal,
        "min_weekly": weekly_min,
        "max_weekly": weekly_max,
        "recommended_weekly": weekly_recommended,
        "min": convert_weekly_amount_to_frequency(weekly_min, frequency),
        "max": convert_weekly_amount_to_frequency(weekly_max, frequency),
        "recommended": convert_weekly_amount_to_frequency(weekly_recommended, frequency),
    }


def _resolve_join_code_for_block(teacher_id: int, block: Optional[str]) -> Optional[str]:
    if not has_app_context() or not block:
        return None

    from app.models import TeacherBlock

    row = (
        TeacherBlock.query.with_entities(TeacherBlock.join_code)
        .filter(
            TeacherBlock.teacher_id == teacher_id,
            TeacherBlock.block == block,
            TeacherBlock.join_code.isnot(None),
        )
        .first()
    )
    return row[0] if row and row[0] else None


def resolve_class_scope(
    teacher_id: int,
    *,
    block: Optional[str] = None,
    join_code: Optional[str] = None,
) -> Optional[dict[str, str]]:
    if not has_app_context() or not teacher_id:
        return None

    from app.models import ClassEconomy, TeacherBlock

    normalized_block = block.strip().upper() if block else None
    normalized_join_code = (join_code or "").strip().upper() or None

    if normalized_block and not normalized_join_code:
        normalized_join_code = _resolve_join_code_for_block(teacher_id, normalized_block)
    if normalized_join_code and not normalized_block:
        block_row = (
            TeacherBlock.query.with_entities(TeacherBlock.block)
            .filter(
                TeacherBlock.teacher_id == teacher_id,
                TeacherBlock.join_code == normalized_join_code,
                TeacherBlock.block.isnot(None),
            )
            .order_by(TeacherBlock.id.asc())
            .first()
        )
        normalized_block = block_row[0].strip().upper() if block_row and block_row[0] else None

    if not normalized_join_code or not normalized_block:
        return None

    class_row = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(
        join_code=normalized_join_code,
        teacher_id=teacher_id,
    ).first()
    if not class_row or not class_row[0]:
        return None

    return {
        "join_code": normalized_join_code,
        "class_id": class_row[0],
        "block": normalized_block,
    }


def resolve_feature_class(
    teacher_id: int,
    feature_name: str,
    *,
    block: Optional[str] = None,
    join_code: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if feature_name not in FEATURE_FLAGS:
        raise ValueError(f"Unknown feature flag: {feature_name}")

    scope = resolve_class_scope(teacher_id, block=block, join_code=join_code)
    if not scope:
        return None

    from app.models import ClassFeature

    enabled = feature_name in ClassFeature.enabled_names_for_class(scope["class_id"])

    return {
        **scope,
        "enabled": bool(enabled),
        "feature_name": feature_name,
    }


def get_class_feature_settings(
    teacher_id: int,
    *,
    block: Optional[str] = None,
    join_code: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not has_app_context():
        return None

    from app.models import ClassFeature

    scope = resolve_class_scope(teacher_id, block=block, join_code=join_code)
    if not scope:
        return None
    return {
        **scope,
        "features": ClassFeature.feature_map_for_class(scope["class_id"]),
    }


def replace_enabled_class_features(class_id: str, enabled_features: set[str]) -> None:
    from app.extensions import db
    from app.models import ClassFeature

    valid_features = set(ClassFeature.feature_names())
    requested_features = {name for name in enabled_features if name in valid_features}
    existing_rows = ClassFeature.query.filter_by(class_id=class_id).all()
    existing_names = {row.feature_name for row in existing_rows}

    for row in existing_rows:
        if row.feature_name not in requested_features:
            db.session.delete(row)

    missing_names = requested_features - existing_names
    for feature_name in sorted(missing_names):
        db.session.add(ClassFeature(class_id=class_id, feature_name=feature_name))


def get_feature_settings_row(
    teacher_id: int,
    block: Optional[str] = None,
    join_code: Optional[str] = None,
    create: bool = False,
):
    if not has_app_context():
        return None

    from app.extensions import db
    from app.models import FeatureSettings

    scope = resolve_class_scope(teacher_id, block=block, join_code=join_code)
    if not scope:
        return None

    row = FeatureSettings.query.filter_by(
        teacher_id=teacher_id,
        class_id=scope["class_id"],
    ).first()
    if row or not create:
        return row

    row = FeatureSettings(
        teacher_id=teacher_id,
        join_code=scope["join_code"],
        class_id=scope["class_id"],
        block=scope["block"],
    )
    db.session.add(row)
    db.session.flush()
    return row


def get_active_policy_mode(teacher_id: int, block: Optional[str] = None, join_code: Optional[str] = None) -> str:
    if not has_app_context():
        return POLICY_MODE_DEFAULT

    row = get_feature_settings_row(teacher_id, block=block, join_code=join_code, create=False)
    if not row:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(row, "economy_policy_mode", POLICY_MODE_DEFAULT))
