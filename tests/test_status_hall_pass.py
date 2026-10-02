"""Hall passes have their own public status line (SPEC-OPS-006 v1.4, DOM-OPS-001 v2.12).

On 2026-10-01 a teacher's Approve or Reject, and a student's Cancel, answered
404 "Pending request not found." about half the time, and the status page showed
nothing: hall passes had no component and a 404 never counted as a failure. The
amendment adds a ``hall_pass`` component and one narrow rule: a 404 on
``/api/hall-pass/request/<id>/(approve|reject|cancel)`` is a failed request.
Every other 404, on hall passes or anywhere else, stays a neutral measurement.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import status.measurements as measurements
from status.measurements import COMPONENT_KEYS, classify_component, validate_snapshot
from tests.test_status_measurements import NOW, snapshot as base_snapshot
from tests.test_status_page import areas, hero, page  # noqa: F401 - pytest fixture
from tests.test_status_store import database, sample  # noqa: F401 - pytest fixture

ROOT = Path(__file__).resolve().parents[1]
ROUTES = json.loads((ROOT / "status_service" / "route_groups.json").read_text())

RESOLUTION_PATHS = [
    "/api/hall-pass/request/3f9c2b1e-0d4a-4c55-9e1a-7b2d6c8f0a11/approve",
    "/api/hall-pass/request/3f9c2b1e-0d4a-4c55-9e1a-7b2d6c8f0a11/reject",
    "/api/hall-pass/request/3f9c2b1e-0d4a-4c55-9e1a-7b2d6c8f0a11/cancel",
]
OTHER_HALL_PASS_PATHS = [
    "/api/hall-pass/request",
    "/api/hall-pass/request/abc/unsupported",
    "/api/hall-pass/42/leave",
    "/api/hall-pass/42/return",
    "/api/hall-pass/checkout",
    "/api/hall-pass/checkin",
    "/api/hall-pass/settings",
    "/api/hall-pass/history",
    "/api/hall-pass/setup",
    "/api/hall-pass/verify-token/rotate",
    "/api/hall-pass/available-types",
    "/admin/hall-pass",
    "/verify/hallpass/Zx81token",
]


def failure_routes():
    # Read at call time: absent before the amendment, so the test fails, not errors.
    return getattr(measurements, "NOT_FOUND_FAILURE_ROUTES", {})


def row(data, key):
    return next(item for item in data["components"] if item["key"] == key)


def hall_pass_window(*, ok=0, not_found=0, failed=0, server_errors=0):
    """A fresh snapshot whose hall-pass window holds the given responses.

    ``not_found`` is every 404; ``failed`` is the subset on resolution routes.
    """
    data = base_snapshot()
    item = row(data, "hall_pass")
    total = ok + not_found + server_errors
    item.update(request_count=total, http_2xx_count=ok, http_4xx_count=not_found,
                http_404_count=not_found, http_5xx_count=server_errors,
                http_500_count=server_errors, http_404_failure_count=failed)
    if not total:
        item.update(p80_ms=None, p95_ms=None)
    return data


# ─── The component exists end to end ───

def test_hall_pass_is_a_closed_component_with_a_route_group():
    assert "hall_pass" in COMPONENT_KEYS
    assert set(ROUTES) == set(COMPONENT_KEYS) - {"service"}
    assert getattr(measurements, "SCHEMA_VERSION") == "request-telemetry-v2"


@pytest.mark.parametrize("path", RESOLUTION_PATHS + OTHER_HALL_PASS_PATHS)
def test_every_hall_pass_route_is_in_the_hall_pass_group_only(path):
    """LogQL `=~` is fully anchored, so `re.fullmatch` is the same test."""
    assert re.fullmatch(ROUTES.get("hall_pass", "(?!)"), path)
    # Moving hall passes into their own line changes no other area's numbers.
    for key, expression in ROUTES.items():
        if key != "hall_pass":
            assert not re.fullmatch(expression, path), key


@pytest.mark.parametrize("path", RESOLUTION_PATHS)
def test_resolution_routes_are_the_only_failure_routes(path):
    assert set(failure_routes()) == {"hall_pass"}
    assert re.fullmatch(failure_routes()["hall_pass"], path)


@pytest.mark.parametrize("path", OTHER_HALL_PASS_PATHS + ["/admin/students/bulk-adjust-hall-pass-entitlements"])
def test_other_404s_are_not_failure_routes(path):
    assert failure_routes(), "the failure-route table must exist"
    assert not re.fullmatch(failure_routes()["hall_pass"], path)


def test_sampler_counts_resolution_404s_into_hall_pass_only():
    from status_service.log_sampler import sample as run_sampler
    from tests.test_status_sampler import fake_loki

    queries = []

    def fetch(endpoint, params, *, timeout):
        queries.append(params.get("query", ""))
        if endpoint == "query" and 'status="404"' in params["query"]:
            return {"status": "success", "data": {"resultType": "vector", "result": [
                {"metric": {}, "value": [NOW.timestamp(), "2"]}]}}
        return fake_loki(endpoint, params, timeout=timeout)

    output = run_sampler(now=NOW + timedelta(seconds=17), fetch=fetch)
    hall_pass = row(output, "hall_pass")
    assert hall_pass["collection_state"] == "OK"
    assert hall_pass["http_404_failure_count"] == 2
    assert hall_pass["http_404_count"] == 6
    for item in output["components"]:
        if item["key"] != "hall_pass":
            assert item["http_404_failure_count"] == 0
            assert item["collection_state"] == "OK"
    failure_queries = [query for query in queries if 'status="404"' in query]
    assert len(failure_queries) == 1
    assert "(approve|reject|cancel)" in failure_queries[0]
    # No route, status or other label leaves the host.
    assert "uri" not in json.dumps(output) and "metric" not in json.dumps(output)


def test_sampler_rejects_more_failures_than_404s():
    from status_service.log_sampler import sample as run_sampler
    from tests.test_status_sampler import fake_loki

    def fetch(endpoint, params, *, timeout):
        if endpoint == "query" and 'status="404"' in params["query"]:
            return {"status": "success", "data": {"resultType": "vector", "result": [
                {"metric": {}, "value": [NOW.timestamp(), "7"]}]}}
        return fake_loki(endpoint, params, timeout=timeout)

    output = run_sampler(now=NOW, fetch=fetch)
    assert row(output, "hall_pass")["collection_state"] == "UNAVAILABLE"
    assert row(output, "attendance")["collection_state"] == "OK"


# ─── Classification ───

def failed_request_reason(result):
    return any("Hall-pass requests not found" in reason for reason in result["reasons"])


def test_the_ruling_fixes_three_and_two_percent():
    """Owner ruling 2026-10-02, stated in SPEC-OPS-006 §VI."""
    assert getattr(measurements, "NOT_FOUND_FAILURE_MIN_COUNT", None) == 3
    assert getattr(measurements, "NOT_FOUND_FAILURE_RATE_PERCENT", None) == 2


def test_resolution_404s_degrade_hall_passes():
    data = validate_snapshot(hall_pass_window(ok=7, not_found=3, failed=3))
    result = classify_component(row(data, "hall_pass"), data, now=NOW)
    assert result["state"] == "ELEVATED_ERRORS"
    assert result["http_404_failure_percent"] == 30
    assert failed_request_reason(result)


@pytest.mark.parametrize("ok,failed,signals", [
    (98, 2, False),   # two, even at 2%+: below the minimum (double click, stale tab)
    (8, 2, False),    # two at 20%: still below the minimum
    (97, 3, True),    # three at 3%: both conditions hold
    (147, 3, False),  # three at exactly 2%: not above it
    (197, 3, False),  # three at 1.5% (busy window): below the rate
    (146, 3, True),   # three at 2.03%: just above it
])
def test_failed_requests_need_a_minimum_and_a_rate(ok, failed, signals):
    data = validate_snapshot(hall_pass_window(ok=ok, not_found=failed, failed=failed))
    result = classify_component(row(data, "hall_pass"), data, now=NOW)
    assert failed_request_reason(result) is signals


def test_other_hall_pass_404s_stay_neutral():
    # 2 of 50 (4%): under the generic 404 threshold, and none on a resolution route.
    data = validate_snapshot(hall_pass_window(ok=48, not_found=2, failed=0))
    result = classify_component(row(data, "hall_pass"), data, now=NOW)
    assert result["state"] == "NORMAL"
    assert result["http_404_failure_percent"] == 0


def test_server_errors_degrade_hall_passes():
    data = validate_snapshot(hall_pass_window(ok=10, server_errors=1))
    result = classify_component(row(data, "hall_pass"), data, now=NOW)
    assert result["state"] == "ELEVATED_ERRORS"
    assert any("server-error" in reason for reason in result["reasons"])


def test_other_components_keep_their_rules():
    data = validate_snapshot(hall_pass_window(ok=8, not_found=2, failed=2))
    for key in COMPONENT_KEYS:
        if key != "hall_pass":
            result = classify_component(row(data, key), data, now=NOW)
            assert result["state"] == "NORMAL"
            assert result["http_404_failure_percent"] is None


# ─── Schema ───

def test_schema_accepts_hall_pass_and_rejects_unknown_or_missing_keys():
    validate_snapshot(base_snapshot())
    renamed = base_snapshot()
    row(renamed, "hall_pass")["key"] = "hall_passes"
    with pytest.raises(ValueError):
        validate_snapshot(renamed)
    missing = base_snapshot()
    missing["components"] = [item for item in missing["components"] if item["key"] != "hall_pass"]
    with pytest.raises(ValueError):
        validate_snapshot(missing)
    extra = base_snapshot()
    extra["components"].append(dict(deepcopy(row(extra, "login")), key="hall_pass_queue"))
    with pytest.raises(ValueError):
        validate_snapshot(extra)


@pytest.mark.parametrize("change", [
    # More failed requests than 404s.
    lambda data: row(data, "hall_pass").update(http_404_failure_count=1),
    # Only a designated component can carry failed-request 404s.
    lambda data: row(data, "attendance").update(http_4xx_count=1, http_404_count=1, http_2xx_count=99,
                                                http_404_failure_count=1),
    lambda data: row(data, "hall_pass").update(http_404_failure_count=True),
    lambda data: row(data, "hall_pass").update(http_404_failure_count=-1),
    lambda data: row(data, "hall_pass").pop("http_404_failure_count"),
    # An unavailable window carries no number.
    lambda data: row(data, "hall_pass").update(collection_state="UNAVAILABLE"),
])
def test_schema_rejects_malformed_failure_counts(change):
    data = base_snapshot()
    change(data)
    with pytest.raises(ValueError):
        validate_snapshot(data)


def legacy_snapshot():
    data = base_snapshot()
    data["schema_version"] = "request-telemetry-v1"
    data["components"] = [{k: v for k, v in item.items() if k != "http_404_failure_count"}
                          for item in data["components"] if item["key"] != "hall_pass"]
    return data


def test_snapshots_written_before_the_amendment_stay_readable():
    data = validate_snapshot(legacy_snapshot())
    assert all(classify_component(item, data, now=NOW)["state"] == "NORMAL" for item in data["components"])


@pytest.mark.parametrize("change", [
    lambda data: data["components"].append(dict(deepcopy(data["components"][0]), key="hall_pass")),
    lambda data: data["components"][0].update(http_404_failure_count=0),
])
def test_legacy_schema_cannot_carry_hall_pass_evidence(change):
    data = legacy_snapshot()
    change(data)
    with pytest.raises(ValueError):
        validate_snapshot(data)


# ─── The public page ───

def hall_pass_card(html):
    return areas(html).split("<strong>Hall passes</strong>", 1)[1].split("</li>", 1)[0]


def set_hall_pass(snapshot, **counts):
    item = row(snapshot, "hall_pass")
    ok = counts.get("ok", 0)
    not_found = counts.get("not_found", 0)
    errors = counts.get("server_errors", 0)
    item.update(request_count=ok + not_found + errors, http_2xx_count=ok, http_4xx_count=not_found,
                http_404_count=not_found, http_404_failure_count=counts.get("failed", 0),
                http_5xx_count=errors, http_500_count=errors)


def test_public_page_shows_a_hall_passes_line(page):  # noqa: F811
    client, _, _ = page
    html = client.get("/").get_data(as_text=True)
    card = hall_pass_card(html)
    assert ">Working</span>" in card
    assert "Asking for, approving and checking hall passes" in card
    assert "<h3>Hall pass requests</h3>" in html


def test_resolution_404s_read_errors_seen_on_the_hall_pass_line_only(page):  # noqa: F811
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=17, not_found=3, failed=3)
    html = client.get("/").get_data(as_text=True)
    assert ">Checking: errors seen</span>" in hall_pass_card(html)
    assert areas(html).count(">Checking: errors seen</span>") == 1
    assert "Requests not found" in html


@pytest.mark.parametrize("ok,failed", [(19, 1), (18, 2), (197, 3)])
def test_stray_or_diluted_resolution_404s_read_working(page, ok, failed):  # noqa: F811
    """One or two (a double click, a stale tab), or three in a busy window, stay quiet."""
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=ok, not_found=failed, failed=failed)
    html = client.get("/").get_data(as_text=True)
    assert ">Working</span>" in hall_pass_card(html)
    assert "No known issues" in hero(html)


def test_other_hall_pass_404_reads_working(page):  # noqa: F811
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=19, not_found=1, failed=0)
    html = client.get("/").get_data(as_text=True)
    assert ">Working</span>" in hall_pass_card(html)
    assert "Checking: errors seen" not in areas(html)


def test_server_error_reads_errors_seen_on_the_hall_pass_line(page):  # noqa: F811
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=19, server_errors=1)
    html = client.get("/").get_data(as_text=True)
    assert ">Checking: errors seen</span>" in hall_pass_card(html)


@pytest.mark.parametrize("ok,not_found,failed,headline", [
    (97, 3, 3, "Detected problems"),   # the rule trips
    (98, 2, 2, "No known issues"),     # below the minimum
    (197, 3, 3, "No known issues"),    # below the rate
    (0, 20, 0, "No known issues"),     # neutral 404s, however many
])
def test_headline_follows_the_same_rule(page, ok, not_found, failed, headline):  # noqa: F811
    """Owner ruling 2026-10-02: the card's rule, and only it, also qualifies the headline."""
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=ok, not_found=not_found, failed=failed)
    summary = hero(client.get("/").get_data(as_text=True))
    assert headline in summary
    if headline == "Detected problems":
        assert "state-pill--problems" in summary


