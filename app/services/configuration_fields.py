"""Closed portable value schemas; identifiers and operational state have no entries."""
from datetime import date
from decimal import Decimal, InvalidOperation
from app.services.configuration_artifact import ConfigurationError
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

# Decimal values travel as strings; dates represent the class calendar, not UTC.
SCHEMAS = {
    "economy": {"economy_policy_mode": "text", "expected_weekly_hours": "decimal"},
    "banking": {"interest_rate": "decimal", "interest_calculation_type": "text",
        "compound_frequency": "text", "interest_accrual_frequency": "text",
        "interest_payout_frequency": "text", "flat_overdraft_fee": "decimal",
        "progressive_overdraft_fee": "tiers", "overdraft_protection_enabled": "bool"},
    "payroll": {"pay_rate": "decimal", "overtime_threshold": "decimal",
        "overtime_threshold_unit": "text", "max_time_per_day": "decimal",
        "max_time_per_day_unit": "text", "pay_schedule_type": "text", "first_pay_date": "date"},
    "rent": {"rent_amount": "decimal", "frequency_type": "text", "custom_frequency_value": "int",
        "custom_frequency_unit": "text", "due_day_of_month": "int", "grace_period_days": "int",
        "late_penalty_amount": "decimal", "late_penalty_type": "text", "late_penalty_frequency_days": "int",
        "bill_preview_enabled": "bool", "bill_preview_days": "int", "allow_incremental_payment": "bool",
        "prevent_purchase_when_late": "bool", "cycle_length_days": "int", "first_rent_due_date": "date",
        "bypass_cwi_warnings": "bool"},
    "store": {"name": "text", "description": "text", "price": "decimal", "economic_role": "text",
        "item_type": "text", "inventory_total": "int", "holding_limit": "int",
        "direct_purchase_allowed": "bool", "available_with_overdue_obligations": "bool",
        "activation_at": "date", "auto_delist_date": "end_date", "auto_expiry_days": "int",
        "is_long_term_goal": "bool", "bypass_cwi_warnings": "bool", "bulk_discount_enabled": "bool",
        "bulk_discount_quantity": "int", "bulk_discount_percentage": "decimal",
        "collective_goal_type": "text", "collective_goal_target": "int", "collective_goal_expires_at": "end_date",
        "redemption_prompt": "text"},
    "insurance": {"insurance_type": "text", "tier_level": "int", "premium": "decimal",
        "charge_frequency": "text", "reimbursement_percentage": "decimal", "payout_multiple": "decimal",
        "claims_per_week_equivalent": "decimal", "claim_window_days": "int",
        "claimable_dates_per_week_equivalent": "decimal", "waiting_period_days": "int",
        "bill_preview_days": "int", "nonpayment_mode": "text", "cancel_after_days": "int",
        "title": "text", "description": "text", "tier_name": "text", "marketing_badge": "text"},
}
SCHEDULES = {
    "payroll": ("pay_schedule_type", "first_pay_date"),
    "rent": ("frequency_type", "custom_frequency_value", "custom_frequency_unit", "first_rent_due_date", "due_day_of_month"),
    "banking": ("interest_calculation_type", "compound_frequency", "interest_accrual_frequency", "interest_payout_frequency"),
    "store": ("activation_at", "auto_delist_date", "collective_goal_expires_at"),
}


def project(row, family, context):
    result = {}
    for field, kind in SCHEMAS[family].items():
        value = getattr(row, field)
        if value is not None:
            if kind in ("date", "end_date"):
                day = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context, primitive="localize_timestamp",
                    timestamp=value).result["evaluation_date"]
                if kind == "end_date":
                    day = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
                        canonical_execution_context=context, primitive="shift_calendar_days", date=day, days=-1).shifted_date
                value = day.isoformat()
            elif kind == "decimal":
                value = str(value)
            elif kind == "tiers":
                value = {key: str(amount) for key, amount in value.items()}
        result[field] = value
    return result


def decode(values, family, context):
    schema = SCHEMAS[family]
    if not isinstance(values, dict) or set(values) != set(schema):
        raise ConfigurationError("Unexpected or missing configuration fields")
    result = {}
    for field, kind in schema.items():
        value = values[field]
        if value is not None:
            if kind == "bool" and type(value) is not bool:
                raise ConfigurationError(f"{field} must be true or false")
            if kind == "int" and (type(value) is not int or value < 0):
                raise ConfigurationError(f"{field} must be a nonnegative whole number")
            if kind in ("decimal", "text", "date", "end_date") and not isinstance(value, str):
                raise ConfigurationError(f"{field} must be text")
            if kind == "tiers":
                if not isinstance(value, dict) or set(value) != {"tier_1", "tier_2", "tier_3"}:
                    raise ConfigurationError("Overdraft tiers must have exactly three rates")
                for amount in value.values():
                    try:
                        if not isinstance(amount, str) or not Decimal(amount).is_finite() or Decimal(amount) < 0:
                            raise ValueError
                    except (InvalidOperation, ValueError):
                        raise ConfigurationError("Invalid overdraft tier rate")
            if kind == "decimal":
                try:
                    value = Decimal(value)
                    if not value.is_finite() or value < 0:
                        raise ValueError
                except (InvalidOperation, ValueError):
                    raise ConfigurationError(f"{field} must be a finite nonnegative number")
            elif kind in ("date", "end_date"):
                try:
                    day = date.fromisoformat(value)
                except ValueError:
                    raise ConfigurationError(f"{field} must be a calendar date")
                resolved = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context, primitive="evaluation_day_boundaries", evaluation_date=day)
                value = resolved.boundary_end_utc if kind == "end_date" else resolved.boundary_start_utc
        result[field] = value
    return result
