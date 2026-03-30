from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import FeatureSettings, InsurancePolicy, RentSettings
from app.utils.time import ensure_utc, utc_now


REBALANCE_ACTIVATION_IMMEDIATE = "immediate"
REBALANCE_ACTIVATION_NEXT_RENEWAL = "next_renewal"
REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL = "next_payroll"
REBALANCE_TRIGGER_INSURANCE_RENEWAL = "insurance_renewal"


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


def _get_rent_effective_at(settings, reference_time: datetime) -> datetime:
    from app.routes.student import _add_rent_period, _calculate_rent_timeline, _get_rent_period_delta

    timeline = _calculate_rent_timeline(settings, reference_time)
    upcoming_due_date = timeline.get("upcoming_due_date")
    if upcoming_due_date is None:
        return reference_time
    return _add_rent_period(upcoming_due_date, _get_rent_period_delta(settings))


def prepare_scheduled_rebalance_changes(change_plan, *, rent_settings=None, insurance_policies=None, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    insurance_by_id = {policy.id: policy for policy in (insurance_policies or [])}
    scheduled_changes = []

    for change in change_plan:
        enriched_change = dict(change)
        effective_at = None

        if change.get("type") == "rent" and rent_settings is not None:
            effective_at = _get_rent_effective_at(rent_settings, reference_time)
        elif change.get("type") == "insurance":
            policy = insurance_by_id.get(change.get("policy_id"))
            if policy is not None:
                enriched_change["activation_event"] = REBALANCE_TRIGGER_INSURANCE_RENEWAL
                enriched_change["activation_policy_id"] = policy.id

        enriched_change["effective_at"] = _serialize_dt(effective_at)
        scheduled_changes.append(enriched_change)

    return scheduled_changes


def _get_effective_rent_settings(teacher_id, block=None, *, join_code=None):
    if join_code:
        settings = (
            RentSettings.query.filter_by(
                teacher_id=teacher_id,
                join_code=join_code,
                is_enabled=True,
            )
            .order_by(RentSettings.block.isnot(None).desc(), RentSettings.id.desc())
            .first()
        )
        if settings:
            return settings

    if block:
        settings = RentSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block,
            is_enabled=True,
        ).first()
        if settings:
            return settings

    return RentSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None,
        is_enabled=True,
    ).first()


def _apply_change_list(teacher_id, settings_row, changes, activation_mode, *, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    applied_labels = []

    for change in changes:
        change_type = change.get("type")
        if change_type == "rent":
            rent_settings = _get_effective_rent_settings(
                teacher_id,
                change.get("block"),
                join_code=change.get("join_code"),
            )
            if rent_settings:
                rent_settings.rent_amount = Decimal(str(change.get("new_value")))
                applied_labels.append("Rent")
        elif change_type == "insurance":
            policy = InsurancePolicy.query.filter_by(
                teacher_id=teacher_id,
                id=change.get("policy_id"),
                is_active=True,
            ).first()
            if policy:
                policy.premium = Decimal(str(change.get("new_value")))
                applied_labels.append(f"Insurance: {policy.title}")

    if applied_labels:
        settings_row.economy_last_rebalanced_at = reference_time
        settings_row.economy_last_rebalanced_by = teacher_id

    return applied_labels


def apply_rebalance_changes(teacher_id, settings_row, change_plan, activation_mode, *, reference_time=None):
    applied_labels = _apply_change_list(
        teacher_id,
        settings_row,
        change_plan,
        activation_mode,
        reference_time=reference_time,
    )
    settings_row.economy_pending_rebalance_json = None
    return applied_labels


def activate_due_rebalances(teacher_id, *, block=None, reference_time=None, renewal_policy_id=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    pending_rows_query = FeatureSettings.query.filter(
        FeatureSettings.teacher_id == teacher_id,
        FeatureSettings.economy_pending_rebalance_json.isnot(None),
    )
    if block:
        pending_rows_query = pending_rows_query.filter(FeatureSettings.block == block)

    activated = 0
    applied_labels = []

    for settings_row in pending_rows_query.all():
        try:
            payload = json.loads(settings_row.economy_pending_rebalance_json or "{}")
        except json.JSONDecodeError:
            settings_row.economy_pending_rebalance_json = None
            continue

        activation_mode = payload.get("activation_mode") or REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL
        changes = payload.get("changes") or []
        if not changes:
            settings_row.economy_pending_rebalance_json = None
            continue

        due_changes = []
        future_changes = []
        for change in changes:
            activation_event = change.get("activation_event")
            activation_policy_id = change.get("activation_policy_id")
            effective_at = _parse_dt(change.get("effective_at"))
            if activation_event == REBALANCE_TRIGGER_INSURANCE_RENEWAL:
                if renewal_policy_id is not None and str(activation_policy_id) == str(renewal_policy_id):
                    due_changes.append(change)
                else:
                    future_changes.append(change)
            elif activation_mode == REBALANCE_ACTIVATION_LEGACY_NEXT_PAYROLL and effective_at is None:
                due_changes.append(change)
            elif effective_at is not None and effective_at <= reference_time:
                due_changes.append(change)
            else:
                future_changes.append(change)

        if due_changes:
            applied_labels.extend(
                _apply_change_list(
                    teacher_id,
                    settings_row,
                    due_changes,
                    activation_mode,
                    reference_time=reference_time,
                )
            )
            activated += 1

        if future_changes:
            payload["changes"] = future_changes
            settings_row.economy_pending_rebalance_json = json.dumps(payload)
        else:
            settings_row.economy_pending_rebalance_json = None

    return activated, applied_labels
