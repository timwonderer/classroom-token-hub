"""Pure, bounded status projection rules from SPEC-OPS-002 and Batch B."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class ObservationClass(str, Enum):
    LIVENESS = "LIVENESS"
    READINESS = "READINESS"
    CORRECTNESS = "CORRECTNESS"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EpistemicState(str, Enum):
    KNOWN = "KNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class PublicState(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class EvidenceSource(str, Enum):
    INVARIANT_VERIFIER = "INVARIANT_VERIFIER"
    GRAFANA_TELEMETRY = "GRAFANA_TELEMETRY"
    EXTERNAL_PROBE = "EXTERNAL_PROBE"
    DOM_OPS_PUBLICATION = "DOM_OPS_PUBLICATION"


CAPABILITY_LABELS = {
    "login": ("Log in", "Can I sign in right now?"),
    "attendance": ("Attendance", "Can I record or view attendance right now?"),
    "payroll": ("Payroll", "Can I run or view payroll right now?"),
    "roster": ("Roster management", "Can I add or edit a roster right now?"),
    "classroom_economy": ("Classroom economy", "Can I use classroom economy features right now?"),
    "public_service_reachability": ("App availability", "Can I access Classroom Token Hub right now?"),
    "ledger_correctness": ("Ledger correctness", "Are account balances and transactions correct?"),
}

PLATFORM_CHECK_LABELS = {
    "database": "Database connectivity",
    "background_jobs": "Background jobs",
    "external_integrations": "External integrations",
    "monitoring_freshness": "Monitoring freshness",
    "invariant_verification": "Invariant verification",
}


def _active_notice_index(notices: list[dict]) -> dict:
    return {notice.get("capability"): notice for notice in notices if notice.get("state") != "RESOLVED"}


def derive_capability_cards(notices: list[dict], capabilities: tuple[str, ...]) -> list[dict[str, str]]:
    active = _active_notice_index(notices)
    cards = []
    for capability in capabilities:
        name, question = CAPABILITY_LABELS.get(capability, (capability.replace("_", " ").title(), "Is this service working right now?"))
        notice = active.get(capability)
        cards.append({
            "key": capability,
            "name": name,
            "question": question,
            "state": notice.get("state", "UNKNOWN") if notice else "UNKNOWN",
            "label": notice.get("impact_statement", "Monitoring evidence is not available yet.") if notice else "Monitoring evidence is not available yet.",
            "checked": "Active status notice" if notice else "No verified observation yet",
        })
    return cards


def derive_platform_checks(notices: list[dict], checks: tuple[str, ...]) -> list[dict[str, str]]:
    active = _active_notice_index(notices)
    rows = []
    for check in checks:
        notice = active.get(check)
        rows.append({
            "key": check,
            "name": PLATFORM_CHECK_LABELS.get(check, check.replace("_", " ").title()),
            "state": notice.get("state", "UNKNOWN") if notice else "UNKNOWN",
            "detail": notice.get("impact_statement", "No current platform evidence is available.") if notice else "No current platform evidence is available.",
        })
    return rows


FRESHNESS_MAX_AGE = {
    "REALTIME": timedelta(minutes=5),
    "PERIODIC_CORRECTNESS": timedelta(minutes=30),
    "DEEP_INTEGRITY": timedelta(hours=2),
}

_VALID_RAW_STATES = {
    (Outcome.PASS, EpistemicState.KNOWN),
    (Outcome.FAIL, EpistemicState.KNOWN),
    (Outcome.FAIL, EpistemicState.UNAVAILABLE),
    (Outcome.UNKNOWN, EpistemicState.UNAVAILABLE),
}


@dataclass(frozen=True)
class Observation:
    source: EvidenceSource
    capability: str
    observation_class: ObservationClass
    outcome: Outcome
    epistemic_state: EpistemicState
    observed_at: datetime
    freshness_class: str
    diagnostic_code: str | None = None

    def validate(self) -> None:
        if not self.source:
            raise ValueError("Observation evidence source is required.")
        if (self.outcome, self.epistemic_state) not in _VALID_RAW_STATES:
            raise ValueError("Invalid raw observation outcome/epistemic-state combination.")
        if self.freshness_class not in FRESHNESS_MAX_AGE:
            raise ValueError("Unknown freshness class.")

    def is_fresh(self, now: datetime) -> bool:
        self.validate()
        current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        observed = self.observed_at if self.observed_at.tzinfo else self.observed_at.replace(tzinfo=timezone.utc)
        return current - observed <= FRESHNESS_MAX_AGE[self.freshness_class]


def aggregate_correctness(observations: tuple[Observation, ...], *, now: datetime) -> PublicState:
    """Apply approved correctness aggregation; raw evidence is never public."""
    if not observations:
        return PublicState.UNKNOWN
    for observation in observations:
        observation.validate()
    if any(not observation.is_fresh(now) for observation in observations):
        return PublicState.UNKNOWN
    if any(observation.outcome == Outcome.FAIL for observation in observations):
        return PublicState.DEGRADED
    if any(observation.outcome == Outcome.UNKNOWN for observation in observations):
        return PublicState.UNKNOWN
    return PublicState.AVAILABLE


__all__ = [
    "CAPABILITY_LABELS", "EpistemicState", "EvidenceSource", "FRESHNESS_MAX_AGE", "Observation", "ObservationClass",
    "Outcome", "PLATFORM_CHECK_LABELS", "PublicState", "aggregate_correctness", "derive_capability_cards",
    "derive_platform_checks",
]
