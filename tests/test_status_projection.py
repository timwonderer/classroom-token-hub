from datetime import datetime, timedelta, timezone
import importlib
import sys
import types

import pytest

from status.projection import (
    EpistemicState, EvidenceSource, Observation, ObservationClass, Outcome, PublicState,
    aggregate_correctness,
)
from status.projection import derive_capability_cards, derive_platform_checks


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def observation(outcome, epistemic=EpistemicState.KNOWN, age=timedelta(minutes=1)):
    return Observation(
        source=EvidenceSource.INVARIANT_VERIFIER, capability="ledger_correctness",
        observation_class=ObservationClass.CORRECTNESS,
        outcome=outcome,
        epistemic_state=epistemic,
        observed_at=NOW - age,
        freshness_class="PERIODIC_CORRECTNESS",
    )


def test_raw_observation_matrix_rejects_invalid_combinations():
    with pytest.raises(ValueError):
        observation(Outcome.PASS, EpistemicState.UNAVAILABLE).validate()
    with pytest.raises(ValueError):
        observation(Outcome.UNKNOWN, EpistemicState.KNOWN).validate()


def test_correctness_aggregation_is_fail_closed_for_missing_stale_or_unknown():
    assert aggregate_correctness((), now=NOW) == PublicState.UNKNOWN
    assert aggregate_correctness((observation(Outcome.UNKNOWN, EpistemicState.UNAVAILABLE),), now=NOW) == PublicState.UNKNOWN
    assert aggregate_correctness((observation(Outcome.PASS, age=timedelta(minutes=31)),), now=NOW) == PublicState.UNKNOWN


def test_correctness_aggregation_maps_pass_and_failure():
    assert aggregate_correctness((observation(Outcome.PASS),), now=NOW) == PublicState.AVAILABLE
    assert aggregate_correctness((observation(Outcome.FAIL),), now=NOW) == PublicState.DEGRADED


def test_status_registry_separates_user_capabilities_from_platform_checks():
    capabilities = derive_capability_cards([], ("login", "payroll"))
    platform = derive_platform_checks([], ("database", "background_jobs"))

    assert [item["name"] for item in capabilities] == ["Log in", "Payroll"]
    assert [item["name"] for item in platform] == ["Database connectivity", "Background jobs"]
    assert all(item["state"] == "UNKNOWN" for item in capabilities + platform)


def test_live_evidence_makes_only_measured_checks_available_and_stale_checks_unknown():
    current = {
        "database": {"source": "EXTERNAL_PROBE", "capability": "database", "observed_at": NOW,
                     "outcome": "PASS", "epistemic_state": "KNOWN"},
        "login": {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": NOW,
                  "outcome": "UNKNOWN", "epistemic_state": "UNAVAILABLE"},
    }
    cards = derive_capability_cards([], ("login", "attendance"), current, now=NOW)
    platform = derive_platform_checks([], ("database",), current, now=NOW)
    assert [card["state"] for card in cards] == ["UNKNOWN", "UNKNOWN"]
    assert platform[0]["state"] == "AVAILABLE"
    assert derive_platform_checks([], ("database",), current, now=NOW + timedelta(minutes=6))[0]["state"] == "UNKNOWN"


def test_active_notice_overrides_green_probe():
    current = {"login": {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": NOW,
                         "outcome": "PASS", "epistemic_state": "KNOWN"}}
    notices = [{"capability": "login", "state": "INVESTIGATING", "impact_statement": "Sign-in is impaired."}]
    assert derive_capability_cards(notices, ("login",), current, now=NOW)[0]["state"] == "INVESTIGATING"


def test_newest_active_notice_wins_for_same_capability():
    notices = [
        {"capability": "login", "state": "MONITORING", "impact_statement": "Recovery is being monitored."},
        {"capability": "login", "state": "INVESTIGATING", "impact_statement": "Older investigation."},
    ]
    card = derive_capability_cards(notices, ("login",), now=NOW)[0]
    assert (card["state"], card["label"]) == ("MONITORING", "Recovery is being monitored.")
    resolved = [{"capability": "login", "state": "RESOLVED"}, *notices]
    assert derive_capability_cards(resolved, ("login",), now=NOW)[0] == card


