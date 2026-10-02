"""Public numerical observations do not inherit human or integrity verdicts.

Labels and precedence follow SPEC-OPS-006 §VIII v1.3.
"""
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
import re
import sys
import pytest
from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION
from tests.test_status_store import platform_record


def gated_record(at, *, gate="GATE_OPEN", failed=False):
    """A platform-check-v2 record carrying the access-gate check."""
    record = platform_record(at, failed=failed)
    record["schema_version"] = "platform-check-v2"
    outcome = {"GATE_OPEN": "PASS", "GATE_CLOSED": "FAIL"}.get(gate, "UNKNOWN")
    record["checks"].append({"key": "gate", "outcome": outcome,
                             "checked_at": at.isoformat() if outcome != "UNKNOWN" else None,
                             "diagnostic": gate})
    return record


@pytest.fixture
def page(monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = {"schema_version": SCHEMA_VERSION, "sampled_at": now.isoformat(), "source_latest_at": now.isoformat(), "window_seconds": 300,
                "components": [{"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0), "request_count": 20,
                                "http_2xx_count": 20, "p80_ms": 100, "p95_ms": 200} for key in COMPONENT_KEYS]}
    store = SimpleNamespace(current_platform=lambda: platform_record(now), list_active_notices=lambda: [], current_snapshot=lambda: {"snapshot": snapshot, "received_at": now, "diagnostic": None},
                            measurement_history=lambda: [{"date": now.date().isoformat(), "components": {}, "scheduled_minutes": 720}],
                            list_resolved_notices=lambda page=1, page_size=20: ([], False))
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")
    # Import the module-level app without real credentials or a Firestore client.
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", SimpleNamespace(Client=lambda **kwargs: store))
    monkeypatch.setitem(sys.modules, "google.cloud", SimpleNamespace(firestore=sys.modules["google.cloud.firestore"]))
    module = import_module("status_service.app")
    app = module.create_app(store=store)
    return app.test_client(), store, snapshot


def hero(html):
    return html.split('class="landing-hero"', 1)[1].split('</section>', 1)[0]


def areas(html):
    return html.split('<ul class="areas">', 1)[1].split('</ul>', 1)[0]


def idle(snapshot):
    for row in snapshot["components"]:
        row.update(dict.fromkeys(COUNT_FIELDS, 0), p80_ms=None, p95_ms=None)


def notice(**fields):
    return dict({"id": "n1", "capability": "attendance", "state": "INVESTIGATING", "impact_statement": "Clock-in issue.",
                 "recommended_user_action": "Please wait.", "updated_at": datetime.now(timezone.utc),
                 "incident_ref": "review-1", "next_update_at": None}, **fields)


def test_public_page_separates_measurements_and_notices(page):
    client, _, _ = page
    html = client.get("/").get_data(as_text=True)
    assert "Within expected range" in html
    assert "HTTP 500" in html and "p80" in html and "p95" in html
    assert "The app is responding and its database connection check passed." in html
    assert "Everything is working" not in html and "Platform health" not in html
    # One per component, hall passes included (SPEC-OPS-006 v1.4).
    assert html.count('class="disclosure history-disclosure"') == 7
    assert "No eligible measurements" in html


def test_stale_snapshot_never_displays_old_latency_as_current(page):
    client, _, snapshot = page
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    snapshot["sampled_at"] = snapshot["source_latest_at"] = old
    for item in snapshot["components"]: item["p95_ms"] = 3456
    html = client.get("/").get_data(as_text=True)
    assert "Monitoring out of date" in html
    assert ">Status unknown</span>" in areas(html)
    assert "3456 ms" not in html and "Slower than usual" not in html


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


def test_layout_order_and_simple_cards(page):
    client, store, _ = page
    store.list_active_notices = lambda: [notice()]
    html = client.get("/").get_data(as_text=True)
    assert html.index('class="landing-hero"') < html.index('id="happening-heading"') < html.index('id="working-heading"') < html.index('id="platform-heading"')
    cards = areas(html)
    assert cards.count('>Working</span>') == 5
    assert 'HTTP 500' not in cards and 'p95' not in cards and 'history-disclosure' not in cards
    assert 'Database access' in html and 'Application endpoint' in html
    assert 'local_atm' in html and 'finance_mode' in html
    assert 'mailto:support@classroomtokenhub.com' in html


def test_hero_asks_the_question_and_answers_in_words(page):
    client, _, _ = page
    summary = hero(client.get("/").get_data(as_text=True))
    assert "Is Classroom Token Hub Working?" in summary
    assert "CURRENT STATUS" in summary and "Last checked: just now" in summary
    assert 'state-pill--ok' in summary and "No known issues" in summary


def test_no_notice_means_no_issue_banner(page):
    client, _, _ = page
    html = client.get("/").get_data(as_text=True)
    assert 'id="happening-heading"' not in html


@pytest.mark.parametrize("total,errors,label", [(20, 1, "Checking: errors seen"), (10, 5, "Checking: errors seen"), (1, 1, "Checking: errors seen"), (1, 0, "Working")])
def test_area_labels_have_no_minimum_count(page, total, errors, label):
    client, _, snapshot = page
    row = next(item for item in snapshot['components'] if item['key'] == 'attendance')
    row.update(request_count=total, http_2xx_count=total-errors, http_5xx_count=errors, http_500_count=errors)
    attendance = areas(client.get('/').get_data(as_text=True)).split('<strong>Attendance</strong>', 1)[1].split('</li>', 1)[0]
    assert f'>{label}</span>' in attendance


def test_slow_area_reads_slower_than_usual(page):
    client, _, snapshot = page
    next(item for item in snapshot['components'] if item['key'] == 'payroll').update(p80_ms=1200, p95_ms=1600)
    assert '>Slower than usual</span>' in areas(client.get('/').get_data(as_text=True))


def test_global_unmapped_request_failure_controls_hero(page):
    client, _, snapshot = page
    row = snapshot['components'][0]
    row.update(http_2xx_count=0, http_5xx_count=20, http_500_count=20)
    html = client.get('/').get_data(as_text=True)
    assert 'Detected problems' in hero(html)
    assert areas(html).count('>Working</span>') == 6


def test_human_notice_prevents_reassuring_hero(page):
    client, store, _ = page
    store.list_active_notices = lambda: [notice()]
    html = client.get('/').get_data(as_text=True)
    assert 'Detected problems' in hero(html)
    assert "Attendance: we&#39;re looking into it" in html
    assert "Reference review-1" in html


@pytest.mark.parametrize("state,label", [("AWARE", "Checking reports"), ("INVESTIGATING", "Having problems"),
                                         ("IDENTIFIED", "Having problems"), ("MONITORING", "Having problems")])
def test_notice_outranks_measurement_on_its_area(page, state, label):
    client, store, _ = page
    store.list_active_notices = lambda: [notice(state=state)]
    attendance = areas(client.get('/').get_data(as_text=True)).split('<strong>Attendance</strong>', 1)[1].split('</li>', 1)[0]
    assert f'>{label}</span>' in attendance and '>Working</span>' not in attendance


def test_quiet_period_keeps_availability_and_timestamped_activity(page):
    from copy import deepcopy
    client, store, snapshot = page
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    activity = {"attendance": {"sampled_at": past, "source_latest_at": past,
                              "component": deepcopy(snapshot["components"][2])}}
    store.current_snapshot = lambda: {"snapshot": snapshot, "last_activity": activity}
    idle(snapshot)
    html = client.get('/').get_data(as_text=True)
    assert 'No known issues' in hero(html)
    assert '>Quiet</span>' in areas(html)
    assert 'Last observed: Working' in html
    assert '(five-minute window ending then)' in html
    assert 'area--ok' not in html


@pytest.mark.parametrize('age', [-60, 301])
def test_fresh_request_traffic_cannot_mask_invalid_availability_checks(page, age):
    client, store, _ = page
    store.current_platform = lambda: platform_record(datetime.now(timezone.utc) - timedelta(seconds=age))
    summary = hero(client.get('/').get_data(as_text=True))
    assert 'state-pill--unknown' in summary
    assert 'Last checked: awaiting availability checks' in summary


def test_platform_failure_controls_hero_without_request_traffic(page):
    client, store, snapshot = page
    idle(snapshot)
    store.current_platform = lambda: platform_record(datetime.fromisoformat(snapshot["sampled_at"]), failed=True)
    assert 'Mostly unavailable' in hero(client.get('/').get_data(as_text=True))


def test_closed_gate_reads_maintenance_over_every_other_state(page):
    client, store, snapshot = page
    store.list_active_notices = lambda: [notice()]
    at = datetime.now(timezone.utc)
    store.current_platform = lambda: gated_record(at, gate="GATE_CLOSED", failed=True)
    html = client.get('/').get_data(as_text=True)
    assert 'state-pill--maint' in hero(html) and 'Under maintenance' in hero(html)
    assert 'Classroom Token Hub is closed for maintenance' in html
    # An access restriction is never presented as an application failure.
    assert 'Mostly unavailable' not in hero(html)
    # Requests from behind the gate cannot make an area look usable.
    assert areas(html).count('>Closed for maintenance</span>') == 6
    assert '>Working</span>' not in areas(html)


@pytest.mark.parametrize("gate", ["GATE_OPEN", "UNEXPECTED_DENIAL", "TRANSPORT_UNAVAILABLE"])
def test_gate_that_is_not_closed_never_reads_maintenance(page, gate):
    client, store, _ = page
    at = datetime.now(timezone.utc)
    store.current_platform = lambda: gated_record(at, gate=gate)
    html = client.get('/').get_data(as_text=True)
    assert 'No known issues' in hero(html)
    assert 'Under maintenance' not in html


def test_404_only_does_not_declare_outage_or_successful_activity(page):
    client, _, snapshot = page
    for row in snapshot['components']:
        row.update(request_count=1, http_2xx_count=0, http_4xx_count=1, http_404_count=1)
    html = client.get('/').get_data(as_text=True)
    assert 'No known issues' in hero(html)
    assert areas(html).count('>Nothing to report</span>') == 6
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
    assert '>Status unknown</span>' in areas(html)
    assert 'Last observed: Working' in html
    assert 'area--ok' not in html
    assert 'No known issues' in hero(html)


def test_times_render_in_utc_and_carry_machine_readable_instants(page):
    client, store, _ = page
    due = datetime(2026, 10, 1, 5, 30, tzinfo=timezone.utc)
    store.list_active_notices = lambda: [notice(next_update_at=due)]
    html = client.get('/').get_data(as_text=True)
    # The server's text is UTC, unambiguous without JavaScript; status.js localises it.
    assert '<time datetime="2026-10-01T05:30:00Z" data-local="time"' in html
    assert '>2026-10-01 05:30 UTC</time>' in html


def test_rail_summarises_history_and_recent_incidents_without_their_reports(page):
    client, store, _ = page
    ended = datetime(2026, 9, 30, 22, 40, tzinfo=timezone.utc)
    store.list_resolved_notices = lambda page=1, page_size=20: ([dict(
        id="r1", capability="payroll", state="RESOLVED", updated_at=ended,
        impact_statement="Detailed investigation of the payroll scheduler.")], False)
    html = client.get('/').get_data(as_text=True)
    rail = html.split('<aside class="rail"', 1)[1].split('</aside>', 1)[0]
    assert '<strong>Payroll</strong>' in rail and 'href="/incidents"' in rail
    assert 'Detailed investigation' not in rail
    assert rail.count('class="bar--gap"') == 1
    assert 'too little data to tell' in rail


def test_public_footer_matches_public_site_with_absolute_links(page):
    client, _, _ = page
    html = client.get('/').get_data(as_text=True)
    footer = html.split('<footer class="landing-footer">', 1)[1]
    for href in ("https://classroomtokenhub.com/terms.html", "https://classroomtokenhub.com/privacy.html",
                 "https://classroomtokenhub.com/district.html", "https://classroomtokenhub.com/docs/"):
        assert f'href="{href}"' in footer
    assert 'href="./' not in footer


def test_page_carries_no_inline_script_or_presentational_style(page):
    client, store, _ = page
    store.list_active_notices = lambda: [notice()]
    html = client.get('/').get_data(as_text=True)
    assert '<script>' not in html and ' style="' not in html
    assert not re.search(r'#[0-9a-fA-F]{6}\b', html)
