"""Local-only Loki sampler. DOM-OPS-001 / SPEC-OPS-006; no raw data leaves host."""
from __future__ import annotations

import json
from math import isfinite
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION, WINDOW_SECONDS, unavailable_component, validate_snapshot

LOKI_URL = "http://127.0.0.1:3100"
OUTPUT_PATH = Path("/var/lib/cth-status/telemetry.json")
ROUTES = json.loads(Path(__file__).with_name("route_groups.json").read_text())


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch_loki(endpoint: str, params: dict, *, timeout: float) -> dict:
    request = Request(f"{LOKI_URL}/loki/api/v1/{endpoint}?{urlencode(params)}", headers={"Accept": "application/json"})
    with build_opener(_NoRedirect()).open(request, timeout=max(0.05, min(timeout, 5))) as response:
        if response.status != 200:
            raise ValueError("Loki request failed")
        body = response.read(262_145)
    if len(body) > 262_144:
        raise ValueError("Loki response exceeded bound")
    return json.loads(body)


def _query(fetch, endpoint: str, params: dict, deadline: float) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Sampler deadline reached")
    payload = fetch(endpoint, params, timeout=min(remaining, 5))
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(payload.get("data"), dict):
        raise ValueError("Invalid Loki response")
    return payload["data"]


def _metric(fetch, expression: str, sampled_at: datetime, deadline: float) -> float | None:
    # Official Loki instant-query API: explicit common evaluation time; vectors.
    # https://grafana.com/docs/loki/latest/reference/loki-http-api/
    data = _query(fetch, "query", {"query": expression, "time": sampled_at.isoformat()}, deadline)
    if data.get("resultType") != "vector" or not isinstance(data.get("result"), list):
        raise ValueError("Expected metric vector")
    results = data["result"]
    if not results:
        return None
    if len(results) != 1 or not isinstance(results[0], dict) or results[0].get("metric") != {}:
        raise ValueError("Aggregate must have no labels and exactly one value")
    value = results[0].get("value")
    if not isinstance(value, list) or len(value) != 2 or type(value[0]) not in (float, int) or not isinstance(value[1], str):
        raise ValueError("Invalid metric sample")
    if not isfinite(value[0]) or abs(value[0] - sampled_at.timestamp()) > 0.001:
        raise ValueError("Metric evaluation time mismatch")
    number = float(value[1])
    if not isfinite(number) or number < 0:
        raise ValueError("Invalid metric number")
    return number


def _latest_event(fetch, sampled_at: datetime, deadline: float) -> str | None:
    # Loki stream timestamps are nanosecond event time, NOT ingestion time.
    # line_format discards raw request text before it reaches the sampler.
    data = _query(fetch, "query_range", {
        "query": '{job="nginx_access"} | line_format "entry"',
        "start": (sampled_at - timedelta(minutes=10)).isoformat(),
        "end": sampled_at.isoformat(), "direction": "backward", "limit": 1,
    }, deadline)
    if data.get("resultType") != "streams" or not isinstance(data.get("result"), list):
        raise ValueError("Expected event stream")
    if any(not isinstance(stream, dict) or not isinstance(stream.get("values"), list) for stream in data["result"]):
        raise ValueError("Invalid source event stream")
    values = [value for stream in data["result"] for value in stream["values"]]
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], list) or len(values[0]) != 2 or values[0][1] != "entry":
        raise ValueError("Unexpected source event")
    stamp = int(values[0][0])
    latest = datetime.fromtimestamp(stamp / 1_000_000_000, timezone.utc)
    if latest > sampled_at or latest < sampled_at - timedelta(minutes=10):
        raise ValueError("Source event outside requested window")
    return latest.isoformat()


