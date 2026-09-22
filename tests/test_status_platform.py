"""Actual endpoint/database checks stay distinct from request-family proxies."""
from datetime import timedelta
import json
from urllib.error import HTTPError

import pytest

from status.platform import platform_rows, validate_platform
from status_service.collector import collect, collect_platform
from tests.test_status_measurements import NOW, snapshot


class Store:
    def append_platform(self, record):
        self.platform = record
    def append_snapshot(self, snapshot, received_at, diagnostic=None):
        self.telemetry = snapshot


def source(*, failed=False, checked_at=NOW):
    return {"observed_at": NOW.isoformat(), "signals": [
        {"key": "database", "layer": "platform", "outcome": "FAIL" if failed else "PASS",
         "epistemic_state": "UNAVAILABLE" if failed else "KNOWN",
         "diagnostic_code": "DATABASE_UNAVAILABLE" if failed else "DATABASE_REACHABLE",
         "checked_at": checked_at.isoformat()},
        {"key": "attendance", "layer": "capability", "outcome": "UNKNOWN", "epistemic_state": "UNAVAILABLE", "diagnostic_code": "CHECK_NOT_REGISTERED", "checked_at": None},
    ]}


@pytest.mark.parametrize("failed,expected", [(False, "PASS"), (True, "FAIL")])
def test_only_real_database_evidence_is_persisted(failed, expected):
    store = Store()
    result = collect_platform(store, client_id="id", client_secret="secret", now=NOW,
                              fetch=lambda *_: json.dumps(source(failed=failed)).encode())
    assert result["checks"][0]["outcome"] == "PASS"
    assert result["checks"][1]["outcome"] == expected
    assert result["checks"][1]["checked_at"] == NOW.isoformat()
    assert "attendance" not in json.dumps(result) and "CHECK_NOT_REGISTERED" not in json.dumps(result)
    assert store.platform == result


@pytest.mark.parametrize("code,endpoint", [(302, "UNKNOWN"), (401, "UNKNOWN"), (403, "UNKNOWN"), (500, "FAIL")])
def test_http_failure_never_invents_database_failure(code, endpoint):
    def fetch(*_):
        raise HTTPError("private", code, "private", {}, None)
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch=fetch)
    assert result["checks"][0]["outcome"] == endpoint
    assert result["checks"][1]["outcome"] == "UNKNOWN"
    assert result["checks"][1]["checked_at"] is None


def test_platform_outage_does_not_discard_request_telemetry():
    store = Store()
    collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: json.dumps(snapshot()).encode())
    def fetch(*_):
        raise OSError("private")
    collect_platform(store, client_id="id", client_secret="secret", now=NOW, fetch=fetch)
    assert store.telemetry == snapshot()
    assert all(check["outcome"] == "UNKNOWN" for check in store.platform["checks"])


@pytest.mark.parametrize("change", [
    lambda data: data["signals"].clear(),
    lambda data: data["signals"].append(data["signals"][0]),
    lambda data: data["signals"][0].update(outcome="PASS", diagnostic_code="DATABASE_UNAVAILABLE"),
    lambda data: data["signals"][0].update(checked_at=None),
    lambda data: data["signals"][0].update(checked_at=(NOW + timedelta(seconds=1)).isoformat()),
    lambda data: data["signals"][0].update(raw_error="private"),
    lambda data: data.update(raw_error="private"),
])
def test_invalid_database_payload_preserves_http_response_only(change):
    data = source()
    change(data)
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: json.dumps(data).encode())
    assert result["checks"][0]["outcome"] == "PASS"
    assert result["checks"][1]["diagnostic"] == "INVALID_RESPONSE"
    assert "private" not in json.dumps(result)


def test_stale_check_cannot_become_fresh_at_receipt_and_later_render():
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW,
                              fetch=lambda *_: json.dumps(source(checked_at=NOW - timedelta(seconds=301))).encode())
    assert result["checks"][1]["diagnostic"] == "STALE_SOURCE"
    fresh = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW,
                             fetch=lambda *_: json.dumps(source()).encode())
    assert all(row["state"] == "STALE" for row in platform_rows(fresh, now=NOW + timedelta(seconds=301)))
    assert all(row["state"] == "UNKNOWN" for row in platform_rows(None, now=NOW))
    fresh["checks"][1]["class_id"] = "private"
    with pytest.raises(ValueError):
        validate_platform(fresh)
    assert all(row["state"] == "UNKNOWN" for row in platform_rows(fresh, now=NOW))