def test_snapshot_from_before_the_amendment_shows_hall_passes_as_unknown(page):  # noqa: F811
    client, store, snapshot = page
    legacy = legacy_snapshot()
    legacy["sampled_at"] = snapshot["sampled_at"]
    legacy["source_latest_at"] = snapshot["source_latest_at"]
    store.current_snapshot = lambda: {"snapshot": legacy, "received_at": None, "diagnostic": None}
    html = client.get("/").get_data(as_text=True)
    assert ">Status unknown</span>" in hall_pass_card(html)
    assert areas(html).count(">Working</span>") == 5


def test_incident_shape_2026_10_01(page):  # noqa: F811
    """One class period on two workers: half of approve/reject/cancel answered 404.

    Window: the student's page loads pass types (4), students ask (3), the
    teacher approves or rejects four and a student cancels once (5 resolutions,
    2 found on the other worker, 3 not): 3 failed of 12, 25%. Before the
    amendment hall passes had no line, the 5xx-only card rule would have read
    this window as `Working`, and the headline said `No known issues`.
    """
    client, _, snapshot = page
    set_hall_pass(snapshot, ok=4 + 3 + 2, not_found=3, failed=3)
    html = client.get("/").get_data(as_text=True)
    assert ">Checking: errors seen</span>" in hall_pass_card(html)
    assert "Detected problems" in hero(html)
    item = row(snapshot, "hall_pass")
    result = classify_component(item, validate_snapshot(snapshot), now=datetime.now(timezone.utc))
    assert result["state"] == "ELEVATED_ERRORS"
    assert any("Hall-pass requests not found" in reason for reason in result["reasons"])


