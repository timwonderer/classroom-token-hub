"""Closed request measurements authorized by DOM-OPS-001 / SPEC-OPS-006."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

SCHEMA_VERSION = "request-telemetry-v1"
WINDOW_SECONDS = 300
COMPONENT_KEYS = ("service", "login", "attendance", "payroll", "roster", "classroom_economy")
COUNT_FIELDS = ("request_count", "http_1xx_count", "http_2xx_count", "http_3xx_count", "http_4xx_count", "http_404_count", "http_500_count", "http_5xx_count")
LATENCY_FIELDS = ("p80_ms", "p95_ms")
DIAGNOSTICS = frozenset({"TRANSPORT_UNAVAILABLE", "ACCESS_DENIED", "INVALID_SNAPSHOT", "STALE_SNAPSHOT"})


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


def unavailable_component(key: str) -> dict:
    if key not in COMPONENT_KEYS:
        raise ValueError("Unknown component")
    return {"key": key, "collection_state": "UNAVAILABLE", **{field: None for field in COUNT_FIELDS + LATENCY_FIELDS}}


def validate_snapshot(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "sampled_at", "window_seconds", "source_latest_at", "components"}:
        raise ValueError("Unexpected snapshot fields")
    if payload["schema_version"] != SCHEMA_VERSION or type(payload["window_seconds"]) is not int or payload["window_seconds"] != WINDOW_SECONDS:
        raise ValueError("Unsupported snapshot schema or window")
    sampled = parse_time(payload["sampled_at"])
    if payload["source_latest_at"] is not None and parse_time(payload["source_latest_at"]) > sampled:
        raise ValueError("Source event cannot be later than evaluation time")
    components = payload["components"]
    if not isinstance(components, list) or len(components) != len(COMPONENT_KEYS):
        raise ValueError("Incomplete components")
    seen = set()
    for component in components:
        if not isinstance(component, dict) or set(component) != {"key", "collection_state", *COUNT_FIELDS, *LATENCY_FIELDS}:
            raise ValueError("Unexpected component fields")
        key = component["key"]
        if not isinstance(key, str) or key not in COMPONENT_KEYS or key in seen:
            raise ValueError("Unknown or duplicate component")
        seen.add(key)
        if component["collection_state"] == "UNAVAILABLE":
            if any(component[field] is not None for field in COUNT_FIELDS + LATENCY_FIELDS):
                raise ValueError("Unavailable collection cannot contain measurements")
            continue
        if component["collection_state"] != "OK":
            raise ValueError("Unknown collection state")
        for field in COUNT_FIELDS:
            if type(component[field]) is not int or not 0 <= component[field] <= 1_000_000_000:
                raise ValueError("Invalid count")
        count = component["request_count"]
        if sum(component[f"http_{kind}xx_count"] for kind in range(1, 6)) != count:
            raise ValueError("Response classes must partition requests")
        if component["http_404_count"] > component["http_4xx_count"] or component["http_500_count"] > component["http_5xx_count"]:
            raise ValueError("Invalid response subsets")
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
    result = {"state": "MONITOR_UNAVAILABLE", "reasons": [], "http_404_percent": None, "http_500_percent": None, "http_5xx_percent": None}
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
    reasons = []
    if result["http_5xx_percent"] > 2:
        reasons.append("Elevated server-error responses (5xx above 2%).")
    if result["http_404_percent"] > 5:
        reasons.append("Elevated not-found responses (404 above 5%).")
    state = "ELEVATED_ERRORS" if reasons else "NORMAL" if count >= 20 else "LOW_TRAFFIC"
    if component["p95_ms"] > 1500:
        reasons.append("High latency (p95 above 1,500 ms).")
        if state != "ELEVATED_ERRORS":
            state = "HIGH_LATENCY"
    if not reasons:
        reasons = ["Observed requests are within the published thresholds." if state == "NORMAL" else "Fewer than 20 requests; evidence is limited."]
    result.update(state=state, reasons=reasons)
    return result
