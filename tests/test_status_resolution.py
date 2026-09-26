"""Selection-bound, atomic external notice resolution."""

from copy import deepcopy
from datetime import datetime, timezone
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

    client = SimpleNamespace(transaction=Transaction, collection=lambda name:
                             SimpleNamespace(document=lambda key: Ref(name, key)))
    firestore = SimpleNamespace(transactional=transactional, Client=lambda **kwargs: client)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", firestore)
    monkeypatch.setitem(sys.modules, "google.cloud", SimpleNamespace(firestore=firestore))
    store = FirestoreNoticeStore(client)
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
    page = client.get("/operator/notices").get_data(as_text=True)
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


@pytest.mark.parametrize("case", ["empty", "tampered", "duplicate", "blank-message", "long-message", "csrf", "unauthenticated", "manual"])
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
    if case == "long-message": body["resolution_message"] = "x" * 501
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
    assert "DETECTED PROBLEMS" not in page
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
