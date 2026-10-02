"""Selection-bound, atomic external notice resolution."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import re
import sys
from types import SimpleNamespace

import pytest
from status_service.store import FirestoreNoticeStore


@pytest.fixture
def setup(monkeypatch):
    data = {"external_status_notices": {}, "external_status_notice_events": {}}

    class Ref:
        def __init__(self, collection, key):
            self.collection, self.key = collection, key

        def get(self, transaction=None):
            assert not transaction.writes, "All reads must precede writes"
            value = deepcopy(data[self.collection].get(self.key))
            return SimpleNamespace(exists=value is not None, to_dict=lambda: value)

    class Transaction:
        def __init__(self):
            self.writes = []

        def create(self, ref, value):
            assert ref.key not in data[ref.collection]
            self.writes.append((ref, value))

        def set(self, ref, value):
            self.writes.append((ref, value))

    def transactional(function):
        def run(transaction):
            function(transaction)
            for ref, value in transaction.writes:
                data[ref.collection][ref.key] = value
        return run

    class Collection:
        def __init__(self, name, filters=()):
            self.name, self.filters = name, filters
            self.orders, self.skip, self.maximum = [], 0, None

        def document(self, key):
            return Ref(self.name, key)

        def where(self, field, operator, value):
            assert operator == "=="
            return Collection(self.name, (*self.filters, (field, value)))

        def order_by(self, field, direction):
            self.orders.append((field, direction))
            return self

        def offset(self, count):
            self.skip = count
            return self

        def limit(self, count):
            self.maximum = count
            return self

        def stream(self):
            rows = [(key, value) for key, value in data[self.name].items()
                    if all(value.get(field) == expected for field, expected in self.filters)]
            for field, direction in reversed(self.orders):
                rows.sort(key=lambda row: row[0] if field == "__name__" else row[1][field],
                          reverse=direction == "DESCENDING")
            rows = rows[self.skip:]
            if self.maximum is not None:
                rows = rows[:self.maximum]
            if self.name == "external_status_notices" and ("state", "RESOLVED") in self.filters:
                assert self.maximum is not None and self.maximum <= 21, "History query must be bounded at the store boundary"
                store.history_reads.append(len(rows))
            return [SimpleNamespace(id=key, to_dict=lambda value=deepcopy(value): value)
                    for key, value in rows]

    client = SimpleNamespace(transaction=Transaction, collection=Collection)
    firestore = SimpleNamespace(transactional=transactional, Client=lambda **kwargs: client)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", firestore)
    monkeypatch.setitem(sys.modules, "google.cloud", SimpleNamespace(firestore=firestore))
    store = FirestoreNoticeStore(client)
    store.history_reads = []
    for key in ("one", "two", "three"):
        data["external_status_notices"][key] = dict(
            external_notice_id=key, incident_ref="incident-" + key, last_event_id="event-" + key,
            state="INVESTIGATING", capability="login", impact_statement="Issue " + key,
            recommended_user_action="Wait.", source_observation_ids=["observation-" + key],
            updated_at=datetime.now(timezone.utc))
    store.list_notices = lambda: [dict(id=k, **deepcopy(v)) for k, v in data["external_status_notices"].items()]
    store.list_active_notices = lambda: [n for n in store.list_notices() if n["state"] != "RESOLVED"]
    store.current_platform = lambda: None
    store.current_snapshot = lambda: None
    store.measurement_history = lambda: []
    monkeypatch.setenv("STATUS_SERVICE_MODE", "operator")
    monkeypatch.setenv("STATUS_SESSION_SECRET", "test-only")
    monkeypatch.setitem(sys.modules, "status_service.identity", SimpleNamespace(
        authenticated_operator_email=lambda *args: "operator@example.com"))
    module = importlib.import_module("status_service.app")
    monkeypatch.setattr(module, "authenticated_operator_email", lambda *args: "operator@example.com")
    app = module.create_app(store=store)
    return data, store, app.test_client(), module


def form(client):
    page = client.get("/operator/notices?action=resolve").get_data(as_text=True)
    with client.session_transaction() as session:
        csrf = session["csrf_token"]
    return csrf, re.findall(r'name="selected_issue" value="([^"]+)"', page), page


def test_selected_issues_resolve_without_clearing_others(setup):
    data, store, client, _ = setup
    original_event = {"state": "INVESTIGATING", "impact_statement": "Original report"}
    data["external_status_notice_events"]["original"] = deepcopy(original_event)
    csrf, tokens, page = form(client)
    assert "Resolve selected issues" in page
    assert "<option>RESOLVED</option>" not in page
    response = client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens[:2], "resolution_message": "Recovered."})
    assert response.status_code == 302
    assert [n["id"] for n in store.list_active_notices()] == ["three"]
    assert data["external_status_notice_events"]["original"] == original_event
    events = [v for k, v in data["external_status_notice_events"].items() if k != "original"]
    assert {e["incident_ref"] for e in events} == {"incident-one", "incident-two"}
    assert {e["external_notice_id"] for e in events} == {"one", "two"}
    assert all(e["state"] == "RESOLVED" and e["actor"] == "operator@example.com" for e in events)
    assert data["external_status_notices"]["three"]["last_event_id"] == "event-three"
    assert client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens[:2], "resolution_message": "Again"}).status_code == 409
    assert len(data["external_status_notice_events"]) == 3


@pytest.mark.parametrize("change", ["updated", "resolved", "missing", "unlinked"])
def test_stale_or_invalid_selection_is_atomic(setup, change):
    data, _, client, _ = setup
    csrf, tokens, _ = form(client)
    notice = data["external_status_notices"]["two"]
    if change == "updated": notice["last_event_id"] = "new-event"
    if change == "resolved": notice["state"] = "RESOLVED"
    if change == "missing": del data["external_status_notices"]["two"]
    if change == "unlinked": del notice["incident_ref"]
    before = deepcopy(data)
    assert client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens[:2], "resolution_message": "Recovered"}).status_code == 409
    assert data == before


@pytest.mark.parametrize("case", ["empty", "tampered", "duplicate", "blank-message", "csrf", "unauthenticated", "manual"])
def test_rejected_requests_do_not_write(setup, case, monkeypatch):
    data, _, client, module = setup
    csrf, tokens, _ = form(client)
    body = dict(csrf_token=csrf, selected_issue=[tokens[0]], resolution_message="Recovered")
    expected = 400
    path = "/operator/notices/resolve"
    if case == "empty": body["selected_issue"] = []
    if case == "tampered": body["selected_issue"] = ["invalid"]
    if case == "duplicate": body["selected_issue"] *= 2
    if case == "blank-message": body["resolution_message"] = " "
    if case == "csrf": body["csrf_token"] = "bad"; expected = 403
    if case == "unauthenticated":
        monkeypatch.setattr(module, "authenticated_operator_email", lambda *args: None)
        expected = 401
    if case == "manual": path = "/operator/notices"; body["state"] = "RESOLVED"
    before = deepcopy(data)
    assert client.post(path, data=body).status_code == expected
    assert data == before


def test_public_mode_cannot_resolve(setup):
    _, _, client, _ = setup
    client.application.config["STATUS_SERVICE_MODE"] = "public"
    assert client.post("/operator/notices/resolve").status_code == 404


def test_resolving_all_removes_notice_warning_but_does_not_invent_health(setup):
    _, _, client, _ = setup
    csrf, tokens, _ = form(client)
    assert client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens, "resolution_message": "Recovered"}).status_code == 302
    client.application.config["STATUS_SERVICE_MODE"] = "public"
    page = client.get("/").get_data(as_text=True)
    assert "Detected problems" not in page
    assert "Monitoring unavailable" in page


def test_operator_investigation_can_resolve_without_automated_sources(setup):
    data, _, client, _ = setup
    for notice in data["external_status_notices"].values():
        notice["source_observation_ids"] = []
    csrf, tokens, _ = form(client)
    assert len(tokens) == 3
    assert client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens, "resolution_message": "Investigation confirmed recovery."}).status_code == 302


def test_publish_investigated_notice_without_automated_source(setup):
    _, store, client, _ = setup
    csrf, _, _ = form(client)
    published = []
    store.append_event = lambda notice, *args: published.append(notice)
    response = client.post("/operator/notices", data={
        "csrf_token": csrf, "incident_ref": "investigation-123", "capability": "attendance",
        "state": "INVESTIGATING", "impact_statement": "We reproduced a clock-in failure.",
        "recommended_user_action": "Please wait for an update.", "recovery_state": "ESTIMATED",
        "recovery_expectation": "2026-09-22T12:00", "next_update_at": "2026-09-22T11:00"})
    assert response.status_code == 302
    assert published[0]["source_observation_ids"] == ()
    assert published[0]["recovery_expectation"] == datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
    assert published[0]["next_update_at"] == datetime(2026, 9, 22, 11, tzinfo=timezone.utc)


@pytest.mark.parametrize("fields", [
    {"recovery_state": "ESTIMATED"},
    {"recovery_state": "UNAVAILABLE", "recovery_expectation": "2026-09-22T12:00"},
    {"next_update_at": "not-a-time"},
    {"state": "arbitrary"},
    {"capability": "unregistered"},
    {"impact_statement": "x" * 501},
])
def test_invalid_notice_fields_do_not_write(setup, fields):
    _, store, client, _ = setup
    csrf, _, _ = form(client)
    published = []
    store.append_event = lambda notice, *args: published.append(notice)
    payload = dict(csrf_token=csrf, incident_ref="investigation-123", capability="attendance",
                   state="INVESTIGATING", impact_statement="Investigating.", recommended_user_action="Wait.",
                   recovery_state="UNAVAILABLE", next_update_unavailable="on")
    payload.update(fields)
    if "next_update_at" in fields: payload.pop("next_update_unavailable")
    response = client.post("/operator/notices", data=payload)
    assert response.status_code == 400
    if fields.get("recovery_state") == "UNAVAILABLE":
        assert "Clear the recovery time or select a known or estimated recovery state." in response.get_data(as_text=True)
    assert not published


@pytest.mark.parametrize("length", [501, 12000])
def test_detailed_resolution_saved_and_visible_in_history(setup, length):
    data, _, client, _ = setup
    csrf, tokens, page = form(client)
    textarea = re.search(r'<textarea[^>]*name="resolution_message"[^>]*>', page).group()
    assert "maxlength" not in textarea and "required" in textarea
    now = datetime.now(timezone.utc)
    data["external_status_notice_events"]["original"] = dict(
        external_notice_id="one", event_id="original", published_at=now,
        state="INVESTIGATING", impact_statement="Original incident report",
        recommended_user_action="Please wait.", actor="PRIVATE-OPERATOR@example.com")
    message = "Detailed investigation: " + "x" * length + "\n\nRecovery verified. <script>alert(1)</script>"
    response = client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens[:1], "resolution_message": message})
    assert response.status_code == 302
    assert data["external_status_notices"]["one"]["impact_statement"] == message
    events = list(data["external_status_notice_events"].values())
    assert events[-1]["impact_statement"] == message
    before = deepcopy(data)
    client.application.config["STATUS_SERVICE_MODE"] = "public"
    current = client.get("/").get_data(as_text=True)
    assert 'href="/incidents"' in current
    assert "Detailed investigation" not in current
    history = client.get("/incidents").get_data(as_text=True)
    assert "Original incident report" in history and "x" * length in history
    assert "&lt;script&gt;" in history and "<script>" not in history
    assert "PRIVATE-OPERATOR" not in history and "operator@example.com" not in history
    # The story reads in order: the original update comes before the resolution.
    assert history.index("Original incident report") < history.index("Marked resolved.")
    assert history.count("<h1>") == 1
    assert data == before


def test_history_pagination_includes_older_resolutions_and_excludes_open_issues(setup):
    data, store, client, _ = setup
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    for i in range(55):
        data["external_status_notices"][f"resolved-{i}"] = dict(
            state="RESOLVED", capability="login", incident_ref=f"past-{i}",
            updated_at=now - timedelta(days=i), impact_statement=f"Report {i}.")
    client.application.config["STATUS_SERVICE_MODE"] = "public"
    first = client.get("/incidents").get_data(as_text=True)
    assert "Report 0." in first and "Report 20." not in first
    assert "Issue one" not in first and "Older incidents" in first
    last = client.get("/incidents?page=3").get_data(as_text=True)
    assert "Report 54." in last and "Newer incidents" in last
    assert "Older incidents" not in last
    assert store.history_reads == [21, 15]
    assert client.get("/incidents?page=4").status_code == 404
    for page in ("0", "-1", "abc"):
        assert client.get("/incidents?page=" + page).status_code == 400


def test_history_empty_state_and_operator_authentication(setup, monkeypatch):
    _, _, client, module = setup
    assert 'href="/incidents"' in form(client)[2]
    assert "No resolved incidents" in client.get("/incidents").get_data(as_text=True)
    monkeypatch.setattr(module, "authenticated_operator_email", lambda *args: None)
    assert client.get("/incidents").status_code == 401
    client.application.config["STATUS_SERVICE_MODE"] = "public"
    assert client.get("/incidents").status_code == 200


@pytest.mark.parametrize("report,selections", [("é" * 450001, 1), ("x" * 50000, 100)],
                         ids=["document-utf8-budget", "transaction-batch-budget"])
def test_storage_budget_rejects_before_writes_and_preserves_report(setup, report, selections):
    from status_service.store import ResolutionTooLarge
    data, store, client, _ = setup
    before = deepcopy(data)
    with pytest.raises(ResolutionTooLarge):
        store.resolve_notices({str(i): "version" for i in range(selections)}, report, "operator")
    assert data == before
    if selections == 100:
        from itsdangerous import URLSafeSerializer
        signer = URLSafeSerializer(client.application.secret_key, salt="notice-resolution")
        csrf, _, _ = form(client)
        response = client.post("/operator/notices/resolve", data={
            "csrf_token": csrf, "selected_issue": [signer.dumps([str(i), "version"]) for i in range(selections)],
            "resolution_message": report})
        assert response.status_code == 413
        assert report in response.get_data(as_text=True)
        assert "No issues were resolved" in response.get_data(as_text=True)
        assert data == before


# ─── AWARE stage and the one-issue-at-a-time console (SPEC-OPS-002 §5.2) ───

def test_aware_notice_is_active_and_resolvable(setup):
    data, store, client, _ = setup
    data["external_status_notices"]["two"]["state"] = "AWARE"
    from status_service.store import FirestoreNoticeStore
    active = {n["id"]: n["state"] for n in FirestoreNoticeStore.list_active_notices(store)}
    assert active["two"] == "AWARE"
    csrf, tokens, page = form(client)
    assert len(tokens) == 3
    assert client.post("/operator/notices/resolve", data={
        "csrf_token": csrf, "selected_issue": tokens[1:2], "resolution_message": "It was nothing."}).status_code == 302
    assert data["external_status_notices"]["two"]["state"] == "RESOLVED"


def publish(client, store, **fields):
    csrf, _, _ = form(client)
    published = []
    store.append_event = lambda notice, *args: published.append(notice)
    body = dict(csrf_token=csrf, incident_ref="ops-1", capability="payroll", state="AWARE",
                impact_statement="Some payroll runs may be failing.", recommended_user_action="Wait.",
                recovery_state="UNAVAILABLE", next_update_choice="none")
    body.update(fields)
    return client.post("/operator/notices", data=body), published


def test_operator_can_publish_an_aware_notice(setup):
    _, store, client, _ = setup
    response, published = publish(client, store)
    assert response.status_code == 302 and "ref=ops-1" in response.headers["Location"]
    assert published[0]["state"] == "AWARE" and published[0]["next_update_unavailable"] is True


def test_quick_next_update_is_relative_to_publish_time(setup):
    _, store, client, _ = setup
    before = datetime.now(timezone.utc)
    _, published = publish(client, store, next_update_choice="60")
    due = published[0]["next_update_at"]
    assert before + timedelta(minutes=60) <= due <= datetime.now(timezone.utc) + timedelta(minutes=60)
    assert published[0]["next_update_unavailable"] is False


def test_local_times_are_stored_in_utc_using_the_reported_offset(setup):
    _, store, client, _ = setup
    _, published = publish(client, store, next_update_choice="custom", next_update_at="2026-09-30T22:30",
                           tz_offset_minutes="-420", recovery_state="ESTIMATED",
                           recovery_expectation="2026-09-30T23:00")
    assert published[0]["next_update_at"] == datetime(2026, 10, 1, 5, 30, tzinfo=timezone.utc)
    assert published[0]["recovery_expectation"] == datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("offset", ["", "abc", "9999"])
def test_missing_or_implausible_offset_means_utc(setup, offset):
    _, store, client, _ = setup
    _, published = publish(client, store, next_update_choice="custom", next_update_at="2026-09-30T22:30",
                           tz_offset_minutes=offset)
    assert published[0]["next_update_at"] == datetime(2026, 9, 30, 22, 30, tzinfo=timezone.utc)


def test_selected_issue_carries_its_identity_so_updates_need_no_retyping(setup):
    _, _, client, _ = setup
    page = client.get("/operator/notices?issue=two").get_data(as_text=True)
    assert '<input type="hidden" name="external_notice_id" value="two">' in page
    assert '<input type="hidden" name="incident_ref" value="incident-two">' in page
    assert 'aria-current="page">Post update' in page and "Publish update" in page
    assert '<option>RESOLVED</option>' not in page and 'value="RESOLVED"' not in page


def test_new_issue_suggests_a_reference_and_starts_at_aware(setup):
    _, _, client, _ = setup
    page = client.get("/operator/notices?issue=new").get_data(as_text=True)
    assert re.search(r'name="incident_ref" type="text" maxlength="160" required value="ops-\d{4}-\d{2}-\d{2}-001"', page)
    assert re.search(r'name="state" value="AWARE" required\s+checked', page)
    assert 'name="external_notice_id"' not in page


def test_detection_offers_an_aware_draft_but_publishes_nothing(setup):
    data, store, client, _ = setup
    from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION
    now = datetime.now(timezone.utc)
    snapshot = {"schema_version": SCHEMA_VERSION, "sampled_at": now.isoformat(), "source_latest_at": now.isoformat(),
                "window_seconds": 300, "components": [
                    {"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0), "request_count": 10,
                     "http_2xx_count": 9 if key == "payroll" else 10, "http_5xx_count": 1 if key == "payroll" else 0,
                     "http_500_count": 1 if key == "payroll" else 0, "p80_ms": 100, "p95_ms": 200}
                    for key in COMPONENT_KEYS]}
    store.current_snapshot = lambda: {"snapshot": snapshot}
    before = deepcopy(data)
    page = client.get("/operator/notices").get_data(as_text=True)
    assert "Detected automatically · 1" in page and "issue=auto-payroll" in page
    draft = client.get("/operator/notices?issue=auto-payroll").get_data(as_text=True)
    assert "Draft from automatic detection" in draft
    assert re.search(r'name="capability" value="payroll" required\s+checked', draft)
    assert f'value="telemetry:{snapshot["sampled_at"]}"' in draft
    assert data == before


def test_hall_pass_not_found_detection_offers_a_draft(setup):
    """SPEC-OPS-006 v1.4: a failed-request 404 is offered like a 5xx, worded as not found."""
    data, store, client, _ = setup
    from status.measurements import COMPONENT_KEYS, COUNT_FIELDS, SCHEMA_VERSION
    now = datetime.now(timezone.utc)
    hall_pass = {"http_2xx_count": 8, "http_4xx_count": 2, "http_404_count": 2, "http_404_failure_count": 2}
    snapshot = {"schema_version": SCHEMA_VERSION, "sampled_at": now.isoformat(), "source_latest_at": now.isoformat(),
                "window_seconds": 300, "components": [
                    {"key": key, "collection_state": "OK", **dict.fromkeys(COUNT_FIELDS, 0), "request_count": 10,
                     "http_2xx_count": 10, "p80_ms": 100, "p95_ms": 200, **(hall_pass if key == "hall_pass" else {})}
                    for key in COMPONENT_KEYS]}
    store.current_snapshot = lambda: {"snapshot": snapshot}
    before = deepcopy(data)
    page = client.get("/operator/notices").get_data(as_text=True)
    assert "Detected automatically · 1" in page and "issue=auto-hall_pass" in page
    assert "Requests not found on Hall passes" in page and "Not found 20.0%" in page
    assert "Server errors on Hall passes" not in page
    draft = client.get("/operator/notices?issue=auto-hall_pass").get_data(as_text=True)
    assert re.search(r'name="capability" value="hall_pass" required\s+checked', draft)
    assert data == before
