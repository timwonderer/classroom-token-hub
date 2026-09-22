"""Public numerical observations do not inherit human or integrity verdicts."""
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
import sys
import pytest
from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION

@pytest.fixture
def page(monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = {"schema_version": SCHEMA_VERSION, "sampled_at": now.isoformat(), "source_latest_at": now.isoformat(), "window_seconds": 300,
                "components": [{"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0), "request_count": 20,
                                "http_2xx_count": 20, "p80_ms": 100, "p95_ms": 200} for key in COMPONENT_KEYS]}
    store = SimpleNamespace(current_platform=lambda: None, list_active_notices=lambda: [], current_snapshot=lambda: {"snapshot": snapshot, "received_at": now, "diagnostic": None},
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
    assert "Everything is looking good." in html
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
    assert cards.count('>Yes</div>') == 5
    assert 'HTTP 500' not in cards and 'p95' not in cards and 'history-disclosure' not in cards
    assert 'Database access' in html and 'Application endpoint' in html
    assert 'local_atm' in html and 'finance_mode' in html
    assert 'mailto:support@classroomtokenhub.com' in html


@pytest.mark.parametrize("total,errors,label", [(20, 1, "Probably not"), (10, 5, "Possibly down"), (9, 5, "Probably not"), (5, 0, "Not recently verified")])
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
    assert 'POSSIBLY DOWN' in hero
    assert '>Yes</div>' in html


def test_human_notice_prevents_reassuring_hero(page):
    client, store, _ = page
    store.list_active_notices = lambda: [dict(capability='attendance', state='INVESTIGATING', impact_statement='Clock-in issue.', recommended_user_action='Please wait.', updated_at=datetime.now(timezone.utc), incident_ref='review-1')]
    html = client.get('/').get_data(as_text=True)
    hero = html.split('class="landing-hero"', 1)[1].split('</section>', 1)[0]
    assert 'SERVICE ISSUES' in hero
