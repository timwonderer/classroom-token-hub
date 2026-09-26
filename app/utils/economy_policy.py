from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from flask import has_app_context
from app.utils.join_code import get_display_join_code


POLICY_MODE_DEFAULT = "default"
AVERAGE_WEEKS_PER_MONTH = Decimal("4.348214285714")
FREQUENCY_WEEK_MULTIPLIERS = {
    "daily": Decimal("0.142857142857"),
    "weekly": Decimal("1.0"),
    "biweekly": Decimal("2.0"),
    # Bound to the constant rather than re-stated: a second spelling of the
    # month length makes two price bands out of one policy ratio (INV-ARC-022).
    "monthly": AVERAGE_WEEKS_PER_MONTH,
    "semester": Decimal("18.0"),
    "yearly": Decimal("52.0"),
}
# NOTE: The legacy TRANSACTION_* tier constants (base-premium × tier-multiplier
# pricing model) were removed as part of the SPEC-ECON-003 insurance migration.
# The canonical insurance economic model (deterministic per-(product, tier, mode)
# presets) now lives in app/services/economic_engine.py (resolve_insurance).

# Store economic role reference bands as a share of CWI (SPEC-ECON-003 §4.7).
# These sit outside POLICY_MODES on purpose: the spec's table has no policy-mode
# axis, so the same band applies in tight, default, and comfortable.
STORE_ROLE_RATIOS: Dict[str, Dict[str, float]] = {
    "necessity": {"min": 0.01, "max": 0.10},
    "convenience": {"min": 0.11, "max": 0.20},
    "add_on": {"min": 0.21, "max": 0.30},
}

FEATURE_FLAGS = {
    "payroll",
    "insurance",
    "banking",
    "rent",
    "hall_pass",
    "store",
}

# Every band here is transcribed from a numbered SPEC-ECON-003 §4 table: rent
# §4.3, fines §4.5, collective goals §4.6, savings §4.2. ``recommended`` is the
# band midpoint, which §4.8 names as the value a rebalance proposes; it is a
# proposal, never a bound.
#
# There is no utilities band. v2 has no utilities feature and SPEC-ECON-003 does
# not model one, so carrying a band for it would make an unreachable number look
# authoritative.
POLICY_MODES: Dict[str, Dict[str, Any]] = {
    "tight": {
        "label": "Tight",
        "summary": "More budgeting pressure",
        "description": "A leaner economy with less surplus and more deliberate spending.",
        "ratios": {
            "rent_weekly": {"min": 0.30, "max": 0.40, "recommended": 0.35},
            "fine_weekly": {"min": 0.05, "max": 0.10, "recommended": 0.075},
            "collective_goal": {"min": 1.0, "max": 3.0},
            "savings_weekly": {"min": 0.05, "target": 0.05},
        },
    },
    "default": {
        "label": "Default",
        "summary": "Balanced economy",
        "description": "The standard baseline with moderate pressure and stable survival margins.",
        "ratios": {
            "rent_weekly": {"min": 0.35, "max": 0.50, "recommended": 0.425},
            "fine_weekly": {"min": 0.05, "max": 0.12, "recommended": 0.085},
            "collective_goal": {"min": 1.0, "max": 5.0},
            "savings_weekly": {"min": 0.10, "target": 0.10},
        },
    },
    "comfortable": {
        "label": "Comfortable",
        "summary": "More breathing room",
        "description": "A more forgiving economy with lower fixed pressure and larger student margin.",
        "ratios": {
            "rent_weekly": {"min": 0.40, "max": 0.55, "recommended": 0.475},
            "fine_weekly": {"min": 0.07, "max": 0.15, "recommended": 0.11},
            "collective_goal": {"min": 1.5, "max": 7.0},
            "savings_weekly": {"min": 0.15, "target": 0.15},
        },
    },
}


def normalize_policy_mode(value: Optional[str]) -> str:
    mode = (value or POLICY_MODE_DEFAULT).strip().lower()
    return mode if mode in POLICY_MODES else POLICY_MODE_DEFAULT


def get_policy_profile(mode: Optional[str]) -> Dict[str, Any]:
    return POLICY_MODES[normalize_policy_mode(mode)]


def _quantize_money(value: Decimal) -> Decimal:
    # Half-up, matching the Economic Engine's ``_money``. The default context
    # rounds half-to-even, so a band landing on an exact half-cent (CWI 337.50 at
    # 7%) came out a cent apart from the engine's figure for the same band.
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def weeks_per_period(
    frequency: Optional[str],
    *,
    custom_frequency_value: Optional[int] = None,
    custom_frequency_unit: Optional[str] = None,
) -> Decimal:
    """How many weeks one period of ``frequency`` spans.

    Every weekly policy ratio reaches a teacher-visible amount through this one
    conversion, so a band shown on a settings page and the band the balance
    warning judges against cannot pick up different rounding on the way.
    """
    normalized_frequency = (frequency or "weekly").strip().lower()
    if normalized_frequency == "custom":
        unit = (custom_frequency_unit or "days").strip().lower()
        count = Decimal(str(custom_frequency_value or 1))
        if unit == "weeks":
            return count
        if unit == "months":
            return AVERAGE_WEEKS_PER_MONTH * count
        return count / Decimal("7")

    return FREQUENCY_WEEK_MULTIPLIERS.get(normalized_frequency, FREQUENCY_WEEK_MULTIPLIERS["weekly"])