def test_operator_drafts_a_not_found_detection():
    from status_service.presentation import detections
    item = {"key": "hall_pass", "collection_state": "OK", "http_5xx_count": 0, "request_count": 10,
            "http_404_failure_count": 3, "http_404_failure_percent": 30.0}
    found = detections([item], [])
    assert [(entry["key"], entry["kind"]) for entry in found] == [("hall_pass", "not_found")]
    assert detections([item], [{"capability": "hall_pass"}]) == []
    # Below the minimum is not offered either.
    assert detections([dict(item, http_404_failure_count=2)], []) == []


# ─── Persistence ───

def test_store_rolls_up_hall_passes_and_keeps_legacy_activity(database):  # noqa: F811
    store, data = database
    legacy = sample(count=1)
    legacy["schema_version"] = "request-telemetry-v1"
    legacy["components"] = [{k: v for k, v in item.items() if k != "http_404_failure_count"}
                            for item in legacy["components"] if item["key"] != "hall_pass"]
    start = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
    store.append_snapshot(legacy, start)
    assert "attendance" in store.current_snapshot()["last_activity"]
    later = start + timedelta(minutes=5)
    upgraded = sample(later, count=0)
    store.append_snapshot(upgraded, later)
    # Quiet first v2 window: the activity retained from the v1 window survives.
    assert "attendance" in store.current_snapshot()["last_activity"]
    burst = sample(later + timedelta(minutes=1), count=2)
    row(burst, "hall_pass").update(http_2xx_count=1, http_4xx_count=1, http_404_count=1,
                                   http_404_failure_count=1)
    store.append_snapshot(burst, later + timedelta(minutes=1))
    day = data["telemetry_days"]["2026-09-21"]["components"]["hall_pass"]
    assert day["elevated_errors"] == 1 and day["sampled"] == 2
    retained = store.current_snapshot()["last_activity"]["hall_pass"]["component"]
    assert retained["http_404_failure_count"] == 1


