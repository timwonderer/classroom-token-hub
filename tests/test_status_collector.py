import json
import sys
import types
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError

import pytest

from status.projection import EpistemicState, Outcome
from status.contracts import ExternalObservationRecord
from status.projection import EvidenceSource, ObservationClass
from status_service.collector import SIGNALS, _signal_map, collect
from status_service.store import FirestoreNoticeStore


NOW = datetime(2026, 9, 19, 19, 30, tzinfo=timezone.utc)


class RecordingStore:
    def __init__(self):
        self.records = []

    def append_observations(self, records):
        self.records.extend(records)


def payload(*, database="PASS", timestamp=NOW):
    signals = []
    for key, (layer, _) in SIGNALS.items():
        measured = key == "database"
        signals.append({
            "key": key, "layer": layer,
            "outcome": database if measured else "UNKNOWN",
            "epistemic_state": "KNOWN" if measured and database == "PASS" else "UNAVAILABLE",
            "diagnostic_code": ("DATABASE_REACHABLE" if database == "PASS" else "DATABASE_UNAVAILABLE") if measured else "CHECK_NOT_REGISTERED",
        })
    return json.dumps({"observed_at": timestamp.isoformat(), "signals": signals}).encode()


def test_collector_records_all_signals_with_one_correlation_and_no_raw_body():
    store = RecordingStore()
    records = collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: payload())
    assert len(records) == len(SIGNALS) + 1
    assert len({record.correlation_id for record in records}) == 1
    assert next(record for record in records if record.capability == "database").outcome == Outcome.PASS
    assert next(record for record in records if record.capability == "login").outcome == Outcome.UNKNOWN
    assert next(record for record in records if record.capability == "public_service_reachability").outcome == Outcome.PASS
    assert all("secret" not in repr(record) for record in records)
    assert all(record.observed_at == NOW for record in records)