def _component(key: str, sampled_at: datetime, deadline: float, fetch) -> dict:
    base = '{job="nginx_access"} | json | upstream_addr="127.0.0.1:8000"'
    if key != "service":
        base += " | uri=~" + json.dumps(ROUTES[key])
    base += ' | __error__=""'

    try:
        # Only the closed HTTP status label exists inside this local response.
        # It is reduced to counts before any snapshot leaves the host.
        data = _query(fetch, "query", {"query": f"sum by (status) (count_over_time({base} [5m]))", "time": sampled_at.isoformat()}, deadline)
        if data.get("resultType") != "vector" or not isinstance(data.get("result"), list):
            raise ValueError("Expected response-count vector")
        record = {"key": key, "collection_state": "OK", **{field: 0 for field in COUNT_FIELDS}}
        seen = set()
        for series in data["result"]:
            if not isinstance(series, dict):
                raise ValueError("Invalid count series")
            labels = series.get("metric")
            if not isinstance(labels, dict) or set(labels) != {"status"}:
                raise ValueError("Unexpected count labels")
            status = labels["status"]
            if not isinstance(status, str) or len(status) != 3 or not status.isascii() or not status.isdigit() or not 100 <= int(status) <= 599 or status in seen:
                raise ValueError("Unexpected response code")
            seen.add(status)
            value = series.get("value")
            if not isinstance(value, list) or len(value) != 2 or type(value[0]) not in (int, float) or not isinstance(value[1], str) or not isfinite(value[0]) or abs(value[0] - sampled_at.timestamp()) > 0.001:
                raise ValueError("Invalid count sample time")
            number = float(value[1])
            if not 0 <= number <= 1_000_000_000 or number != int(number):
                raise ValueError("Invalid response count")
            count = int(number)
            record["request_count"] += count
            record[f"http_{status[0]}xx_count"] += count
            if status in {"404", "500"}:
                record[f"http_{status}_count"] += count
        total = record["request_count"]
        # Quantiles must cover every counted request, not only a parseable subset.
        covered = _metric(fetch, f'sum(count_over_time({base} | request_time >= 0 | request_time <= 600 | __error__="" [5m]))', sampled_at, deadline)
        if (0 if covered is None else covered) != total:
            raise ValueError("Incomplete latency evidence")
        for percentile in (80, 95):
            # Group raw unwrapped samples together; never average stream quantiles.
            # https://grafana.com/docs/loki/latest/query/metric_queries/
            value = _metric(fetch, f'quantile_over_time(0.{percentile}, {base} | unwrap request_time | __error__="" [5m]) by ()', sampled_at, deadline)
            record[f"p{percentile}_ms"] = value * 1000 if value is not None else None
        # Reuse full closed validation without inventing a second component schema.
        validate_snapshot({"schema_version": SCHEMA_VERSION, "sampled_at": sampled_at.isoformat(), "window_seconds": WINDOW_SECONDS,
                           "source_latest_at": None, "components": [record if name == key else unavailable_component(name) for name in COMPONENT_KEYS]})
        return record
    except (ValueError, TypeError, KeyError, OSError, TimeoutError, OverflowError):
        return unavailable_component(key)


def sample(*, now: datetime | None = None, fetch=fetch_loki) -> dict:
    sampled_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    # Whole run is bounded below the timer period. Requests share this deadline.
    deadline = time.monotonic() + 45
    try:
        latest = _latest_event(fetch, sampled_at, deadline)
    except (ValueError, TypeError, KeyError, OSError, TimeoutError, OverflowError):
        latest = None
    with ThreadPoolExecutor(max_workers=len(COMPONENT_KEYS)) as executor:
        components = list(executor.map(lambda key: _component(key, sampled_at, deadline, fetch), COMPONENT_KEYS))
    return validate_snapshot({"schema_version": SCHEMA_VERSION, "sampled_at": sampled_at.isoformat(), "window_seconds": WINDOW_SECONDS,
                              "source_latest_at": latest, "components": components})


def write_snapshot(snapshot: dict, path: Path = OUTPUT_PATH) -> None:
    body = json.dumps(validate_snapshot(snapshot), allow_nan=False, separators=(",", ":")) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".telemetry-", delete=False) as handle:
            temporary = handle.name
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o640)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    write_snapshot(sample())
    print("Stored bounded request telemetry snapshot")


if __name__ == "__main__":
    main()
