from datetime import datetime, timezone

import pytest

from status.contracts import (
    ExternalObservationRecord, ExternalStatusNoticeEvent, NoticeState,
    RecoveryExpectationState,
)
from status.projection import EpistemicState, EvidenceSource, ObservationClass, Outcome


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def test_observation_contract_rejects_unbounded_or_invalid_state():
    record = ExternalObservationRecord(
        "obs-1", NOW, "corr-1", EvidenceSource.GRAFANA_TELEMETRY, "public_service", ObservationClass.LIVENESS,
        Outcome.PASS, EpistemicState.UNAVAILABLE, "ok", 10, "probe-v1", "REALTIME", "UNKNOWN", None,
    )
    with pytest.raises(ValueError):
        record.validate()


@pytest.mark.parametrize("latency,status", [(-1, 200), (600001, 200), (0, 99), (0, 600), (0, True)])
def test_observation_contract_bounds_transport_result(latency, status):
    record = ExternalObservationRecord(
        "obs-transport", NOW, "corr-1", EvidenceSource.EXTERNAL_PROBE, "public_service",
        ObservationClass.LIVENESS, Outcome.UNKNOWN, EpistemicState.UNAVAILABLE,
        "PROBE_UNAVAILABLE", latency, "probe-v1", "REALTIME", "UNKNOWN", None,
        transport_http_status=status,
    )
    with pytest.raises(ValueError, match="transport"):
        record.validate()


def test_notice_contract_requires_explicit_recovery_and_next_update_state():
    notice = ExternalStatusNoticeEvent(
        "notice-1", "event-1", "PUBLISHED", NOW, NoticeState.INVESTIGATING,
        "public_service", "Service reachability is impaired.", "NO_ACTION_REQUIRED",
        RecoveryExpectationState.UNAVAILABLE, None, None, True, ("obs-1",),
    )
    notice.validate()


def test_notice_contract_rejects_recovery_state_without_matching_expectation():
    notice = ExternalStatusNoticeEvent(
        "notice-1", "event-1", "PUBLISHED", NOW, NoticeState.MONITORING,
        "public_service", "Service is recovering.", "NO_ACTION_REQUIRED",
        RecoveryExpectationState.ESTIMATED, None, NOW, False, ("obs-1",),
    )
    with pytest.raises(ValueError):
        notice.validate()
