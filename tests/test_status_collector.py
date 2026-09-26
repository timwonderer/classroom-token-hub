"""Collector preserves source time and records bounded transport failures."""
from datetime import timedelta
import json
from urllib.error import HTTPError

import pytest

from status_service.collector import collect
from tests.test_status_measurements import NOW, snapshot


class Store:
    def append_snapshot(self, snapshot_or_none, received_at, diagnostic=None):
        self.record = (snapshot_or_none, received_at, diagnostic)


def test_valid_transport_keeps_source_time_and_separate_receipt():
    store = Store()
    source = snapshot()
    result = collect(store, client_id="id", client_secret="secret", now=NOW + timedelta(seconds=20), fetch=lambda *_: json.dumps(source).encode())
    assert result == source
    assert store.record == (source, NOW + timedelta(seconds=20), None)


@pytest.mark.parametrize("code,diagnostic", [(401, "ACCESS_DENIED"), (403, "ACCESS_DENIED"), (302, "ACCESS_DENIED"), (500, "TRANSPORT_UNAVAILABLE")])
def test_http_failure_has_no_fabricated_source_sample(code, diagnostic):
    def fetch(*_):
        raise HTTPError("hidden", code, "hidden", {}, None)
    store = Store()
    assert collect(store, client_id="id", client_secret="secret", now=NOW, fetch=fetch) is None
    assert store.record == (None, NOW, diagnostic)


@pytest.mark.parametrize("body", [b"{}", b"null", b"x"*16385, b'{"x":1,"x":2}', json.dumps({**snapshot(), "raw_logs": "secret"}).encode()])
def test_invalid_payload_records_only_closed_diagnostic(body):
    store = Store()
    collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: body)
    assert store.record == (None, NOW, "INVALID_SNAPSHOT")


def test_huge_json_numeric_is_rejected_without_crashing():
    data = snapshot()
    data["components"][0]["p95_ms"] = 10**500
    store = Store()
    collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: json.dumps(data).encode())
    assert store.record == (None, NOW, "INVALID_SNAPSHOT")


def test_stale_and_network_failures_remain_distinct():
    store = Store()
    collect(store, client_id="id", client_secret="secret", now=NOW + timedelta(seconds=301), fetch=lambda *_: json.dumps(snapshot()).encode())
    assert store.record[2] == "STALE_SNAPSHOT"
    def fail(*_):
        raise OSError("private network details")
    collect(store, client_id="id", client_secret="secret", now=NOW, fetch=fail)
    assert store.record == (None, NOW, "TRANSPORT_UNAVAILABLE")


def test_validation_and_store_use_one_post_fetch_clock(monkeypatch):
    import status_service.collector as module
    calls = []
    class Clock:
        @staticmethod
        def now(zone):
            calls.append(zone)
            # A second read would cross the allowed300-second freshness boundary.
            return NOW + timedelta(seconds=300 if len(calls) == 1 else 301)
    monkeypatch.setattr(module, "datetime", Clock)
    class CheckingStore(Store):
        def append_snapshot(self, snapshot_or_none, received_at, diagnostic=None):
            from status.measurements import validate_fresh_snapshot
            validate_fresh_snapshot(snapshot_or_none, received_at)
            super().append_snapshot(snapshot_or_none, received_at, diagnostic)
    store = CheckingStore()
    result = collect(store, client_id="id", client_secret="secret", fetch=lambda *_: json.dumps(snapshot()).encode())
    assert result is not None and len(calls) == 1
    assert store.record[1] == NOW + timedelta(seconds=300)
