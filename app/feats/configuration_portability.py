"""FEAT-CLASS-009/010/011: class-scoped transfer with one transaction per mutation."""
from copy import deepcopy
from uuid import uuid4
from app.extensions import db
from app.feats.base import FEATContext
from app.services import configuration_identity as identity, configuration_receipts as receipts
from app.services.configuration_artifact import ConfigurationError, StrictJSON, sign, verify, digest, instant, MAX_ENTRIES
from app.services.configuration_fields import SCHEMAS, SCHEDULES, project, decode
from app.services.configuration_policy_inventory import policy_inventory
from app.services.class_configuration_query_service import get_current_economic_engine, get_class_features
from app.services.economic_configuration_commands import evolve_economic_engine, _validate_engine_field
from app.services.insurance_configuration import create_tier_group, submit_insurance_definition, _validate_and_build_definition
from app.services.store_service import publish_product, _validate_definition
from app.services.payroll.settings import save_payroll_setting
from app.services.admin_settings_service import supersede_rent_settings
from app.services.hall_pass_configuration import save_hall_pass_setup_config
from app.services.audit_service import emit_audit_event

FAMILIES = frozenset(SCHEMAS) | {"hall_pass"}


def execution_authority(context, session_nonce, *, lock):
    user = identity.execution_authority(context, session_nonce, lock=lock)
    classroom = receipts.class_scope(context.class_id, lock=lock)
    identity.assert_actor_seat(context)
    if classroom is None or classroom.teacher_user_id != user.id:
        raise ConfigurationError("You must own this class to transfer its configuration")
    return user, classroom


def inventory(context):
    result = policy_inventory(context)
    engine = get_current_economic_engine(context.class_id)
    if engine:
        if engine.expected_weekly_hours is not None:
            result["economy"] = project(engine, "economy", context)
        if engine.interest_rate is not None:
            result["banking"] = project(engine, "banking", context)
    enabled = get_class_features(context.class_id)
    return {key: value for key, value in result.items() if key == "economy" or key in enabled}


def _validate(groups, context):
    if not isinstance(groups, dict) or set(groups) - FAMILIES:
        raise ConfigurationError("Unknown configuration family")
    count = 0
    decoded = {}
    for family, values in groups.items():
        if family == "store":
            if not isinstance(values, list):
                raise ConfigurationError("Store configuration must be a list")
            count += len(values)
            decoded[family] = [decode(v, family, context) for v in values]
            for definition in decoded[family]:
                _validate_definition(definition)
        elif family == "insurance":
            if not isinstance(values, list):
                raise ConfigurationError("Insurance configuration must be a list")
            decoded[family] = []
            for group in values:
                if not isinstance(group, dict) or set(group) != {"name", "policies"} or not isinstance(group["policies"], list):
                    raise ConfigurationError("Invalid insurance group")
                name = group["name"]
                policies = group["policies"]
                if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 60):
                    raise ConfigurationError("Invalid insurance group name")
                if (name is None and len(policies) != 1) or not policies:
                    raise ConfigurationError("Invalid insurance group membership")
                count += len(policies)
                rows = [decode(p, family, context) for p in policies]
                ranks = [p["tier_level"] for p in rows]
                if name is not None and (len(set(ranks)) != len(ranks) or any(rank not in (1, 2, 3) for rank in ranks)):
                    raise ConfigurationError("Each insurance group needs distinct ranks of 1, 2 or 3")
                for row in rows:
                    _validate_and_build_definition(row)
                decoded[family].append({"name": name, "policies": rows})
        elif family == "hall_pass":
            if not isinstance(values, dict) or set(values) != {"max_queue_limit", "pass_type_payload"}:
                raise ConfigurationError("Invalid hall pass settings")
            if type(values["max_queue_limit"]) is not int or values["max_queue_limit"] < 0:
                raise ConfigurationError("Invalid hall pass queue limit")
            entries = values["pass_type_payload"]
            if not isinstance(entries, list):
                raise ConfigurationError("Invalid hall pass destinations")
            count += len(entries)
            for entry in entries:
                if (not isinstance(entry, dict) or set(entry) != {"pass_name", "max_queue", "consume_pass"}
                        or not isinstance(entry["pass_name"], str) or not entry["pass_name"].strip()
                        or type(entry["max_queue"]) is not int or entry["max_queue"] < 0
                        or type(entry["consume_pass"]) is not bool):
                    raise ConfigurationError("Invalid hall pass destination")
            decoded[family] = deepcopy(values)
        else:
            decoded[family] = decode(values, family, context)
            if family in ("economy", "banking"):
                for field, value in decoded[family].items():
                    valid, message = _validate_engine_field(field, value)
                    if not valid:
                        raise ConfigurationError(message)
    if count > MAX_ENTRIES:
        raise ConfigurationError("Configuration exceeds the 1,000 entry limit")
    return decoded


