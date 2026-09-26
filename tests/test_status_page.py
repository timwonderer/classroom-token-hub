"""Public numerical observations do not inherit human or integrity verdicts."""
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
import sys
import pytest
from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION
from tests.test_status_store import platform_record

@pytest.fixture
def page(monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = {"schema_version": SCHEMA_VERSION, "sampled_at": now.isoformat(), "source_latest_at": now.isoformat(), "window_seconds": 300,
                "components": [{"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0), "request_count": 20,
                                "http_2xx_count": 20, "p80_ms": 100, "p95_ms": 200} for key in COMPONENT_KEYS]}
    store = SimpleNamespace(current_platform=lambda: platform_record(now), list_active_notices=lambda: [], current_snapshot=lambda: {"snapshot": snapshot, "received_at": now, "diagnostic": None},
                            measurement_history=lambda: [{"date": now.date().isoformat(), "components": {}, "scheduled_minutes": 720}])
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")
    # Import the module-level app without real credentials or a Firestore client.
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", SimpleNamespace(Client=lambda **kwargs: store))
    monkeypatch.setitem(sys.modules, "google.cloud", SimpleNamespace(firestore=sys.modules["google.cloud.firestore"]))
    module = import_module("status_service.app")
    app = module.create_app(store=store)
    return app.test_client(), store, snapshot

def test_public_page_separates_measurements_and_notices(page):
    client, _, _ = page
    html = client.get("/").get_data(as_text=True)
    assert "Within expected range" in html
    assert "HTTP 500" in html and "p80" in html and "p95" in html
    assert "The app is responding and its database connection check passed." in html
    assert "Everything is working" not in html and "Platform health" not in html
    assert html.count('class="history-disclosure"') == 6
    assert "No eligible measurements" in html

def test_stale_snapshot_never_displays_old_latency_as_current(page):
    client, _, snapshot = page
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    snapshot["sampled_at"] = snapshot["source_latest_at"] = old
    for item in snapshot["components"]: item["p95_ms"] = 3456
    html = client.get("/").get_data(as_text=True)
    assert "Monitoring out of date" in html
    assert "3456 ms" not in html and "High latency observed" not in html

def test_corrupt_persisted_snapshot_fails_closed(page):
    client, _, snapshot = page
    snapshot["raw_log"] = "PRIVATE PAYLOAD"
    html = client.get("/").get_data(as_text=True)
    assert "Monitoring unavailable" in html
    assert "PRIVATE PAYLOAD" not in html

def test_not_found_measurement_does_not_claim_system_failure(page):
    client, _, snapshot = page
    component = snapshot["components"][0]
    component.update(http_2xx_count=18, http_4xx_count=2, http_404_count=2)
    html = client.get("/").get_data(as_text=True)
    assert "Elevated not-found responses" in html
    assert "SYSTEM_FAILURE" not in html

def test_public_operator_endpoints_remain_unavailable(page):
    client, _, _ = page
    assert client.get("/operator/notices").status_code == 404
    assert client.post("/operator/notices").status_code == 404


@pytest.mark.parametrize("value,expected", [
    ("2026-09-22T01:00:00+02:00", "2026-09-21 23:00 UTC"),
    ("2026-09-22T01:00:00", "2026-09-22 01:00 (timezone not provided)"),
    ("invalid", "Time unavailable"),
    (None, "Time unavailable"),
])
def test_notice_display_never_invents_timezone(page, value, expected):
    from status_service.app import format_status_time
    assert format_status_time(value) == expected


def test_mockup_order_and_simple_cards(page):
    client, _, _ = page
    html = client.get("/").get_data(as_text=True)
    assert html.index('class="landing-hero"') < html.index('id="happening-heading"') < html.index('id="working-heading"') < html.index('id="platform-heading"')
    cards = html.split('<div class="capability-grid">', 1)[1].split('</section>', 1)[0]
    assert cards.count('>Requests responding</div>') == 5
    assert 'HTTP 500' not in cards and 'p95' not in cards and 'history-disclosure' not in cards
    assert 'Database access' in html and 'Application endpoint' in html
    assert 'local_atm' in html and 'finance_mode' in html
    assert 'mailto:support@classroomtokenhub.com' in html


@pytest.mark.parametrize("total,errors,label", [(20, 1, "Server errors observed"), (10, 5, "Server errors observed"), (1, 1, "Server errors observed"), (1, 0, "Requests responding")])
def test_teacher_estimate_thresholds(page, total, errors, label):
    client, _, snapshot = page
    row = next(item for item in snapshot['components'] if item['key'] == 'attendance')
    row.update(request_count=total, http_2xx_count=total-errors, http_5xx_count=errors, http_500_count=errors)
    html = client.get('/').get_data(as_text=True)
    assert f'>{label}</div>' in html


def test_global_unmapped_request_failure_controls_hero(page):
    client, _, snapshot = page
    row = snapshot['components'][0]
    row.update(http_2xx_count=0, http_5xx_count=20, http_500_count=20)
    html = client.get('/').get_data(as_text=True)
    hero = html.split('class="landing-hero"', 1)[1].split('</section>', 1)[0]
    assert 'ISSUES REPORTED' in hero
    assert '>Requests responding</div>' in html


def test_human_notice_prevents_reassuring_hero(page):
    client, store, _ = page
    store.list_active_notices = lambda: [dict(capability='attendance', state='INVESTIGATING', impact_statement='Clock-in issue.', recommended_user_action='Please wait.', updated_at=datetime.now(timezone.utc), incident_ref='review-1')]
    html = client.get('/').get_data(as_text=True)
    hero = html.split('class="landing-hero"', 1)[1].split('</section>', 1)[0]
    assert 'ISSUES REPORTED' in hero


def idle(snapshot):
    for row in snapshot["components"]:
        row.update(dict.fromkeys(COUNT_FIELDS, 0), p80_ms=None, p95_ms=None)


def hero(html):
    return html.split('class="landing-hero"', 1)[1].split('</section>', 1)[0]


def test_quiet_period_keeps_availability_and_timestamped_activity(page):
    from copy import deepcopy
    client, store, snapshot = page
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    activity = {"attendance": {"sampled_at": past, "source_latest_at": past,
                              "component": deepcopy(snapshot["components"][2])}}
    store.current_snapshot = lambda: {"snapshot": snapshot, "last_activity": activity}
    idle(snapshot)
    html = client.get('/').get_data(as_text=True)
    assert 'APP REACHABLE' in hero(html)
    assert 'No recent activity</div>' in html
    assert 'Last observed: Requests responding' in html
    assert past[:10] in html and '(five-minute window ending then)' in html
    assert 'capability-card--available' not in html


@pytest.mark.parametrize('age', [-60, 301])
def test_fresh_request_traffic_cannot_mask_invalid_availability_checks(page, age):
    client, store, _ = page
    store.current_platform = lambda: platform_record(datetime.now(timezone.utc) - timedelta(seconds=age))
    assert 'AVAILABILITY NOT VERIFIED' in hero(client.get('/').get_data(as_text=True))


def test_platform_failure_controls_hero_without_request_traffic(page):
    client, store, snapshot = page
    idle(snapshot)
    store.current_platform = lambda: platform_record(datetime.fromisoformat(snapshot["sampled_at"]), failed=True)
    assert 'AVAILABILITY CHECK FAILED' in hero(client.get('/').get_data(as_text=True))


def test_404_only_does_not_declare_outage_or_successful_activity(page):
    client, _, snapshot = page
    for row in snapshot['components']:
        row.update(request_count=1, http_2xx_count=0, http_4xx_count=1, http_404_count=1)
    html = client.get('/').get_data(as_text=True)
    assert 'APP REACHABLE' in hero(html)
    assert html.count('Requests declined or not found</div>') == 5
    assert 'Probably not' not in html
    assert 'Elevated not-found responses' in html


@pytest.mark.parametrize('kind', ['expired', 'future', 'corrupt', 'stale_source'])
def test_invalid_historical_activity_is_not_rendered(page, kind):
    from copy import deepcopy
    client, store, snapshot = page
    at = datetime.now(timezone.utc) + timedelta(days=-8 if kind == 'expired' else 1 if kind == 'future' else -1)
    value = {'sampled_at': at.isoformat(), 'source_latest_at': at.isoformat(),
             'component': deepcopy(snapshot['components'][2])}
    if kind == 'corrupt': value['component']['raw_log'] = 'PRIVATE'
    if kind == 'stale_source': value['source_latest_at'] = (at-timedelta(hours=1)).isoformat()
    store.current_snapshot = lambda: {'snapshot': snapshot, 'last_activity': {'attendance': value}}
    idle(snapshot)
    html = client.get('/').get_data(as_text=True)
    assert 'Last observed:' not in html and 'PRIVATE' not in html


def test_failed_collection_shows_history_without_claiming_current_health(page):
    from copy import deepcopy
    client, store, snapshot = page
    value = {'sampled_at': snapshot['sampled_at'], 'source_latest_at': snapshot['source_latest_at'],
             'component': deepcopy(snapshot['components'][2])}
    store.current_snapshot = lambda: {'snapshot': None, 'last_activity': {'attendance': value}}
    html = client.get('/').get_data(as_text=True)
    assert 'Monitoring unavailable</div>' in html
    assert 'Last observed: Requests responding' in html
    assert 'capability-card--available' not in html
    assert 'APP REACHABLE' in hero(html)