def test_fresh_known_failure_overrides_monitoring_card_and_platform_row():
    notices = [
        {"capability": key, "state": "MONITORING", "impact_statement": "Recovery is being monitored."}
        for key in ("login", "database")
    ] + [
        {"capability": key, "state": "INVESTIGATING", "impact_statement": "Older investigation."}
        for key in ("login", "database")
    ]
    current = {
        key: {"source": "EXTERNAL_PROBE", "capability": key, "observed_at": NOW,
              "outcome": "FAIL", "epistemic_state": "KNOWN"}
        for key in ("login", "database")
    }

    card = derive_capability_cards(notices, ("login",), current, now=NOW)[0]
    row = derive_platform_checks(notices, ("database",), current, now=NOW)[0]
    assert card["state"] == row["state"] == "DEGRADED"
    assert card["label"] == row["detail"] == "The current check detected a problem. Observed 2026-09-05 12:00 UTC."
    assert card["checked"] == "2026-09-05 12:00 UTC"


def test_hero_guidance_uses_selected_older_investigation_not_newer_monitoring():
    derive_overall_status = _overall_status()
    notices = [
        {"capability": "payroll", "state": "MONITORING", "impact_statement": "Payroll recovering.",
         "recommended_user_action": "Wait for payroll."},
        {"capability": "login", "state": "INVESTIGATING", "impact_statement": "Sign-in impaired.",
         "recommended_user_action": "Use another sign-in method."},
    ]
    hero = derive_overall_status(notices)
    assert hero["state"] == "INVESTIGATING"
    assert hero["notice"] is notices[1]
    assert hero["detail"] == "Sign-in impaired."


def test_hero_probe_failure_does_not_inherit_unrelated_notice_guidance():
    derive_overall_status = _overall_status()
    now = datetime.now(timezone.utc)
    notices = [{"capability": "payroll", "state": "MONITORING",
                "recommended_user_action": "Wait for payroll."}]
    evidence = {"login": {"source": "EXTERNAL_PROBE", "capability": "login",
                          "observed_at": now, "outcome": "FAIL", "epistemic_state": "KNOWN"}}
    cards = derive_capability_cards(notices, ("login",), evidence, now=now)
    hero = derive_overall_status(notices, cards, [], evidence)
    assert hero["state"] == "DEGRADED"
    assert hero.get("notice") is None


def test_public_page_renders_guidance_only_for_hero_condition(monkeypatch):
    _overall_status()
    create_app = sys.modules["status_service.app"].create_app
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")
    monkeypatch.setenv("STATUS_CAPABILITIES", "login")
    monkeypatch.setenv("STATUS_PLATFORM_CHECKS", "")

    class Store:
        notices = [
            {"capability": "payroll", "state": "MONITORING", "impact_statement": "Payroll recovering.",
             "recommended_user_action": "Wait for payroll."},
            {"capability": "login", "state": "INVESTIGATING", "impact_statement": "Sign-in impaired.",
             "recommended_user_action": "Use another sign-in method."},
        ]
        observations = {}

        def list_notices(self, **_kwargs):
            return self.notices

        def list_active_notices(self):
            return [notice for notice in self.notices if notice["state"] != "RESOLVED"]

        def list_current_observations(self):
            return self.observations

    store = Store()
    client = create_app(store=store).test_client()
    page = client.get("/").get_data(as_text=True)
    assert "Use another sign-in method." in page
    assert "Wait for payroll." not in page

    store.observations = {"login": {"source": "EXTERNAL_PROBE", "capability": "login",
                                    "observed_at": datetime.now(timezone.utc),
                                    "outcome": "FAIL", "epistemic_state": "KNOWN"}}
    page = client.get("/").get_data(as_text=True)
    assert "A current check detected a service problem." in page
    assert "Use another sign-in method." not in page
    assert "Wait for payroll." not in page