def select(groups, selection):
    if selection is None:
        return deepcopy(groups)
    if not isinstance(selection, dict) or set(selection) - set(groups):
        raise ConfigurationError("Invalid selection")
    result = {}
    for family, chosen in selection.items():
        values = deepcopy(groups[family])
        if family in ("store", "insurance", "hall_pass"):
            entries = values["pass_type_payload"] if family == "hall_pass" else values
            if family == "insurance":
                # Selection keys are file-local positions, never database identities.
                entries = [(g, p) for g, group in enumerate(values) for p in range(len(group["policies"]))]
            if not isinstance(chosen, list) or any(type(i) is not int or i < 0 or i >= len(entries) for i in chosen) or len(set(chosen)) != len(chosen):
                raise ConfigurationError("Invalid entry selection")
            if family == "hall_pass":
                values["pass_type_payload"] = [entries[i] for i in chosen]
            elif family == "insurance":
                positions = {entries[i] for i in chosen}
                values = [{"name": group["name"], "policies": [p for j, p in enumerate(group["policies"]) if (i, j) in positions]}
                          for i, group in enumerate(values) if any(g == i for g, _ in positions)]
            else:
                values = [entries[i] for i in chosen]
        elif chosen is not True:
            raise ConfigurationError("Invalid family selection")
        result[family] = values
    return result


def _audit(context, operation, operation_id, details):
    table = "users" if operation == "EXPORT" else "configuration_import_receipts"
    row_pk = context.user_id if operation == "EXPORT" else operation_id
    verb = {"EXPORT": "UPDATE", "IMPORT": "INSERT", "CLEANUP": "DELETE"}[operation]
    emit_audit_event(table, row_pk, verb, details,
        class_id=context.class_id, seat_id=context.seat_id, actor_type="teacher")


def export_configuration(context, session_nonce, selection=None, *, expected_inventory_digest=None):
    with FEATContext("FEAT-CLASS-009", idempotency_key=f"configuration:export:{uuid4()}"):
        user, _ = execution_authority(context, session_nonce, lock=True)
        current_inventory = inventory(context)
        if expected_inventory_digest is not None and expected_inventory_digest != digest(StrictJSON.dumps(current_inventory)):
            raise ConfigurationError("Class configuration changed. Review your export selection again.")
        groups = select(current_inventory, selection)
        _validate(groups, context)
        reference, issued, expires = identity.new_export_reference()
        envelope = {"format": 1, "reference": reference, "issued_at": issued, "expires_at": expires, "groups": groups}
        raw = sign(envelope, "export")
        identity.rotate(user, reference, expires)
        _audit(context, "EXPORT", digest(reference), {"digest": digest(raw)})
    return raw


def _load(raw, context):
    envelope = verify(raw, "export")
    if (not isinstance(envelope, dict) or set(envelope) != {"format", "reference", "issued_at", "expires_at", "groups"}
            or type(envelope["format"]) is not int or envelope["format"] != 1
            or not isinstance(envelope["reference"], str) or len(envelope["reference"]) != 64):
        raise ConfigurationError("Unsupported configuration format")
    instant(envelope["issued_at"])
    instant(envelope["expires_at"])
    _validate(envelope["groups"], context)
    return envelope


def _schedule(groups, choices, destination):
    if not isinstance(choices, dict) or set(choices) - (set(groups) & set(SCHEDULES)):
        raise ConfigurationError("Invalid schedule selection")
    for family, choice in choices.items():
        if not isinstance(choice, dict) or set(choice) - {"mode", "values"}:
            raise ConfigurationError("Invalid schedule choice")
        mode = choice.get("mode")
        if mode == "exported":
            if set(choice) != {"mode"}:
                raise ConfigurationError("Exported schedule cannot carry overrides")
            continue
        if mode == "destination":
            if family == "store" or family not in destination or set(choice) != {"mode"}:
                raise ConfigurationError("This configuration has no destination schedule")
            source = destination[family]
            groups[family].update({key: source[key] for key in SCHEDULES[family]})
        elif mode == "custom":
            values = choice.get("values")
            if family == "store":
                if not isinstance(values, list) or len(values) != len(groups[family]):
                    raise ConfigurationError("Enter dates for every selected store product")
                pairs = zip(groups[family], values)
            else:
                pairs = [(groups[family], values)]
            for target, fields in pairs:
                if not isinstance(fields, dict) or set(fields) != set(SCHEDULES[family]):
                    raise ConfigurationError("Enter the complete schedule")
                target.update(fields)
        else:
            raise ConfigurationError("Choose destination, exported, or entered schedule")
    return groups