# ─── Structural guard: every hall-pass route is measured (SOP-TEST-003 §IX.A) ───

_BLUEPRINT = re.compile(r"^(\w+)\s*=\s*Blueprint\(([^)]*)\)", re.M)
_ROUTE = re.compile(r"@(\w+)\.route\(\s*['\"]([^'\"]+)['\"]")
_CONVERTER = re.compile(r"<(?:(\w+):)?\w+>")


def unmeasured_hall_pass_routes(sources: dict[str, str], expression: str) -> list[str]:
    """Hall-pass routes in route-module source that the hall-pass group would miss.

    A hall-pass route has a whole path segment ``hall-pass`` or ``hallpass``.
    Converters become a sample value of their type before matching.
    """
    missed = []
    for text in sources.values():
        prefixes = {}
        for name, arguments in _BLUEPRINT.findall(text):
            prefix = re.search(r"url_prefix\s*=\s*['\"]([^'\"]*)['\"]", arguments)
            prefixes[name] = prefix.group(1) if prefix else ""
        for blueprint, rule in _ROUTE.findall(text):
            path = prefixes.get(blueprint, "") + rule
            if not {"hall-pass", "hallpass"} & set(path.split("/")):
                continue
            concrete = _CONVERTER.sub(lambda m: "7" if m.group(1) == "int" else "sample", path)
            if not re.fullmatch(expression, concrete):
                missed.append(path)
    return missed


