"""Bounded telemetry-to-observation translation.

The transport/query layer is deliberately outside this module.  Grafana and
Prometheus are evidence sources; this module only translates an already
bounded, approved result into the status observation contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .projection import (
    EpistemicState,
    EvidenceSource,
    Observation,
    ObservationClass,
    Outcome,
)


@dataclass(frozen=True)
class TelemetryResult:
    """One bounded result from a configured telemetry query.

    ``healthy`` is deliberately tri-state: ``None`` means the telemetry
    source could not establish a state and must not be treated as healthy.
    """

    capability: str
    observation_class: ObservationClass
    observed_at: datetime
    healthy: bool | None
    diagnostic_code: str
    freshness_class: str = "REALTIME"

    def to_observation(self) -> Observation:
        if not self.capability:
            raise ValueError("Telemetry capability is required.")
        if not self.diagnostic_code or len(self.diagnostic_code) > 64:
            raise ValueError("Telemetry diagnostic_code must be bounded.")

        if self.healthy is True:
            outcome, epistemic = Outcome.PASS, EpistemicState.KNOWN
        elif self.healthy is False:
            outcome, epistemic = Outcome.FAIL, EpistemicState.KNOWN
        else:
            outcome, epistemic = Outcome.UNKNOWN, EpistemicState.UNAVAILABLE

        observation = Observation(
            source=EvidenceSource.GRAFANA_TELEMETRY,
            capability=self.capability,
            observation_class=self.observation_class,
            outcome=outcome,
            epistemic_state=epistemic,
            observed_at=self.observed_at,
            freshness_class=self.freshness_class,
            diagnostic_code=self.diagnostic_code,
        )
        observation.validate()
        return observation


__all__ = ["TelemetryResult"]