def inspect_import(context, session_nonce, raw):
    """Authorize the file before presenting its selectable definitions."""
    user, _ = execution_authority(context, session_nonce, lock=False)
    envelope = _load(raw, context)
    identity.validate_reference(user, envelope)
    return envelope


def _state(context):
    from app.services.payroll.settings import pending_payroll_settings, current_payroll_setting
    from app.services.payroll.schedule import effective_date_for_new_setting
    from app.services.obligations_service import get_latest_bill_cycle
    from app.services.class_configuration_query_service import pending_economic_engines
    current = inventory(context)
    # Pending payroll changes are not exported but can change the receiving boundary.
    state = {"current": current, "enabled": sorted(get_class_features(context.class_id)),
        "pending_payroll": [row.policy_uuid for row in pending_payroll_settings(context.class_id)]}
    engine = get_current_economic_engine(context.class_id)
    state["economic_version"] = engine.economic_version_id if engine else None
    state["pending_economics"] = [row.economic_version_id for row in pending_economic_engines(context.class_id)]
    payroll = current_payroll_setting(context.class_id)
    state["payroll_policy"] = payroll.policy_uuid if payroll else None
    state["payroll_boundary"] = (effective_date_for_new_setting(context.class_id, identity.now()).isoformat()
        if payroll else None)
    cycle = get_latest_bill_cycle(f"rent:{context.class_id}")
    state["rent_boundary"] = cycle.next_assessment_at.isoformat() if cycle and cycle.next_assessment_at else None
    return current, digest(StrictJSON.dumps(state))


def _preview_timing(context, decoded):
    from types import SimpleNamespace
    from app.services.payroll.schedule import effective_date_for_new_setting, first_boundary_after, pay_cadence
    from app.services.rent_schedule_service import first_due_local_date, advance_due_date
    from app.services.obligations_service import get_latest_bill_cycle
    from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
    now = identity.now()
    def local(timestamp):
        return canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
            primitive="localize_timestamp", timestamp=timestamp).result["local_timestamp"].isoformat()
    timing = {}
    if "payroll" in decoded:
        row = decoded["payroll"]
        timing["Payroll effective date and time if confirmed now"] = local(effective_date_for_new_setting(context.class_id, now))
        anchor = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
            primitive="localize_timestamp", timestamp=row["first_pay_date"]).evaluation_date
        timing["Next occurrence of selected payroll schedule"] = local(first_boundary_after(context.class_id, anchor, pay_cadence(row["pay_schedule_type"]), now))
    if "rent" in decoded:
        row = SimpleNamespace(**decoded["rent"])
        day = first_due_local_date(row, context=context, reference_time_utc=now)
        # Validate recurrence even when the first due date is still in the future.
        advance_due_date(row, day, context=context)
        for _ in range(10000):
            timestamp = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
                primitive="evaluation_day_boundaries", evaluation_date=day).boundary_start_utc
            if not canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
                    primitive="earlier_than", candidate=timestamp, reference=now).is_earlier:
                break
            day = advance_due_date(row, day, context=context)
        else:
            raise ConfigurationError("Rent schedule cannot be resolved")
        timing["Next occurrence of selected rent schedule"] = local(timestamp)
        cycle = get_latest_bill_cycle(f"rent:{context.class_id}")
        timing["Rent terms first bind to a new period"] = (local(cycle.next_assessment_at) if cycle and cycle.next_assessment_at
            else "No further rent cycle is scheduled" if cycle else "When the first rent period is issued")
    if "banking" in decoded:
        for field in ("interest_accrual_frequency", "compound_frequency", "interest_payout_frequency"):
            frequency = decoded["banking"][field]
            if frequency in {"daily", "weekly", "monthly"}:
                boundary = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
                    primitive="evaluation_period_boundaries", period={"daily": "day", "weekly": "week", "monthly": "month"}[frequency],
                    reference_time_utc=now).boundary_end_utc
                timing["Next " + field.replace("_frequency", "").replace("_", " ")] = local(boundary)
    return timing


def preview_import(context, session_nonce, raw, selection=None, schedules=None):
    user, classroom = execution_authority(context, session_nonce, lock=False)
    envelope = _load(raw, context)
    identity.validate_reference(user, envelope)
    destination, state = _state(context)
    groups = select(envelope["groups"], selection)
    groups = _schedule(groups, schedules or {}, destination)
    enabled = get_class_features(context.class_id)
    skipped = sorted(key for key in groups if key != "economy" and key not in enabled)
    groups = {key: value for key, value in groups.items() if key not in skipped}
    decoded = _validate(groups, context)
    timing = _preview_timing(context, decoded)
    token = {"operation_id": str(uuid4()), "class_id": context.class_id, "seat_id": context.seat_id,
        "digest": digest(raw), "reference": envelope["reference"], "expires_at": envelope["expires_at"],
        "selection": selection, "schedules": schedules or {}, "state": state}
    return {"token": sign(token, "confirmation").decode("utf-8"), "groups": groups,
        "skipped": skipped, "timing": timing, "timezone": classroom.class_timezone, "expires_at": envelope["expires_at"]}