def test_old_unresolved_notice_survives_more_than_twenty_newer_resolutions(monkeypatch):
    _overall_status()
    from status_service.store import FirestoreNoticeStore
    create_app = sys.modules["status_service.app"].create_app
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")
    monkeypatch.setenv("STATUS_CAPABILITIES", "login")
    monkeypatch.setenv("STATUS_PLATFORM_CHECKS", "")

    class Snapshot:
        def __init__(self, document):
            self.id = document["incident_ref"]
            self.document = document

        def to_dict(self):
            return self.document

    class Query:
        def __init__(self, documents):
            self.documents = documents

        def where(self, field, operator, value):
            assert (field, operator) == ("state", "==")
            return Query([document for document in self.documents if document[field] == value])

        def order_by(self, *_args, **_kwargs):
            return Query(sorted(self.documents, key=lambda document: document["updated_at"], reverse=True))

        def limit(self, count):
            return Query(self.documents[:count])

        def stream(self):
            return (Snapshot(document) for document in self.documents)

    class Client:
        def __init__(self, documents, observations):
            self.documents = documents
            self.observations = observations

        def collection(self, name):
            if name == "external_status_notices":
                return Query(self.documents)
            assert name == "external_status_current"
            return Query([{"incident_ref": key, **value} for key, value in self.observations.items()])

    now = datetime.now(timezone.utc)
    open_notice = {"incident_ref": "still-open", "capability": "login", "state": "INVESTIGATING",
                   "impact_statement": "Sign-in is impaired.", "recommended_user_action": "Try later.",
                   "updated_at": now - timedelta(days=1)}
    resolved = [{"incident_ref": f"closed-{index}", "capability": "login", "state": "RESOLVED",
                 "updated_at": now - timedelta(minutes=index)} for index in range(21)]
    observations = {"login": {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": now,
                              "outcome": "PASS", "epistemic_state": "KNOWN"}}
    store = FirestoreNoticeStore(Client([*resolved, open_notice], observations))
    assert all(notice["incident_ref"] != "still-open" for notice in store.list_notices(limit=20))
    page = create_app(store=store).test_client().get("/").get_data(as_text=True)
    assert "Sign-in is impaired." in page
    assert "Try later." in page
    assert "DETECTED PROBLEMS" in page
    assert "EVERYTHING IS WORKING" not in page


def test_fresh_known_failure_takes_precedence_over_monitoring_hero():
    derive_overall_status = _overall_status()
    now = datetime.now(timezone.utc)
    current = {"login": {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": now,
                         "outcome": "FAIL", "epistemic_state": "KNOWN"}}
    notices = [{"capability": "login", "state": "MONITORING", "impact_statement": "Recovery is being monitored."}]
    cards = derive_capability_cards(notices, ("login",), current, now=now)
    hero = derive_overall_status(notices, cards, [], current)
    assert hero["state"] == "DEGRADED"
    assert hero["label"] == "DETECTED PROBLEMS"
    assert "detected a service problem" in hero["headline"]
    assert hero["checked"] != "awaiting monitoring evidence"
    assert derive_overall_status(notices, cards, [], {"login": {**current["login"], "observed_at": now - timedelta(minutes=6)}})["state"] == "MONITORING"


def test_unavailable_probe_failure_does_not_claim_feature_or_hero_problem():
    derive_overall_status = _overall_status()
    current = {"login": {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": NOW,
                         "outcome": "FAIL", "epistemic_state": "UNAVAILABLE"}}
    cards = derive_capability_cards([], ("login",), current, now=NOW)
    assert cards[0]["state"] == "UNKNOWN"
    assert derive_overall_status([], cards, [], current)["state"] == "UNKNOWN"


