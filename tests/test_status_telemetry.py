from datetime import datetime, timezone

import pytest

from status.projection import EpistemicState, EvidenceSource, ObservationClass, Outcome
from status.telemetry import TelemetryResult


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def test_grafana_telemetry_pass_becomes_known_pass_observation():
    observation = TelemetryResult(
        "public_service", ObservationClass.LIVENESS, NOW, True, "route_ok"
    ).to_observation()

    assert observation.source is EvidenceSource.GRAFANA_TELEMETRY
    assert observation.outcome is Outcome.PASS
    assert observation.epistemic_state is EpistemicState.KNOWN


def test_grafana_telemetry_failure_becomes_known_failure_observation():
    observation = TelemetryResult(
        "public_service", ObservationClass.READINESS, NOW, False, "http_5xx_rate"
    ).to_observation()

    assert observation.outcome is Outcome.FAIL
    assert observation.epistemic_state is EpistemicState.KNOWN


def test_grafana_telemetry_unavailable_is_not_pass():
    observation = TelemetryResult(
        "public_service", ObservationClass.LIVENESS, NOW, None, "query_unavailable"
    ).to_observation()

    assert observation.outcome is Outcome.UNKNOWN
    assert observation.epistemic_state is EpistemicState.UNAVAILABLE


def test_grafana_telemetry_diagnostic_code_is_bounded():
    result = TelemetryResult(
        "public_service", ObservationClass.LIVENESS, NOW, True, "x" * 65
    )
    with pytest.raises(ValueError):
        result.to_observation()