def confirm_import(context, session_nonce, raw, confirmation):
    token = verify(confirmation, "confirmation")
    expected = {"operation_id", "class_id", "seat_id", "digest", "reference", "expires_at", "selection", "schedules", "state"}
    if not isinstance(token, dict) or set(token) != expected:
        raise ConfigurationError("Invalid confirmation")
    if token["class_id"] != context.class_id or token["seat_id"] != context.seat_id or token["digest"] != digest(raw):
        raise ConfigurationError("Confirmation does not match this class, actor or file")
    fingerprint = digest(StrictJSON.dumps(token))
    operation_id = token["operation_id"]
    with FEATContext("FEAT-CLASS-010", idempotency_key=f"configuration:import:{operation_id}"):
        user, _ = execution_authority(context, session_nonce, lock=True)
        envelope = _load(raw, context)
        if token["reference"] != envelope["reference"] or token["expires_at"] != envelope["expires_at"]:
            raise ConfigurationError("Confirmation does not match the export")
        identity.validate_reference(user, envelope, token)
        previous = receipts.find(context, operation_id)
        if previous:
            if previous.fingerprint != fingerprint or previous.actor_seat_id != context.seat_id:
                raise ConfigurationError("Operation identity was reused with different inputs")
            return previous.result
        destination, state = _state(context)
        if state != token["state"]:
            raise ConfigurationError("Class configuration changed. Preview the import again.")
        groups = _schedule(select(envelope["groups"], token["selection"]), token["schedules"], destination)
        enabled = get_class_features(context.class_id)
        skipped = sorted(key for key in groups if key != "economy" and key not in enabled)
        decoded = _validate({key: value for key, value in groups.items() if key not in skipped}, context)
        receipt, inserted = receipts.reserve(context, operation_id, fingerprint, instant(token["expires_at"]), identity.now())
        if not inserted:
            return receipt.result
        results = {}
        updates = {**decoded.get("economy", {}), **decoded.get("banking", {})}
        if updates:
            result = evolve_economic_engine(canonical_context=context, class_id=context.class_id,
                updates=updates, feature_list=list(enabled), idempotency_key=f"configuration:{operation_id}")
            if not result.success:
                raise ConfigurationError(result.error_message)
            results["economic_version"] = result.new_engine_id
        if "payroll" in decoded:
            row = save_payroll_setting(class_id=context.class_id, settings_data=decoded["payroll"])
            results["payroll"] = row.policy_uuid
            results["payroll_effective_at"] = row.effective_date.isoformat()
        if "rent" in decoded:
            row = supersede_rent_settings(class_id=context.class_id, updates=decoded["rent"])
            results["rent"] = row.policy_uuid
        if "hall_pass" in decoded:
            row = save_hall_pass_setup_config(user_id=context.user_id, class_id=context.class_id,
                hall_pass_enabled=True, **decoded["hall_pass"], correlation_id=operation_id,
                idempotency_key=f"configuration:{operation_id}")
            results["hall_pass"] = row.policy_uuid
        results["store"] = []
        for definition in decoded.get("store", []):
            if definition["item_type"] == "collective":
                definition["collective_goal_instance_code"] = str(uuid4())
            row = publish_product(class_id=context.class_id, definition=definition, actor_seat_id=context.seat_id)
            results["store"].append(row.policy_uuid)
        results["insurance"] = []
        for group in decoded.get("insurance", []):
            group_id = create_tier_group(context.class_id, group["name"]).group_id if group["name"] is not None else None
            for definition in group["policies"]:
                if group_id:
                    definition["tier_group_id"] = group_id
                row = submit_insurance_definition(class_id=context.class_id, submission=definition, actor_seat_id=context.seat_id)
                results["insurance"].append(row.policy_uuid)
        results["skipped"] = skipped
        results["operation_id"] = operation_id
        receipt.result = results
        _audit(context, "IMPORT", operation_id, {"fingerprint": fingerprint, "result": results})
        db.session.flush()
    return results


def cleanup_receipts(context, session_nonce):
    with FEATContext("FEAT-CLASS-011", idempotency_key=f"configuration:cleanup:{uuid4()}"):
        execution_authority(context, session_nonce, lock=True)
        count = receipts.cleanup(context.class_id, identity.now())
        _audit(context, "CLEANUP", str(uuid4()), {"count": count, "reason": "expired"})
    return count
