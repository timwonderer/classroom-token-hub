"""Minute idempotency, ordering and history projection at the Firestore boundary."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sys
import pytest
from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION
from status_service.store import FirestoreNoticeStore

NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)

def sample(at=NOW, count=20):
    return {"schema_version": SCHEMA_VERSION, "sampled_at": at.isoformat(), "source_latest_at": at.isoformat(), "window_seconds": 300,
            "components": [{"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0),
                            "request_count": count, "http_2xx_count": count,
                            "p80_ms": 100 if count else None, "p95_ms": 200 if count else None} for key in COMPONENT_KEYS]}

@pytest.fixture
def database(monkeypatch):
    data = {}
    class Ref:
        def __init__(self, collection, key): self.collection, self.key = collection, key
        def get(self, transaction=None):
            if transaction: assert not transaction.writes, "Firestore reads must precede writes"
            value = deepcopy(data.get(self.collection, {}).get(self.key))
            return SimpleNamespace(id=self.key, exists=value is not None, to_dict=lambda: value)
    class Transaction:
        def __init__(self): self.writes = []
        def create(self, ref, value):
            assert ref.key not in data.get(ref.collection, {})
            self.writes.append((ref, value))
        def set(self, ref, value): self.writes.append((ref, value))
    def transactional(function):
        def run(transaction):
            function(transaction)
            for ref, value in transaction.writes: data.setdefault(ref.collection, {})[ref.key] = deepcopy(value)
        return run
    client = SimpleNamespace(transaction=Transaction, collection=lambda name: SimpleNamespace(document=lambda key: Ref(name, key)),
                             get_all=lambda refs: [ref.get() for ref in refs])
    firestore = SimpleNamespace(transactional=transactional)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", firestore)
    monkeypatch.setitem(sys.modules, "google.cloud", SimpleNamespace(firestore=firestore))
    return FirestoreNoticeStore(client), data

def test_source_minute_duplicate_does_not_inflate_rollup(database):
    store, data = database
    store.append_snapshot(sample(), NOW)
    store.append_snapshot(sample(), NOW + timedelta(seconds=15))
    assert len(data["telemetry_snapshots"]) == 1
    day = data["telemetry_days"]["2026-09-21"]["components"]["attendance"]
    assert day == dict(sampled=1, measured=1, normal=1, elevated_errors=0, high_latency=0, other=0)
    assert store.current_snapshot()["received_at"] == NOW

def test_failure_does_not_poison_valid_same_minute(database):
    store, data = database
    store.append_snapshot(None, NOW + timedelta(seconds=1), "TRANSPORT_UNAVAILABLE")
    store.append_snapshot(sample(), NOW + timedelta(seconds=2))
    assert store.current_snapshot()["snapshot"] == sample()
    assert len(data["telemetry_attempts"]) == 1

def test_delayed_duplicate_cannot_hide_newer_failure(database):
    store, _ = database
    store.append_snapshot(sample(), NOW)
    store.append_snapshot(None, NOW + timedelta(minutes=1), "ACCESS_DENIED")
    store.append_snapshot(sample(), NOW + timedelta(minutes=1, seconds=1))
    assert store.current_snapshot()["diagnostic"] == "ACCESS_DENIED"

def test_out_of_order_source_preserves_current_and_day_attribution(database):
    store, data = database
    midnight = NOW.replace(hour=0)
    store.append_snapshot(sample(midnight), midnight)
    prior = midnight - timedelta(minutes=1)
    store.append_snapshot(sample(prior), midnight + timedelta(seconds=1))
    assert store.current_snapshot()["snapshot"]["sampled_at"] == midnight.isoformat()
    assert set(data["telemetry_days"]) == {"2026-09-20", "2026-09-21"}

def test_idle_windows_are_sampled_not_measured(database):
    store, data = database
    store.append_snapshot(sample(count=0), NOW)
    counters = data["telemetry_days"]["2026-09-21"]["components"]["service"]
    assert counters["sampled"] == counters["other"] == 1
    assert counters["normal"] == counters["measured"] == 0

def test_stale_or_unbounded_write_rejected_without_side_effect(database):
    store, data = database
    with pytest.raises(ValueError): store.append_snapshot(sample(), NOW + timedelta(minutes=6))
    with pytest.raises(ValueError): store.append_snapshot(None, NOW, "raw error with user data")
    assert data == {}

def test_history_returns_gaps_without_writes(database):
    store, data = database
    history = store.measurement_history()
    assert len(history) == 90
    assert all(day["components"] == {} for day in history)
    assert data == {}


def platform_record(at=NOW, failed=False):
    return {"schema_version": "platform-check-v1", "received_at": at.isoformat(), "checks": [
        {"key": "endpoint", "outcome": "PASS", "checked_at": at.isoformat(), "diagnostic": "HTTP_OK"},
        {"key": "database", "outcome": "FAIL" if failed else "PASS", "checked_at": at.isoformat(),
         "diagnostic": "DATABASE_UNAVAILABLE" if failed else "DATABASE_REACHABLE"},
    ]}


def test_platform_check_storage_is_independent_append_only_and_monotonic(database):
    store, data = database
    assert store.current_platform() is None
    store.append_snapshot(sample(), NOW)
    prior_telemetry = deepcopy(store.current_snapshot())
    newer = platform_record(NOW + timedelta(seconds=30), failed=True)
    store.append_platform(newer)
    store.append_platform(platform_record())
    assert store.current_platform() == newer
    assert store.current_snapshot() == prior_telemetry
    assert len(data["platform_observations"]) == 2
    assert all(value["expires_at"] == datetime.fromisoformat(value["received_at"]) + timedelta(days=7)
               for value in data["platform_observations"].values())
    assert data["telemetry_days"]["2026-09-21"]["components"]["service"]["sampled"] == 1


def test_platform_store_rejects_unbounded_records_without_side_effects(database):
    store, data = database
    value = platform_record()
    value["raw_error"] = "sensitive"
    with pytest.raises(ValueError):
        store.append_platform(value)
    assert data == {}


def test_activity_survives_idle_and_failed_collection_then_records_recovery(database):
    store, _ = database
    burst = sample(count=1)
    burst['components'][2].update(http_2xx_count=0, http_5xx_count=1, http_500_count=1)
    store.append_snapshot(burst, NOW)
    original = deepcopy(store.current_snapshot()['last_activity'])
    later = NOW + timedelta(minutes=10)
    store.append_snapshot(sample(later, count=0), later)
    assert store.current_snapshot()['last_activity'] == original
    store.append_snapshot(None, later + timedelta(minutes=1), 'ACCESS_DENIED')
    assert store.current_snapshot()['last_activity'] == original
    # A delayed duplicate cannot replace the retained error or current failure.
    store.append_snapshot(sample(later, count=1), later + timedelta(minutes=2))
    assert store.current_snapshot()['last_activity'] == original
    recovery = later + timedelta(minutes=3)
    store.append_snapshot(sample(recovery, count=1), recovery)
    activity = store.current_snapshot()['last_activity']['attendance']
    assert activity['component']['http_5xx_count'] == 0
    assert activity['sampled_at'] == recovery.isoformat()


def test_stale_source_does_not_replace_activity_and_expired_context_is_pruned(database):
    store, _ = database
    store.append_snapshot(sample(count=1), NOW)
    original = deepcopy(store.current_snapshot()['last_activity'])
    later = NOW + timedelta(minutes=10)
    stale = sample(later)
    stale['source_latest_at'] = NOW.isoformat()
    store.append_snapshot(stale, later)
    assert store.current_snapshot()['last_activity'] == original
    expired = NOW + timedelta(days=8)
    store.append_snapshot(sample(expired, count=0), expired)
    assert store.current_snapshot()['last_activity'] == {}


def test_corrupt_retained_context_cannot_poison_collector(database):
    store, data = database
    store.append_snapshot(sample(count=1), NOW)
    data['telemetry_current']['current']['last_activity']['attendance']['component']['raw_log'] = 'PRIVATE'
    later = NOW + timedelta(minutes=10)
    store.append_snapshot(sample(later, count=0), later)
    assert 'attendance' not in store.current_snapshot()['last_activity']
    assert 'login' in store.current_snapshot()['last_activity']
