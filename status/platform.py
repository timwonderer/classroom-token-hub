"""Endpoint, database and access-gate checks under DOM-OPS-001/SPEC-OPS-006."""
from __future__ import annotations

from datetime import datetime

from .measurements import parse_time

PLATFORM_SCHEMA = "platform-check-v2"
# Each schema version names exactly the checks its records carry. v1 records,
# written before the gate check existed, carry no gate evidence.
SCHEMA_KEYS = {
    "platform-check-v1": ("endpoint", "database"),
    "platform-check-v2": ("endpoint", "database", "gate"),
}
PLATFORM_KEYS = SCHEMA_KEYS[PLATFORM_SCHEMA]
_OUTCOMES = {
    "endpoint": {"HTTP_OK": "PASS", "HTTP_UNAVAILABLE": "FAIL", "ACCESS_DENIED": "UNKNOWN", "TRANSPORT_UNAVAILABLE": "UNKNOWN", "INVALID_RESPONSE": "UNKNOWN"},
    "database": {"DATABASE_REACHABLE": "PASS", "DATABASE_UNAVAILABLE": "FAIL", "ACCESS_DENIED": "UNKNOWN", "TRANSPORT_UNAVAILABLE": "UNKNOWN", "INVALID_RESPONSE": "UNKNOWN", "STALE_SOURCE": "UNKNOWN"},
    # The Application Availability Gate (DOM-OPS-001): FAIL means the gate is
    # closed to the public, an access restriction rather than an app failure.
    "gate": {"GATE_OPEN": "PASS", "GATE_CLOSED": "FAIL", "UNEXPECTED_DENIAL": "UNKNOWN", "TRANSPORT_UNAVAILABLE": "UNKNOWN"},
}


def validate_platform(record: object) -> dict:
    if (not isinstance(record, dict) or set(record) != {"schema_version", "received_at", "checks"}
            or not isinstance(record["schema_version"], str) or record["schema_version"] not in SCHEMA_KEYS):
        raise ValueError("Invalid platform record")
    keys = SCHEMA_KEYS[record["schema_version"]]
    received = parse_time(record["received_at"])
    if not isinstance(record["checks"], list) or len(record["checks"]) != len(keys):
        raise ValueError("Incomplete platform checks")
    seen = set()
    for check in record["checks"]:
        if not isinstance(check, dict) or set(check) != {"key", "outcome", "checked_at", "diagnostic"}:
            raise ValueError("Invalid platform check fields")
        key = check["key"]
        if not isinstance(key, str) or key not in keys or key in seen:
            raise ValueError("Unknown platform key")
        seen.add(key)
        diagnostic = check["diagnostic"]
        if not isinstance(diagnostic, str) or diagnostic not in _OUTCOMES[key] or check["outcome"] != _OUTCOMES[key][diagnostic]:
            raise ValueError("Invalid platform result")
        checked = check["checked_at"]
        if check["outcome"] == "UNKNOWN":
            if checked is not None:
                raise ValueError("Unknown checks cannot claim an execution timestamp")
        elif checked is None or parse_time(checked) > received:
            raise ValueError("Measured checks require a valid source execution time")
    return record


def platform_rows(record: dict | None, *, now: datetime) -> list[dict]:
    if record is not None:
        try:
            record = validate_platform(record)
        except (ValueError, TypeError):
            record = None
    names = {"endpoint": "Application endpoint", "database": "Database access", "gate": "Public access"}
    details = {
        "HTTP_OK": "The monitored application endpoint responded with HTTP 200.",
        "HTTP_UNAVAILABLE": "The monitored application endpoint returned an unsuccessful HTTP response.",
        "DATABASE_REACHABLE": "The application completed its database connection check (SELECT 1).",
        "DATABASE_UNAVAILABLE": "The application's database connection check failed.",
        "ACCESS_DENIED": "Monitoring could not authenticate to the check endpoint.",
        "TRANSPORT_UNAVAILABLE": "Monitoring could not retrieve this check.",
        "INVALID_RESPONSE": "Monitoring could not validate this check's response.",
        "STALE_SOURCE": "The application returned an outdated database check.",
        "GATE_OPEN": "Public pages are open; no access restriction is in place.",
        "GATE_CLOSED": "Access is temporarily restricted for maintenance.",
        "UNEXPECTED_DENIAL": "A public page was refused without the access restriction being confirmed.",
    }
    rows = []
    for key in PLATFORM_KEYS:
        if key == "gate" and record and "gate" not in SCHEMA_KEYS[record["schema_version"]]:
            continue
        check = next((item for item in record["checks"] if item["key"] == key), None) if record else None
        state = check["outcome"] if check else "UNKNOWN"
        checked_at = check["checked_at"] if check else None
        detail = details[check["diagnostic"]] if check else "No recent measured check is available."
        if record:
            source_time = parse_time(checked_at or record["received_at"])
            age = (now - source_time).total_seconds()
            if age < 0:
                state, detail = "UNKNOWN", "The monitoring timestamp is ahead of the current time."
            elif age > 300:
                state, detail = "STALE", "No recent measured check is available."
        label = {"PASS": "Responding", "FAIL": "Check failed", "UNKNOWN": "Not verified", "STALE": "Out of date"}[state]
        if key == "gate" and state in {"PASS", "FAIL"}:
            label = "Open" if state == "PASS" else "Restricted"
        rows.append({"key": key, "name": names[key], "state": state, "label": label, "checked_at": checked_at, "detail": detail})
    return rows