def test_collector_default_clock_validates_and_stores_receipt_time(monkeypatch):
    receipt_time = NOW + timedelta(minutes=3)
    clock_reads = iter((NOW, receipt_time))

    class ReceiptClock(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz == timezone.utc
            return next(clock_reads)

    monkeypatch.setattr("status_service.collector.datetime", ReceiptClock)
    store = RecordingStore()
    records = collect(store, client_id="id", client_secret="secret",
                      fetch=lambda *_: payload(timestamp=receipt_time))

    database = next(record for record in records if record.capability == "database")
    assert database.outcome == Outcome.PASS
    assert database.epistemic_state == EpistemicState.KNOWN
    assert database.diagnostic_code == "DATABASE_REACHABLE"
    assert all(record.observed_at == receipt_time for record in records)
    assert store.records == records


def test_access_denial_is_not_reported_as_app_failure():
    store = RecordingStore()

    def denied(*_):
        raise HTTPError("https://app.classroomtokenhub.com/health/status", 302, "Access login", {}, None)

    records = collect(store, client_id="id", client_secret="secret", now=NOW, fetch=denied)
    assert all(record.outcome == Outcome.UNKNOWN for record in records)
    assert all(record.epistemic_state == EpistemicState.UNAVAILABLE for record in records)


def test_network_failure_records_reachability_failure_without_fabricating_feature_failure():
    store = RecordingStore()

    def unavailable(*_):
        raise URLError("network down")

    records = collect(store, client_id="id", client_secret="secret", now=NOW, fetch=unavailable)
    assert records[0].outcome == Outcome.FAIL
    assert records[0].epistemic_state == EpistemicState.UNAVAILABLE
    assert all(record.outcome == Outcome.UNKNOWN for record in records[1:])


def test_unregistered_or_stale_payload_fails_closed():
    store = RecordingStore()
    stale = payload(timestamp=datetime(2026, 9, 19, 19, 20, tzinfo=timezone.utc))
    records = collect(store, client_id="id", client_secret="secret", now=NOW, fetch=lambda *_: stale)
    assert records[0].outcome == Outcome.PASS  # The HTTP endpoint answered; feature evidence is unusable.
    assert all(record.outcome == Outcome.UNKNOWN for record in records[1:])
    malformed = json.loads(payload())
    malformed["signals"][0]["key"] = "tenant_42"
    try:
        _signal_map(json.dumps(malformed).encode(), NOW)
        assert False, "unregistered key accepted"
    except ValueError:
        pass


def test_health_response_accepts_bounded_clock_skew_but_rejects_future_payload():
    # A response generated after the poll began can be slightly ahead of the
    # collector's clock; an arbitrarily future response is not evidence.
    assert _signal_map(payload(timestamp=NOW + timedelta(seconds=1)), NOW)["database"][0] == Outcome.PASS
    with pytest.raises(ValueError, match="future"):
        _signal_map(payload(timestamp=NOW + timedelta(seconds=6)), NOW)


def test_diagnostic_cannot_claim_pass_for_unregistered_check():
    malformed = json.loads(payload())
    malformed["signals"][0]["outcome"] = "PASS"
    malformed["signals"][0]["epistemic_state"] = "KNOWN"
    store = RecordingStore()
    records = collect(store, client_id="id", client_secret="secret", now=NOW,
                      fetch=lambda *_: json.dumps(malformed).encode())
    assert all(record.outcome == Outcome.UNKNOWN for record in records[1:])


def test_network_os_error_is_unavailable():
    store = RecordingStore()

    def unavailable(*_):
        raise OSError("connection failed")

    records = collect(store, client_id="id", client_secret="secret", now=NOW, fetch=unavailable)
    assert records[0].outcome == Outcome.FAIL


def test_store_keeps_newest_current_and_append_only_history(monkeypatch):
    class Snapshot:
        def __init__(self, value):
            self.exists = value is not None
            self.value = value

        def to_dict(self):
            return self.value

    class Ref:
        def __init__(self, client, collection, key):
            self.client, self.collection, self.key = client, collection, key

        def get(self, transaction=None):
            return Snapshot(self.client.data[self.collection].get(self.key))

    class Collection:
        def __init__(self, client, name):
            self.client, self.name = client, name

        def document(self, key):
            return Ref(self.client, self.name, key)

    class Transaction:
        def __init__(self, client):
            self.client, self.writes = client, []

        def create(self, ref, value):
            self.writes.append(("create", ref, value))

        def set(self, ref, value):
            self.writes.append(("set", ref, value))

        def commit(self):
            for operation, ref, value in self.writes:
                if operation == "create":
                    assert ref.key not in self.client.data[ref.collection]
                self.client.data[ref.collection][ref.key] = value

    class Client:
        def __init__(self):
            self.data = {"external_status_current": {}, "external_status_observations": {}}

        def collection(self, name):
            return Collection(self, name)

        def transaction(self):
            return Transaction(self)

    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    cloud.firestore = types.SimpleNamespace(transactional=lambda function: lambda transaction: (function(transaction), transaction.commit()))
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    client = Client()
    store = FirestoreNoticeStore(client)

    def record(identifier, minute, outcome, epistemic):
        return ExternalObservationRecord(identifier, NOW.replace(minute=minute), "corr", EvidenceSource.EXTERNAL_PROBE,
                                         "login", ObservationClass.READINESS, outcome, epistemic, "CHECK", None, "v1")

    newer = record("newer", 31, Outcome.FAIL, EpistemicState.UNAVAILABLE)
    older = record("older", 30, Outcome.PASS, EpistemicState.KNOWN)
    tie_pass = record("tie-pass", 31, Outcome.PASS, EpistemicState.KNOWN)
    store.append_observations([newer])
    store.append_observations([older, tie_pass])  # Reverse completion order.
    assert client.data["external_status_current"]["login"]["observation_id"] == "newer"
    assert set(client.data["external_status_observations"]) == {"newer", "older", "tie-pass"}
    client = Client()
    store = FirestoreNoticeStore(client)
    store.append_observations([tie_pass])
    store.append_observations([newer])
    assert client.data["external_status_current"]["login"]["observation_id"] == "newer"
