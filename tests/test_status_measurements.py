"""Public HTTP measurements cannot become business correctness claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, classify_component, unavailable_component, validate_fresh_snapshot, validate_snapshot

NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def snapshot(count=100):
    components = []
    for key in COMPONENT_KEYS:
        row = {"key": key, "collection_state": "OK", **{field: 0 for field in COUNT_FIELDS},
               "p80_ms": 100 if count else None, "p95_ms": 200 if count else None}
        row.update(request_count=count, http_2xx_count=count)
        components.append(row)
    return {"schema_version": "request-telemetry-v1", "sampled_at": NOW.isoformat(), "window_seconds": 300,
            "source_latest_at": (NOW - timedelta(seconds=10)).isoformat(), "components": components}


def test_traffic_empty_and_unavailable_are_distinct():
    for count, expected in [(0, "NO_TRAFFIC"), (1, "NORMAL"), (20, "NORMAL")]:
        data = validate_snapshot(snapshot(count))
        result = classify_component(data["components"][0], data, now=NOW)
        assert result["state"] == expected
        assert result["http_500_percent"] == (0 if count else None)
    data = snapshot()
    data["components"][0] = unavailable_component("service")
    assert classify_component(data["components"][0], validate_snapshot(data), now=NOW)["state"] == "MONITOR_UNAVAILABLE"


def test_codes_counts_and_multiple_visible_reasons():
    data = snapshot()
    row = data["components"][0]
    row.update(http_2xx_count=87, http_4xx_count=10, http_404_count=6, http_5xx_count=3, http_500_count=1, p95_ms=1600)
    result = classify_component(row, validate_snapshot(data), now=NOW)
    assert result["state"] == "ELEVATED_ERRORS"
    assert (result["http_404_percent"], result["http_500_percent"], result["http_5xx_percent"]) == (6, 1, 3)
    assert len(result["reasons"]) == 3
    assert "not-found" in result["reasons"][1]


def test_thresholds_are_strict_and_small_samples_can_show_errors():
    data = snapshot()
    row = data["components"][0]
    row.update(http_2xx_count=93, http_4xx_count=5, http_404_count=5, http_5xx_count=2, p95_ms=1500)
    assert classify_component(row, validate_snapshot(data), now=NOW)["state"] == "NORMAL"
    data = snapshot(1)
    row = data["components"][0]
    row.update(http_2xx_count=0, http_5xx_count=1, http_500_count=1)
    assert classify_component(row, validate_snapshot(data), now=NOW)["state"] == "ELEVATED_ERRORS"


@pytest.mark.parametrize("change", [
    lambda data: data.update(raw_logs="private"),
    lambda data: data.update(window_seconds=True),
    lambda data: data.update(sampled_at="2026-09-22T12:00:00"),
    lambda data: data.update(source_latest_at=(NOW + timedelta(seconds=1)).isoformat()),
    lambda data: data["components"].append(deepcopy(data["components"][0])),
    lambda data: data["components"][0].update(uri="/student/private"),
    lambda data: data["components"][0].update(request_count=True),
    lambda data: data["components"][0].update(request_count=101),
    lambda data: data["components"][0].update(http_404_count=1),
    lambda data: data["components"][0].update(p95_ms=float("nan")),
    lambda data: data["components"][0].update(p95_ms=float("inf")),
    lambda data: data["components"][0].update(p95_ms=10**500),
    lambda data: data["components"][0].update(p80_ms=300),
    lambda data: data["components"][0].update(p95_ms=None),
    lambda data: data["components"][0].update(collection_state="UNAVAILABLE"),
])
def test_rejects_malformed_or_sensitive_schema(change):
    data = snapshot()
    change(data)
    with pytest.raises(ValueError):
        validate_snapshot(data)


def test_source_freshness_does_not_renew_with_new_sample_or_receipt():
    data = snapshot()
    data["source_latest_at"] = (NOW - timedelta(seconds=181)).isoformat()
    assert classify_component(data["components"][0], validate_snapshot(data), now=NOW)["state"] == "STALE"
    data["source_latest_at"] = None
    assert classify_component(data["components"][0], data, now=NOW)["state"] == "MONITOR_UNAVAILABLE"
    with pytest.raises(ValueError):
        validate_fresh_snapshot(snapshot(), NOW + timedelta(seconds=301))
    with pytest.raises(ValueError):
        validate_fresh_snapshot(snapshot(), NOW - timedelta(seconds=1))
