"""Display text for configuration transfer previews (SPEC-UI-001 §VII: builders format, templates print)."""
from datetime import date
from decimal import Decimal
from app.services.configuration_fields import SCHEMAS
from app.utils.temporal_display import format_local_date

FAMILY_LABELS = {"economy": "Economy", "banking": "Banking", "payroll": "Payroll", "rent": "Rent",
    "store": "Store", "insurance": "Insurance", "hall_pass": "Hall passes"}
FAMILY_ICONS = {"economy": "tune", "banking": "account_balance", "payroll": "payments", "rent": "home",
    "store": "storefront", "insurance": "health_and_safety", "hall_pass": "directions_walk"}

FIELD_LABELS = {
    "economy_policy_mode": "Policy mode", "expected_weekly_hours": "Expected work time",
    "interest_rate": "Savings interest", "interest_calculation_type": "Interest type",
    "compound_frequency": "Compounds", "interest_accrual_frequency": "Accrues", "interest_payout_frequency": "Pays out",
    "flat_overdraft_fee": "Overdraft fee", "progressive_overdraft_fee": "Progressive overdraft fees",
    "overdraft_protection_enabled": "Overdraft protection",
    "pay_rate": "Pay rate", "overtime_threshold": "Overtime after", "max_time_per_day": "Maximum paid time per day",
    "pay_schedule_type": "Pay schedule", "first_pay_date": "First payday",
    "rent_amount": "Rent", "frequency_type": "Charged", "custom_frequency_value": "Charged every",
    "due_day_of_month": "Due day of month", "grace_period_days": "Grace period", "late_penalty_amount": "Late fee",
    "late_penalty_type": "Late fee type", "late_penalty_frequency_days": "Late fee repeats every",
    "bill_preview_enabled": "Show upcoming bill", "bill_preview_days": "Bill preview",
    "allow_incremental_payment": "Partial payments", "prevent_purchase_when_late": "Block purchases when late",
    "cycle_length_days": "Cycle length", "first_rent_due_date": "First due date",
    "bypass_cwi_warnings": "Ignore CWI warnings",
    "description": "Description", "price": "Price", "economic_role": "Economic role", "item_type": "Item type",
    "inventory_total": "Inventory", "holding_limit": "Limit per student", "direct_purchase_allowed": "Students can buy directly",
    "available_with_overdue_obligations": "Available with overdue bills", "activation_at": "Available from",
    "auto_delist_date": "Available until", "auto_expiry_days": "Expires after", "is_long_term_goal": "Long-term goal",
    "bulk_discount_enabled": "Bulk discount", "bulk_discount_quantity": "Bulk discount quantity",
    "bulk_discount_percentage": "Bulk discount", "collective_goal_type": "Collective goal type",
    "collective_goal_target": "Collective goal target", "collective_goal_expires_at": "Collective goal ends",
    "redemption_prompt": "Redemption prompt",
    "insurance_type": "Coverage type", "tier_level": "Tier rank", "premium": "Premium", "charge_frequency": "Billed",
    "reimbursement_percentage": "Percent of loss covered", "payout_multiple": "Payout multiple",
    "claims_per_week_equivalent": "Claims per week", "claim_window_days": "Claim window",
    "claimable_dates_per_week_equivalent": "Claimable days per week", "waiting_period_days": "Waiting period",
    "nonpayment_mode": "If unpaid", "cancel_after_days": "Cancel after", "tier_name": "Tier name",
    "marketing_badge": "Badge",
}
VALUE_LABELS = {"biweekly": "Bi-weekly"}
MONEY = {"flat_overdraft_fee", "rent_amount", "late_penalty_amount", "price", "premium"}
PERCENT = {"reimbursement_percentage", "bulk_discount_percentage"}
DATES = {"first_pay_date", "first_rent_due_date", "activation_at", "auto_delist_date", "collective_goal_expires_at"}
# Shown inside another row's value, never as their own row.
FOLDED = {"overtime_threshold_unit", "max_time_per_day_unit", "custom_frequency_unit", "bulk_discount_quantity",
    "name", "title"}


def _number(value):
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money(value):
    return f"${Decimal(value):,.2f}"


def _plural(count, unit):
    unit = unit.rstrip("s")
    return f"{_number(count)} {unit if Decimal(count) == 1 else unit + 's'}"


def _text(value):
    return VALUE_LABELS.get(value) or value.replace("_", " ").capitalize()


def value_text(field, value, row):
    if value is None:
        return "Not set"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if field == "pay_rate":  # stored per minute; teachers set and read it per hour
        return f"{_money(Decimal(value) * 60)} per hour"
    if field == "expected_weekly_hours":
        return f"{_plural(value, 'hour')} per week"
    if field == "interest_rate":
        return f"{_number(Decimal(value) * 100)}% per year"
    if field in ("overtime_threshold", "max_time_per_day"):
        return _plural(value, row.get(field + "_unit") or "minute")
    if field == "custom_frequency_value":
        return _plural(value, row.get("custom_frequency_unit") or "day")
    if field == "progressive_overdraft_fee":
        return ", ".join(f"Tier {key[-1]}: {_money(amount)}" for key, amount in sorted(value.items()))
    if field == "bulk_discount_percentage":
        quantity = row.get("bulk_discount_quantity")
        return f"{_number(value)}% off" + (f" when buying {quantity} or more" if quantity else "")
    if field in MONEY:
        return _money(value)
    if field in PERCENT:
        return f"{_number(value)}%"
    if field in DATES:
        return format_local_date(date.fromisoformat(value), "long")
    if field.endswith("_days"):
        return _plural(value, "day")
    if isinstance(value, str):
        return _text(value)
    return _number(value)


def rows(values, family):
    order = list(SCHEMAS.get(family, values))  # files carry sorted keys; show the settings page's order
    return [{"label": FIELD_LABELS.get(field, field.replace("_", " ").capitalize()), "value": value_text(field, values[field], values)}
        for field in sorted(values, key=lambda f: order.index(f) if f in order else len(order)) if field not in FOLDED]


def preview_sections(groups):
    """One section per family; store items, insurance policies and hall passes get one block each."""
    sections = []
    for family, values in groups.items():
        if family == "store":
            blocks = [{"heading": item["name"], "rows": rows(item, family)} for item in values]
        elif family == "insurance":
            blocks = [{"heading": " — ".join(filter(None, [group["name"], policy["title"] or "Insurance policy"])),
                "rows": rows(policy, family)} for group in values for policy in group["policies"]]
        elif family == "hall_pass":
            passes = [{"label": item["pass_name"],
                "value": f"Up to {item['max_queue']} waiting · " + ("uses a pass" if item["consume_pass"] else "free")}
                for item in values["pass_type_payload"]]
            blocks = [{"heading": None, "rows": [{"label": "Waiting list limit", "value": value_text("max_queue_limit", values["max_queue_limit"], values)}] + passes}]
        else:
            blocks = [{"heading": None, "rows": rows(values, family)}]
        sections.append({"title": FAMILY_LABELS.get(family, family), "icon": FAMILY_ICONS.get(family, "settings"), "blocks": blocks})
    return sections
