from datetime import datetime, timedelta, timezone

import pytest

from status.projection import (
    EpistemicState, Observation, ObservationClass, Outcome, PublicState,
    aggregate_correctness,
)


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def observation(outcome, epistemic=EpistemicState.KNOWN, age=timedelta(minutes=1)):
    return Observation(
        capability="ledger_correctness",
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