def frequency_label(
    frequency: Optional[str],
    *,
    custom_frequency_value: Optional[int] = None,
    custom_frequency_unit: Optional[str] = None,
) -> str:
    """The human phrasing of a billing cadence, e.g. ``per 2 weeks``."""
    normalized_frequency = (frequency or "weekly").strip().lower()
    if normalized_frequency == "custom":
        count = int(custom_frequency_value or 1)
        unit = (custom_frequency_unit or "days").strip().lower()
        unit = unit.rstrip("s") if count == 1 else (unit if unit.endswith("s") else f"{unit}s")
        return f"per {count} {unit}"

    return {
        "daily": "per day",
        "weekly": "per week",
        "biweekly": "per 2 weeks",
        "monthly": "per month",
        "semester": "per semester",
        "yearly": "per year",
    }.get(normalized_frequency, normalized_frequency)


def scale_band(
    cwi: Optional[Decimal],
    ratios: Dict[str, Any],
    weeks: Decimal = Decimal("1"),
) -> Dict[str, Decimal]:
    """Turn weekly CWI ratios into per-period money, rounding exactly once.

    Rounding the weekly figure and then scaling it produces a different band
    than scaling and then rounding, which is how the Economic Engine card and
    the rent page came to disagree by a cent or two.
    """
    cwi_decimal = _quantize_money(Decimal(str(cwi or 0)))
    return {
        key: _quantize_money(cwi_decimal * Decimal(str(ratio)) * weeks)
        for key, ratio in ratios.items()
    }


def get_price_recommendation_context(mode: Optional[str], cwi: Optional[Decimal]) -> Optional[Dict[str, Any]]:
    """
    Central recommendation source for all economy-policy pricing guidance.
    """
    if cwi is None:
        return None

    profile = get_policy_profile(mode)
    ratios = profile["ratios"]
    cwi_decimal = _quantize_money(Decimal(str(cwi)))

    def store_roles() -> Dict[str, Dict[str, float]]:
        return {
            role: {
                "min": float(_quantize_money(cwi_decimal * Decimal(str(bounds["min"])))),
                "max": float(_quantize_money(cwi_decimal * Decimal(str(bounds["max"])))),
            }
            for role, bounds in STORE_ROLE_RATIOS.items()
        }

    # NOTE (SPEC-ECON-003 migration): insurance pricing guidance is no longer
    # produced here. Insurance recommendations are owned exclusively by the
    # Economic Engine (app/services/economic_engine.resolve_insurance), which is
    # product- and tier-aware. This legacy builder retains only the
    # rent/fines/store/savings surfaces still pending their own Engine migration.
    rent_ratios = ratios["rent_weekly"]
    rent_weekly = scale_band(cwi_decimal, rent_ratios)
    rent_monthly = scale_band(cwi_decimal, rent_ratios, AVERAGE_WEEKS_PER_MONTH)
    fine_weekly = scale_band(cwi_decimal, ratios["fine_weekly"])
    savings = ratios["savings_weekly"]

    return {
        "policy_mode": normalize_policy_mode(mode),
        "policy_label": profile["label"],
        "cwi": float(cwi_decimal),
        "rent_weekly": {key: float(value) for key, value in rent_weekly.items()},
        "rent": {key: float(value) for key, value in rent_monthly.items()},
        # The policy ratios themselves, so a "% of CWI" line is read rather than
        # reverse-engineered from an already-rounded dollar band.
        "rent_ratios": {key: float(value) for key, value in rent_ratios.items()},
        "fine": {key: float(value) for key, value in fine_weekly.items()},
        "store_roles": store_roles(),
        "min_weekly_savings": float(_quantize_money(cwi_decimal * Decimal(str(savings["min"])))),
    }


def resolve_class_scope(
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, str]]:
    if not has_app_context() or not user_id:
        return None

    from app.models import ClassEconomy

    normalized_class_id = str(class_id).strip() if class_id else None
    if not normalized_class_id:
        return None

    class_row = (
        ClassEconomy.query.with_entities(ClassEconomy.class_id, ClassEconomy.section)
        .filter(
            ClassEconomy.teacher_user_id == user_id,
            ClassEconomy.class_id == normalized_class_id,
        )
        .first()
    )
    if not class_row:
        return None

    return {
        "class_id": class_row.class_id,
        "join_code": get_display_join_code(class_row.class_id),
        "block": class_row.section,
    }


