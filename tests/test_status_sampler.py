"""Closed Loki queries, combined samples and bounded public payloads."""
from datetime import timedelta
import json

import pytest

from status_service.log_sampler import sample, write_snapshot
from tests.test_status_measurements import NOW, snapshot


def fake_loki(endpoint, params, *, timeout):
    assert 0 < timeout <= 5
    if endpoint == "query_range":
        assert params["direction"] == "backward" and params["limit"] == 1
        assert 'line_format "entry"' in params["query"]
        return {"status": "success", "data": {"resultType": "streams", "result": [
            {"stream": {"job": "nginx_access"}, "values": [[str(int((NOW - timedelta(seconds=10)).timestamp() * 1e9)), "entry"]]}]}}
    assert params["time"] == NOW.isoformat()
    query = params["query"]
    assert 'upstream_addr="127.0.0.1:8000"' in query
    if "sum by (status)" in query:
        result = [{"metric": {"status": code}, "value": [NOW.timestamp(), str(count)]} for code, count in [("200", 90), ("404", 6), ("500", 1), ("502", 3)]]
    else:
        value = "0.1" if "0.80" in query else "0.2" if "0.95" in query else "100"
        if "quantile_over_time" in query:
            assert query.endswith("by ()")
        result = [{"metric": {}, "value": [NOW.timestamp(), value]}]
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


def test_closed_queries_reduce_code_counts_and_combined_quantiles():
    output = sample(now=NOW + timedelta(seconds=17), fetch=fake_loki)
    assert output["sampled_at"] == NOW.isoformat()
    for row in output["components"]:
        assert row["request_count"] == 100
        assert (row["http_404_count"], row["http_500_count"], row["http_5xx_count"]) == (6, 1, 4)
        assert (row["p80_ms"], row["p95_ms"]) == (100, 200)
    assert "metric" not in json.dumps(output) and "uri" not in json.dumps(output)


@pytest.mark.parametrize("failure", ["labels", "duplicate", "wrong_time", "partial_latency", "nan", "outage", "unknown_code"])
def test_bad_metric_evidence_is_unavailable_not_zero(failure):
    def fetch(endpoint, params, *, timeout):
        data = fake_loki(endpoint, params, timeout=timeout)
        if endpoint == "query_range":
            return data
        if failure == "outage":
            raise TimeoutError()
        result = data["data"]["result"]
        if failure == "labels":
            result[0]["metric"]["user"] = "sensitive"
        elif failure == "duplicate":
            result.append(result[0])
        elif failure == "wrong_time":
            result[0]["value"][0] -= 60
        elif failure == "partial_latency" and "request_time >=" in params["query"]:
            result[0]["value"][1] = "99"
        elif failure == "nan":
            result[0]["value"][1] = "NaN"
        elif failure == "unknown_code" and "sum by (status)" in params["query"]:
            result[0]["metric"]["status"] = "unknown"
        return data
    output = sample(now=NOW, fetch=fetch)
    assert all(row["collection_state"] == "UNAVAILABLE" and row["request_count"] is None for row in output["components"])
    assert "sensitive" not in json.dumps(output)


def test_empty_source_and_route_are_not_invented_activity():
    def empty(endpoint, params, *, timeout):
        return {"status": "success", "data": {"resultType": "streams" if endpoint == "query_range" else "vector", "result": []}}
    output = sample(now=NOW, fetch=empty)
    assert output["source_latest_at"] is None
    assert all(row["request_count"] == 0 and row["p95_ms"] is None for row in output["components"])


def test_atomic_output_is_valid_json_and_readable_by_nginx_group(tmp_path):
    destination = tmp_path / "telemetry.json"
    destination.write_text("old")
    write_snapshot(snapshot(), destination)
    assert json.loads(destination.read_text()) == snapshot()
    assert destination.stat().st_mode & 0o777 == 0o640
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("malformation", ["null_series", "nan_time", "null_event", "boolean_value"])
def test_malformed_loki_elements_and_timestamps_fail_closed(malformation):
    def fetch(endpoint, params, *, timeout):
        result = fake_loki(endpoint, params, timeout=timeout)
        if malformation == "null_event" and endpoint == "query_range":
            result["data"]["result"] = [None]
        elif malformation == "null_series" and endpoint == "query":
            result["data"]["result"] = [None]
        elif malformation == "nan_time" and endpoint == "query":
            result["data"]["result"][0]["value"][0] = float("nan")
        elif malformation == "boolean_value" and endpoint == "query":
            result["data"]["result"][0]["value"][1] = True
        return result
    output = sample(now=NOW, fetch=fetch)
    if malformation == "null_event":
        assert output["source_latest_at"] is None
    else:
        assert all(row["collection_state"] == "UNAVAILABLE" for row in output["components"])
