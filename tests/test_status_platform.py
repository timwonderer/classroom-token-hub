"""Actual endpoint/database checks stay distinct from request-family proxies."""
from datetime import timedelta
import json
from urllib.error import HTTPError

import pytest

from status.platform import platform_rows, validate_platform
from status_service.collector import collect, collect_platform
from tests.test_status_measurements import NOW, snapshot


def OPEN():
    return 200, None


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
    result = collect_platform(store, client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN,
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
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN, fetch=fetch)
    assert result["checks"][0]["outcome"] == endpoint
    assert result["checks"][1]["outcome"] == "UNKNOWN"
    assert result["checks"][1]["checked_at"] is None


def test_platform_outage_does_not_discard_request_telemetry():
    store = Store()
    collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: json.dumps(snapshot()).encode())
    def fetch(*_):
        raise OSError("private")
    collect_platform(store, client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN, fetch=fetch)
    assert store.telemetry == snapshot()
    assert all(check["outcome"] == "UNKNOWN" for check in store.platform["checks"] if check["key"] != "gate")


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
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN, fetch=lambda *_: json.dumps(data).encode())
    assert result["checks"][0]["outcome"] == "PASS"
    assert result["checks"][1]["diagnostic"] == "INVALID_RESPONSE"
    assert "private" not in json.dumps(result)


def test_stale_check_cannot_become_fresh_at_receipt_and_later_render():
    result = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN,
                              fetch=lambda *_: json.dumps(source(checked_at=NOW - timedelta(seconds=301))).encode())
    assert result["checks"][1]["diagnostic"] == "STALE_SOURCE"
    fresh = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW, fetch_gate=OPEN,
                             fetch=lambda *_: json.dumps(source()).encode())
    assert all(row["state"] == "STALE" for row in platform_rows(fresh, now=NOW + timedelta(seconds=301)))
    assert all(row["state"] == "UNKNOWN" for row in platform_rows(None, now=NOW))
    fresh["checks"][1]["class_id"] = "private"
    with pytest.raises(ValueError):
        validate_platform(fresh)
    assert all(row["state"] == "UNKNOWN" for row in platform_rows(fresh, now=NOW))


# ─── Application Availability Gate (SPEC-OPS-006 §Independent platform checks) ───

ACCESS_LOGIN = "https://cth.cloudflareaccess.com/cdn-cgi/access/login/app.classroomtokenhub.com"


def gate_result(fetch_gate, fetch=lambda *_: json.dumps(source()).encode()):
    record = collect_platform(Store(), client_id="id", client_secret="secret", now=NOW,
                              fetch=fetch, fetch_gate=fetch_gate)
    assert record["schema_version"] == "platform-check-v2"
    return next(check for check in record["checks"] if check["key"] == "gate"), record


@pytest.mark.parametrize("code", [302, 303, 307])
def test_access_login_redirect_is_a_closed_gate(code):
    gate, record = gate_result(lambda: (code, ACCESS_LOGIN))
    assert (gate["outcome"], gate["diagnostic"]) == ("FAIL", "GATE_CLOSED")
    assert gate["checked_at"] == NOW.isoformat()
    # An access restriction never becomes an application or database failure.
    assert [c["outcome"] for c in record["checks"] if c["key"] != "gate"] == ["PASS", "PASS"]


@pytest.mark.parametrize("code,location", [
    (200, None),
    (500, None),  # the app is down, but nothing stands in front of it
    (302, "/student/login"),  # the application's own redirect stays on its host
    (302, "https://cloudflareaccess.com.attacker.example/login"),  # a near miss on the host
    (302, "https://notcloudflareaccess.com/login"),
])
def test_anything_but_an_access_redirect_is_an_open_gate(code, location):
    gate, _ = gate_result(lambda: (code, location))
    assert (gate["outcome"], gate["diagnostic"]) == ("PASS", "GATE_OPEN")


@pytest.mark.parametrize("code", [401, 403])
def test_bare_denial_does_not_establish_a_closed_gate(code):
    gate, _ = gate_result(lambda: (code, None))
    assert (gate["outcome"], gate["diagnostic"], gate["checked_at"]) == ("UNKNOWN", "UNEXPECTED_DENIAL", None)


def test_gate_transport_failure_is_unknown():
    def fail():
        raise OSError("private network details")
    gate, record = gate_result(fail)
    assert (gate["outcome"], gate["diagnostic"]) == ("UNKNOWN", "TRANSPORT_UNAVAILABLE")
    assert "private" not in json.dumps(record)


def test_lapsed_service_token_never_reads_as_a_closed_gate():
    def denied(*_):
        raise HTTPError("private", 302, "private", {"Location": ACCESS_LOGIN}, None)
    gate, record = gate_result(lambda: (200, None), fetch=denied)
    assert record["checks"][0]["diagnostic"] == "ACCESS_DENIED"
    assert (gate["outcome"], gate["diagnostic"]) == ("PASS", "GATE_OPEN")


def test_gate_probe_sends_no_credential(monkeypatch):
    import status_service.collector as module
    seen = {}

    class Opener:
        def open(self, request, timeout):
            seen["headers"] = {key.lower() for key in request.headers}
            seen["url"] = request.full_url
            raise HTTPError(request.full_url, 302, "Found", {"Location": ACCESS_LOGIN}, None)

    monkeypatch.setattr(module, "build_opener", lambda *handlers: Opener())
    assert module.fetch_gate() == (302, ACCESS_LOGIN)
    assert not any(header.startswith("cf-access") or header == "authorization" for header in seen["headers"])
    assert seen["url"] == module.GATE_URL


def test_v1_records_stay_readable_and_carry_no_gate():
    from tests.test_status_store import platform_record
    record = validate_platform(platform_record(NOW))
    rows = platform_rows(record, now=NOW)
    assert [row["key"] for row in rows] == ["endpoint", "database"]


@pytest.mark.parametrize("change", [
    lambda r: r["checks"].pop(),  # v2 without its gate
    lambda r: r["checks"][2].update(outcome="PASS", diagnostic="GATE_CLOSED"),
    lambda r: r["checks"][2].update(outcome="FAIL", diagnostic="ACCESS_DENIED"),
    lambda r: r.update(schema_version="platform-check-v3"),
])
def test_invalid_gate_records_are_rejected(change):
    _, record = gate_result(lambda: (302, ACCESS_LOGIN))
    change(record)
    with pytest.raises(ValueError):
        validate_platform(record)