def test_last_checked_excludes_rejected_current_records():
    derive_overall_status = _overall_status()
    now = datetime.now(timezone.utc)
    valid = {"source": "EXTERNAL_PROBE", "capability": "login", "observed_at": now,
             "outcome": "PASS", "epistemic_state": "KNOWN"}
    cards = [{"key": "login", "state": "AVAILABLE"}]
    for bad in (
        {**valid, "source": "GRAFANA_TELEMETRY"},
        {**valid, "capability": "payroll"},
        {**valid, "outcome": "PASS", "epistemic_state": "UNAVAILABLE"},
    ):
        assert derive_overall_status([], cards, [], {"login": bad})["checked"] == "awaiting monitoring evidence"
    assert derive_overall_status([], cards, [], {"login": valid})["checked"] != "awaiting monitoring evidence"


def test_public_page_uses_one_clock_at_freshness_boundary(monkeypatch):
    _overall_status()
    module = sys.modules["status_service.app"]
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")
    monkeypatch.setenv("STATUS_CAPABILITIES", "login")
    monkeypatch.setenv("STATUS_PLATFORM_CHECKS", "")

    class Clock(datetime):
        calls = 0

        @classmethod
        def now(cls, tz=None):
            value = NOW + timedelta(microseconds=cls.calls)
            cls.calls += 1
            return value

    class Store:
        def list_active_notices(self):
            return []

        def list_current_observations(self):
            return {"login": {"source": "EXTERNAL_PROBE", "capability": "login",
                              "observed_at": NOW - timedelta(minutes=5),
                              "outcome": "PASS", "epistemic_state": "KNOWN"}}

    monkeypatch.setattr(module, "datetime", Clock)
    page = module.create_app(store=Store()).test_client().get("/").get_data(as_text=True)
    assert "EVERYTHING IS WORKING" in page
    assert "Last checked: 2026-09-05 11:55 UTC" in page
    assert Clock.calls == 1


@pytest.mark.parametrize("value,expected", [
    (datetime(2026, 9, 19, 19, 30, tzinfo=timezone.utc), "2026-09-19 19:30 UTC"),
    ("2026-09-19T12:30:00-07:00", "2026-09-19 19:30 UTC"),
    ("2026-09-19T19:30", "2026-09-19 19:30 (timezone not provided)"),
    (datetime(2026, 9, 19, 19, 30), "2026-09-19 19:30 (timezone not provided)"),
    ("invalid-time", "Time unavailable"),
])
def test_public_next_update_formats_time_without_inventing_timezone(monkeypatch, value, expected):
    _overall_status()
    module = sys.modules["status_service.app"]
    monkeypatch.setenv("STATUS_SERVICE_MODE", "public")

    class Store:
        def list_active_notices(self):
            return [{"state": "INVESTIGATING", "capability": "login",
                     "impact_statement": "Sign-in impaired.", "next_update_at": value,
                     "recommended_user_action": "Please wait."}]

        def list_current_observations(self):
            return {}

    page = module.create_app(store=Store()).test_client().get("/").get_data(as_text=True)
    assert f"Next update:</strong> {expected}" in page


def _overall_status():
    """Load the pure hero projection without optional cloud runtime packages."""
    if "status_service.app" not in sys.modules:
        identity = types.ModuleType("status_service.identity")
        identity.authenticated_operator_email = lambda *_: None
        cloud = types.ModuleType("google.cloud")
        cloud.firestore = types.SimpleNamespace(Client=lambda **_: None)
        google = types.ModuleType("google")
        google.cloud = cloud
        original = {name: sys.modules.get(name) for name in ("status_service.identity", "google", "google.cloud")}
        try:
            sys.modules.update({"status_service.identity": identity, "google": google, "google.cloud": cloud})
            importlib.import_module("status_service.app")
        finally:
            for name, value in original.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
    return sys.modules["status_service.app"].derive_overall_status