def resolve_feature_class(
    user_id: int,
    feature_name: str,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if feature_name not in FEATURE_FLAGS:
        raise ValueError(f"Unknown feature flag: {feature_name}")

    scope = resolve_class_scope(user_id, class_id=class_id)
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
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not has_app_context():
        return None

    from app.models import ClassFeature

    scope = resolve_class_scope(user_id, class_id=class_id)
    if not scope:
        return None
    return {
        **scope,
        "features": ClassFeature.feature_map_for_class(scope["class_id"]),
    }


def replace_enabled_class_features(class_id: str, enabled_features: set[str]) -> None:
    from app.extensions import db
    from app.models import ClassFeature, EconomicEngine
    from sqlalchemy import desc

    valid_features = set(ClassFeature.feature_names())
    requested_features = {name for name in enabled_features if name in valid_features}
    # Payroll is mandatory in v2 class feature gating.
    requested_features.add("payroll")

    # Get the current economic version for this class
    latest_engine = EconomicEngine.query.filter_by(
        class_id=class_id
    ).order_by(desc(EconomicEngine.created_at)).first()

    if not latest_engine:
        # Create default engine if missing
        latest_engine = EconomicEngine(
            class_id=class_id,
            economic_version_id="v1",
            economy_policy_mode="default",
        )
        db.session.add(latest_engine)
        db.session.flush()

    economic_version_id = latest_engine.economic_version_id

    # Get currently enabled features for this class
    currently_enabled = ClassFeature.enabled_names_for_class(class_id)

    # For each feature, if the requested state differs from current state, append a row
    for feature_name in sorted(valid_features | requested_features):
        is_currently_enabled = feature_name in currently_enabled
        should_be_enabled = feature_name in requested_features

        if is_currently_enabled != should_be_enabled:
            # State changed; append new row to timeline
            if should_be_enabled:
                # Enable: set version_id to current version
                db.session.add(ClassFeature(
                    class_id=class_id,
                    feature=feature_name,
                    economic_version_id=economic_version_id
                ))
            else:
                # Disable: set version_id to None
                db.session.add(ClassFeature(
                    class_id=class_id,
                    feature=feature_name,
                    economic_version_id=None
                ))


def get_feature_settings_row(
    user_id: int,
    class_id: Optional[str] = None,
    create: bool = False,
):
    if not has_app_context():
        return None

    scope = resolve_class_scope(user_id, class_id=class_id)
    if not scope:
        return None
    return get_feature_settings_row_for_class(
        scope["class_id"],
        create=create,
    )


def get_feature_settings_row_for_class(
    class_id: str | None,
    *,
    create: bool = False,
):
    """Resolve feature settings by explicit canonical class_id context.

    This helper is class-authoritative and never infers scope from legacy keys.
    """
    if not has_app_context() or not class_id:
        return None

    from app.extensions import db
    from app.models import FeatureSettings

    row = FeatureSettings.query.filter_by(class_id=class_id).first()
    if row or not create:
        return row

    row = FeatureSettings(
        class_id=class_id,
    )
    db.session.add(row)
    db.session.flush()
    return row


def get_active_policy_mode(
    user_id: int,
    *,
    class_id: Optional[str] = None,
) -> str:
    if not has_app_context():
        return POLICY_MODE_DEFAULT

    row = get_feature_settings_row(user_id, class_id=class_id, create=False)
    if not row:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(row, "economy_policy_mode", POLICY_MODE_DEFAULT))


def get_active_policy_mode_for_class(class_id: Optional[str]) -> str:
    """Get the active policy mode for a class from its latest EconomicEngine version.

    Refactored in Phase 2 to get policy_mode from EconomicEngine instead of FeatureSettings.
    If no EconomicEngine version exists yet, returns the default policy mode.
    """
    if not has_app_context() or not class_id:
        return POLICY_MODE_DEFAULT

    from app.models import EconomicEngine
    from sqlalchemy import desc

    # Get the most recent EconomicEngine version for this class
    economic_engine = EconomicEngine.query.filter_by(
        class_id=class_id
    ).order_by(desc(EconomicEngine.created_at)).first()

    if not economic_engine:
        return POLICY_MODE_DEFAULT
    return normalize_policy_mode(getattr(economic_engine, "economy_policy_mode", POLICY_MODE_DEFAULT))


def resolve_feature_class_for_class(
    class_id: Optional[str],
    feature_name: str,
) -> Optional[dict[str, Any]]:
    """Resolve feature enablement by explicit canonical class_id."""
    if feature_name not in FEATURE_FLAGS:
        raise ValueError(f"Unknown feature flag: {feature_name}")
    if not has_app_context() or not class_id:
        return None

    from app.extensions import db
    from app.models import ClassFeature
    from app.models import ClassEconomy
    from app.utils.join_code import get_display_join_code

    class_row = db.session.get(ClassEconomy, class_id)
    if not class_row:
        return None

    enabled = feature_name in ClassFeature.enabled_names_for_class(class_id)
    return {
        "class_id": class_id,
        "enabled": bool(enabled),
        "feature_name": feature_name,
        "join_code": get_display_join_code(class_id),
    }


def get_class_feature_settings_for_class(
    class_id: Optional[str],
) -> Optional[dict[str, Any]]:
    """Return class feature map by explicit canonical class_id."""
    if not has_app_context() or not class_id:
        return None

    from app.models import ClassEconomy, ClassFeature

    class_exists = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(class_id=class_id).first()
    if not class_exists:
        return None

    return {
        "class_id": class_id,
        "features": ClassFeature.feature_map_for_class(class_id),
    }
