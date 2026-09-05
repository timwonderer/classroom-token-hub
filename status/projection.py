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
    capability: str
    observation_class: ObservationClass
    outcome: Outcome
    epistemic_state: EpistemicState
    observed_at: datetime
    freshness_class: str
    diagnostic_code: str | None = None

    def validate(self) -> None:
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
    "EpistemicState", "FRESHNESS_MAX_AGE", "Observation", "ObservationClass",
    "Outcome", "PublicState", "aggregate_correctness",
]