def route_sources():
    return {str(path): path.read_text() for path in sorted((ROOT / "app" / "routes").glob("*.py"))}


def test_every_registered_hall_pass_route_is_in_the_hall_pass_group():
    sources = route_sources()
    assert any("/hall-pass/request" in text for text in sources.values())
    assert unmeasured_hall_pass_routes(sources, ROUTES.get("hall_pass", "(?!)")) == []


def test_guard_reports_a_new_hall_pass_route_it_does_not_measure():
    """Mutation proof: a near-miss route a future change would really add."""
    synthetic = {"api.py": (
        "api_bp = Blueprint('api', __name__, url_prefix='/api')\n"
        "@api_bp.route('/hall-pass/request/<request_id>/approve', methods=['POST'])\n"
        "def ok(): pass\n"
        "@api_bp.route('/hall-pass/queue', methods=['GET'])\n"
        "def missed(): pass\n"
        "@api_bp.route('/hall-pass-stats', methods=['GET'])\n"
        "def not_a_hall_pass_family_route(): pass\n")}
    assert unmeasured_hall_pass_routes(synthetic, ROUTES["hall_pass"]) == ["/api/hall-pass/queue"]
    admin = {"admin.py": "admin_bp = Blueprint('admin', __name__, url_prefix='/admin')\n"
                         "@admin_bp.route('/hall-pass/export')\ndef missed(): pass\n"}
    assert unmeasured_hall_pass_routes(admin, ROUTES["hall_pass"]) == ["/admin/hall-pass/export"]
