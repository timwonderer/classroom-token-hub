"""Bounded logical status objects from SPEC-OPS-002 §V."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .projection import EpistemicState, ObservationClass, Outcome


class NoticeState(str, Enum):
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class RecoveryExpectationState(str, Enum):
    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ExternalObservationRecord:
    observation_id: str
    observed_at: datetime
    correlation_id: str
    capability: str
    observation_class: ObservationClass
    outcome: Outcome
    epistemic_state: EpistemicState
    diagnostic_code: str
    latency_ms: int | None
    probe_version: str

    def validate(self) -> None:
        if not self.observation_id or not self.correlation_id or not self.capability:
            raise ValueError("Observation identity and capability are required.")
        if not self.diagnostic_code or len(self.diagnostic_code) > 64:
            raise ValueError("Observation diagnostic_code must be bounded.")
        if self.latency_ms is not None and (self.latency_ms < 0 or self.latency_ms > 86_400_000):
            raise ValueError("Observation latency is outside the bounded range.")
        if not self.probe_version or len(self.probe_version) > 32:
            raise ValueError("Observation probe_version must be bounded.")
        if (self.outcome, self.epistemic_state) not in {
            (Outcome.PASS, EpistemicState.KNOWN),
            (Outcome.FAIL, EpistemicState.KNOWN),
            (Outcome.FAIL, EpistemicState.UNAVAILABLE),
            (Outcome.UNKNOWN, EpistemicState.UNAVAILABLE),
        }:
            raise ValueError("Invalid raw observation state combination.")


@dataclass(frozen=True)
class ExternalStatusNoticeEvent:
    external_notice_id: str
    event_id: str
    event_type: str
    published_at: datetime
    state: NoticeState
    capability: str
    impact_statement: str
    recommended_user_action: str
    recovery_state: RecoveryExpectationState
    recovery_expectation: datetime | None
    next_update_at: datetime | None
    next_update_unavailable: bool
    source_observation_ids: tuple[str, ...]
    reconciliation_incident_id: str | None = None

    def validate(self) -> None:
        if not self.external_notice_id or not self.event_id or not self.event_type:
            raise ValueError("Notice identity and event type are required.")
        if not self.capability or not self.impact_statement or not self.recommended_user_action:
            raise ValueError("Notice communication fields are required.")
        if len(self.impact_statement) > 500 or len(self.recommended_user_action) > 240:
            raise ValueError("Notice communication fields exceed bounded limits.")
        if self.recovery_state == RecoveryExpectationState.UNAVAILABLE and self.recovery_expectation is not None:
            raise ValueError("Unavailable recovery expectation cannot carry a timestamp.")
        if self.recovery_state != RecoveryExpectationState.UNAVAILABLE and self.recovery_expectation is None:
            raise ValueError("Known or estimated recovery requires a timestamp.")
        if self.next_update_at is None and not self.next_update_unavailable:
            raise ValueError("Notice requires a next update timestamp or explicit unavailability.")
        if self.next_update_at is not None and self.next_update_unavailable:
            raise ValueError("Notice cannot provide and disclaim a next update simultaneously.")
        if not self.source_observation_ids:
            raise ValueError("Notice requires bounded source observation lineage.")


__all__ = [
    "ExternalObservationRecord", "ExternalStatusNoticeEvent", "NoticeState",
    "RecoveryExpectationState",
]
