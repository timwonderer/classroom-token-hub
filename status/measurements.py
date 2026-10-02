"""Closed request measurements authorized by DOM-OPS-001 / SPEC-OPS-006."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

SCHEMA_VERSION = "request-telemetry-v2"
# Written before hall passes had a component (SPEC-OPS-006 v1.3). Still read, as
# carrying no hall-pass evidence, so the sampler and the collector can be
# upgraded in either order and retained activity survives the change.
LEGACY_SCHEMA_VERSION = "request-telemetry-v1"
WINDOW_SECONDS = 300
COMPONENT_KEYS = ("service", "login", "attendance", "hall_pass", "payroll", "roster", "classroom_economy")
LEGACY_COMPONENT_KEYS = ("service", "login", "attendance", "payroll", "roster", "classroom_economy")
LEGACY_COUNT_FIELDS = ("request_count", "http_1xx_count", "http_2xx_count", "http_3xx_count", "http_4xx_count", "http_404_count", "http_500_count", "http_5xx_count")
# 404s that a component's contract counts as failed requests, not missing pages.
COUNT_FIELDS = LEGACY_COUNT_FIELDS + ("http_404_failure_count",)
LATENCY_FIELDS = ("p80_ms", "p95_ms")
DIAGNOSTICS = frozenset({"TRANSPORT_UNAVAILABLE", "ACCESS_DENIED", "INVALID_SNAPSHOT", "STALE_SNAPSHOT"})
# SPEC-OPS-006 §VI: the only routes whose 404 is a failed request. The hall-pass
# page only ever approves, rejects or cancels a request id it was given, so "not
# found" there means a request the app had just shown could not be found
# (2026-10-01). Every other component, and every other hall-pass route, has none.
NOT_FOUND_FAILURE_ROUTES = {"hall_pass": "/api/hall-pass/request/[^/]+/(approve|reject|cancel)"}
# Owner ruling 2026-10-02 (SPEC-OPS-006 §VI): failed-request 404s signal only when
# a window holds at least this many AND they exceed this share of the component's
# requests, so one stray 404 (a double click, a stale tab) never does.
NOT_FOUND_FAILURE_MIN_COUNT = 3
NOT_FOUND_FAILURE_RATE_PERCENT = 2
_SCHEMAS = {SCHEMA_VERSION: (COMPONENT_KEYS, COUNT_FIELDS),
            LEGACY_SCHEMA_VERSION: (LEGACY_COMPONENT_KEYS, LEGACY_COUNT_FIELDS)}


def not_found_failures(component: dict) -> int:
    """Failed-request 404s; a legacy component predates the field and had none."""
    return component.get("http_404_failure_count") or 0


def not_found_failures_signal(component: dict) -> bool:
    """The rate-plus-minimum rule: card, headline, history and operator drafts share it."""
    failures, count = not_found_failures(component), component.get("request_count") or 0
    return (bool(count) and failures >= NOT_FOUND_FAILURE_MIN_COUNT
            and 100 * failures / count > NOT_FOUND_FAILURE_RATE_PERCENT)


def parse_time(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Timestamp must be bounded UTC ISO text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamp must be UTC")
    return parsed.astimezone(timezone.utc)


def unavailable_component(key: str, schema_version: str = SCHEMA_VERSION) -> dict:
    keys, counts = _SCHEMAS[schema_version]
    if key not in keys:
        raise ValueError("Unknown component")
    return {"key": key, "collection_state": "UNAVAILABLE", **{field: None for field in counts + LATENCY_FIELDS}}


def validate_snapshot(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "sampled_at", "window_seconds", "source_latest_at", "components"}:
        raise ValueError("Unexpected snapshot fields")
    if payload["schema_version"] not in _SCHEMAS or type(payload["window_seconds"]) is not int or payload["window_seconds"] != WINDOW_SECONDS:
        raise ValueError("Unsupported snapshot schema or window")
    component_keys, count_fields = _SCHEMAS[payload["schema_version"]]
    sampled = parse_time(payload["sampled_at"])
    if payload["source_latest_at"] is not None and parse_time(payload["source_latest_at"]) > sampled:
        raise ValueError("Source event cannot be later than evaluation time")
    components = payload["components"]
    if not isinstance(components, list) or len(components) != len(component_keys):
        raise ValueError("Incomplete components")
    seen = set()
    for component in components:
        if not isinstance(component, dict) or set(component) != {"key", "collection_state", *count_fields, *LATENCY_FIELDS}:
            raise ValueError("Unexpected component fields")
        key = component["key"]
        if not isinstance(key, str) or key not in component_keys or key in seen:
            raise ValueError("Unknown or duplicate component")
        seen.add(key)
        if component["collection_state"] == "UNAVAILABLE":
            if any(component[field] is not None for field in count_fields + LATENCY_FIELDS):
                raise ValueError("Unavailable collection cannot contain measurements")
            continue
        if component["collection_state"] != "OK":
            raise ValueError("Unknown collection state")
        for field in count_fields:
            if type(component[field]) is not int or not 0 <= component[field] <= 1_000_000_000:
                raise ValueError("Invalid count")
        count = component["request_count"]
        if sum(component[f"http_{kind}xx_count"] for kind in range(1, 6)) != count:
            raise ValueError("Response classes must partition requests")
        if component["http_404_count"] > component["http_4xx_count"] or component["http_500_count"] > component["http_5xx_count"]:
            raise ValueError("Invalid response subsets")
        if not_found_failures(component) > component["http_404_count"] or (
                key not in NOT_FOUND_FAILURE_ROUTES and not_found_failures(component)):
            raise ValueError("Failed-request 404s are a subset of a designated component's 404s")
        for field in LATENCY_FIELDS:
            value = component[field]
            if count == 0:
                if value is not None:
                    raise ValueError("Empty windows have no latency quantile")
            elif type(value) not in (int, float) or not 0 <= value <= 600_000 or not isfinite(value):
                raise ValueError("Invalid latency")
        if count and component["p80_ms"] > component["p95_ms"]:
            raise ValueError("Quantiles are not ordered")
    return payload


def validate_fresh_snapshot(payload: object, received_at: datetime) -> dict:
    snapshot = validate_snapshot(payload)
    if received_at.tzinfo is None:
        raise ValueError("Receipt time must be aware")
    age = (received_at - parse_time(snapshot["sampled_at"])).total_seconds()
    if not 0 <= age <= WINDOW_SECONDS:
        raise ValueError("Stale or future snapshot")
    return snapshot


def classify_component(component: dict, snapshot: dict, *, now: datetime) -> dict:
    """Describe requests only; never infer domain correctness or human impact."""
    result = {"state": "MONITOR_UNAVAILABLE", "reasons": [], "http_404_percent": None, "http_500_percent": None,
              "http_5xx_percent": None, "http_404_failure_percent": None}
    age = (now - parse_time(snapshot["sampled_at"])).total_seconds()
    latest = snapshot["source_latest_at"]
    if age < 0 or (latest is not None and parse_time(latest) > now):
        result["reasons"] = ["Monitoring timestamps are ahead of the current time."]
        return result
    if age > WINDOW_SECONDS or (latest is not None and (now - parse_time(latest)).total_seconds() > 180):
        result.update(state="STALE", reasons=["Recent monitoring evidence is unavailable."])
        return result
    if latest is None or component["collection_state"] != "OK":
        result["reasons"] = ["Monitoring could not collect this measurement."]
        return result
    count = component["request_count"]
    if not count:
        result.update(state="NO_TRAFFIC", reasons=["No matching requests in this window."])
        return result
    for code in ("404", "500", "5xx"):
        result[f"http_{code}_percent"] = 100 * component[f"http_{code}_count"] / count
    if component["key"] in NOT_FOUND_FAILURE_ROUTES:
        result["http_404_failure_percent"] = 100 * not_found_failures(component) / count
    reasons = []
    if result["http_5xx_percent"] > 2:
        reasons.append("Elevated server-error responses (5xx above 2%).")
    if not_found_failures_signal(component):
        reasons.append("Hall-pass requests not found when approved, rejected or cancelled "
                       f"(at least {NOT_FOUND_FAILURE_MIN_COUNT}, above {NOT_FOUND_FAILURE_RATE_PERCENT}%).")
    if result["http_404_percent"] > 5:
        reasons.append("Elevated not-found responses (404 above 5%).")
    state = "ELEVATED_ERRORS" if reasons else "NORMAL"
    if component["p95_ms"] > 1500:
        reasons.append("High latency (p95 above 1,500 ms).")
        if state != "ELEVATED_ERRORS":
            state = "HIGH_LATENCY"
    if not reasons:
        reasons = ["Observed requests are within the published thresholds."]
    result.update(state=state, reasons=reasons)
    return result


def retained_activity(activity: object, *, now: datetime) -> dict:
    """Validate historical context without renewing its source timestamp."""
    if not isinstance(activity, dict):
        return {}
    result = {}
    for key in COMPONENT_KEYS:
        value = activity.get(key)
        try:
            if not isinstance(value, dict) or set(value) != {"sampled_at", "source_latest_at", "component"}:
                continue
            # Retained before or after the hall-pass amendment: validate it as written.
            version = SCHEMA_VERSION if "http_404_failure_count" in value["component"] else LEGACY_SCHEMA_VERSION
            if key not in _SCHEMAS[version][0]:
                continue
            historical = validate_snapshot({"schema_version": version,
                "window_seconds": WINDOW_SECONDS, "sampled_at": value["sampled_at"],
                "source_latest_at": value["source_latest_at"], "components": [
                    value["component"] if name == key else unavailable_component(name, version)
                    for name in _SCHEMAS[version][0]]})
            sampled = parse_time(historical["sampled_at"])
            component = value["component"]
            if (0 <= (now - sampled).total_seconds() <= 7 * 86400 and component["request_count"]
                    and classify_component(component, historical, now=sampled)["state"]
                    not in {"STALE", "MONITOR_UNAVAILABLE"}):
                result[key] = value
        except (ValueError, TypeError, KeyError):
            continue
    return result
