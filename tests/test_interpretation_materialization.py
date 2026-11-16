"""Slice 8.2c — interpretation cycle-record materialization writer.

The first slice in which DOM-ITR lawfully creates history. These tests are the
acceptance bar for the writer as an independent ITR command (FEAT-PROD-004
orchestration is a later slice and is NOT exercised here):

* a complete lawful payload inserts exactly one record;
* an incomplete payload is rejected (and the writer never trusts a payload's own
  ``coverage.complete`` claim);
* lawful ``not_applicable`` candidates are accepted;
* same-cycle / same-content replay is idempotent success;
* same-cycle / different-content is a fail-closed integrity violation — no update;
* ``reference_configuration`` is persisted exactly as the frozen projection used;
* failures roll back (no partial row);
* records are scoped by ``(class_id, payroll_cycle_id)``;
* the command never calls Analytics.
"""

from __future__ import annotations

import copy
import inspect
from datetime import timedelta
from uuid import uuid4

import pytest

from app.feats.base import FEATContext
from app.models import InterpretationCycleRecord
from app.services.interpretation.compute import compute_partial_payload
from app.services.interpretation.materialization import (
    CycleMaterializationConflict,
    materialize_interpretation_cycle,
)
from app.services.interpretation.observation_contract import ObservationContractError
from app.services.interpretation.reference_configuration import (
    capture_reference_configuration,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers import temporal
from tests.helpers.class_domain import disable_class_feature
from tests.helpers.classroom_initializer import initialize


def _window():
    now = utc_now()
    return now - timedelta(hours=1), now + timedelta(hours=1)


def _materialize(cid, cycle_id, payload, start, end, feat="FEAT-ITR-001"):
    with FEATContext(feat, idempotency_key=f"itr:materialize:{cycle_id}"):
        return materialize_interpretation_cycle(
            class_id=cid, payroll_cycle_id=cycle_id,
            cycle_started_at=start, cycle_completed_at=end,
            observations_json=payload,
        )


def test_complete_payload_inserts_exactly_one_record(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)
    assert payload["coverage"]["complete"] is True

    cycle_id = str(uuid4())
    result = _materialize(cid, cycle_id, payload, start, end)

    assert result.created is True
    assert result.record.id is not None
    rows = InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id
    ).all()
    assert len(rows) == 1
    assert rows[0].observations_json["coverage"]["complete"] is True
    assert len(rows[0].observations_json["observations"]) == 17


def test_incomplete_payload_rejected_even_if_it_claims_complete(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)

    # Drop Q9-C1 but LIE that coverage is complete — the writer re-derives it.
    payload["observations"] = [
        o for o in payload["observations"] if o["candidate_id"] != "Q9-C1"
    ]
    payload["coverage"]["complete"] = True

    cycle_id = str(uuid4())
    with pytest.raises(ObservationContractError):
        _materialize(cid, cycle_id, payload, start, end)

    # Rollback: no partial row.
    assert InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id
    ).count() == 0


def test_not_applicable_candidates_are_accepted(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    disable_class_feature(class_id=cid, feature="banking")  # savings off → Q4/Q6-C2 N/A
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)
    assert payload["coverage"]["complete"] is True

    cycle_id = str(uuid4())
    result = _materialize(cid, cycle_id, payload, start, end)

    assert result.created is True
    obs = {o["candidate_id"]: o for o in result.record.observations_json["observations"]}
    assert obs["Q4-C1"]["applicability"] == "not_applicable"
    assert obs["Q6-C2"]["applicability"] == "not_applicable"


def test_replay_same_cycle_same_content_is_idempotent(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)
    cycle_id = str(uuid4())

    first = _materialize(cid, cycle_id, payload, start, end)
    second = _materialize(cid, cycle_id, payload, start, end)

    assert first.created is True
    assert second.created is False
    assert second.record.id == first.record.id
    assert InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id
    ).count() == 1


def test_replay_same_cycle_different_content_fails_closed_no_update(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)
    cycle_id = str(uuid4())

    first = _materialize(cid, cycle_id, payload, start, end)
    stored_before = copy.deepcopy(first.record.observations_json)

    # A lawful-but-different complete payload: mutate one value string in place.
    mutated = copy.deepcopy(payload)
    for entry in mutated["observations"]:
        if entry["candidate_id"] == "Q1a-C1":
            entry["value"]["value"] = "0.4242"
    assert mutated != payload

    with pytest.raises(CycleMaterializationConflict):
        _materialize(cid, cycle_id, mutated, start, end)

    # Immutable: the stored record is unchanged — no update path exists.
    row = InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id
    ).one()
    assert row.observations_json == stored_before
    assert InterpretationCycleRecord.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id
    ).count() == 1


def test_reference_configuration_persisted_exactly_as_frozen_projection(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    start, end = _window()
    payload = compute_partial_payload(cid, start, end)
    cycle_id = str(uuid4())

    expected = capture_reference_configuration(cid, cycle_completed_at=end)
    result = _materialize(cid, cycle_id, payload, start, end)

    assert result.reference_configuration == expected
    assert result.record.reference_configuration == expected
    # 2: the policy block names the payroll_settings row (operator ruling 2026-09-30).
    assert result.record.reference_configuration["schema_version"] == 2
    assert set(result.record.reference_configuration) == {
        "schema_version", "economic_engine", "policy"
    }


def test_reference_configuration_binds_expected_weekly_hours_to_cycle_boundary(app):
    """DOM-ITR-001 §IX: ``expected_weekly_hours``/``cwi`` are bound to the cycle's
    closing boundary the same way ``hourly_pay_rate``/``policy`` already are — not
    to whichever Economic Engine version happens to be current when the writer
    actually runs. A version saved after the boundary but before materialization
    must not leak into the closed cycle's frozen reference values."""
    from app.extensions import db
    from app.models import EconomicEngine

    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    # The closing boundary sits well after the provisioned root engine (so the
    # governing version below supersedes it) and well before the "later" version
    # (so that version is unambiguously saved after the cycle closed).
    boundary = temporal.shifted(temporal.now(), hours=1)

    root = (
        EconomicEngine.query.filter_by(class_id=cid)
        .order_by(EconomicEngine.created_at.asc())
        .first()
    )
    governing_effective_at = temporal.shifted(boundary, minutes=-5)
    later_effective_at = temporal.shifted(boundary, minutes=5)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"econ-engine-fixture:{cid}"):
        governing_version = EconomicEngine(
            class_id=cid,
            previous_version_id=root.economic_version_id,
            expected_weekly_hours=12.5,
            economy_policy_mode="default",
            effective_at=governing_effective_at,
            created_at=governing_effective_at,
        )
        db.session.add(governing_version)
        db.session.flush()
        # Saved after the boundary closed — must govern only the NEXT cycle.
        later_version = EconomicEngine(
            class_id=cid,
            previous_version_id=governing_version.economic_version_id,
            expected_weekly_hours=17.5,
            economy_policy_mode="default",
            effective_at=later_effective_at,
            created_at=later_effective_at,
        )
        db.session.add(later_version)
        db.session.flush()
    db.session.commit()

    captured = capture_reference_configuration(cid, cycle_completed_at=boundary)

    # Provisioned default pay_rate is $0.50/min -> $30.00/hr.
    assert captured["economic_engine"]["expected_weekly_hours"] == "12.5"
    assert captured["economic_engine"]["cwi"] == "375.00"

    # A cycle closing after the later version took effect sees that version.
    captured_next_cycle = capture_reference_configuration(
        cid, cycle_completed_at=temporal.shifted(boundary, minutes=10)
    )
    assert captured_next_cycle["economic_engine"]["expected_weekly_hours"] == "17.5"
    assert captured_next_cycle["economic_engine"]["cwi"] == "525.00"

    # A version effective EXACTLY at the closing boundary must not govern that
    # boundary's own cycle: the resolver is strict-before (`<`), not `<=`, so a
    # cycle whose cycle_completed_at lands exactly on later_version.effective_at
    # still sees governing_version, not later_version.
    captured_at_later_effective_at = capture_reference_configuration(
        cid, cycle_completed_at=later_version.effective_at
    )
    assert captured_at_later_effective_at["economic_engine"]["expected_weekly_hours"] == "12.5"
    assert captured_at_later_effective_at["economic_engine"]["cwi"] == "375.00"

    # Symmetrically, a cycle closing exactly at governing_version's own
    # effective_at does not see governing_version either — it governs from the
    # version before it (the provisioned root, with no expected_weekly_hours set).
    captured_at_governing_effective_at = capture_reference_configuration(
        cid, cycle_completed_at=governing_version.effective_at
    )
    assert captured_at_governing_effective_at["economic_engine"]["expected_weekly_hours"] is None
    assert captured_at_governing_effective_at["economic_engine"]["cwi"] is None


def test_records_are_scoped_by_class_and_cycle(app):
    class_a = initialize("chemistry_p1", app).class_id
    class_b = initialize("chemistry_p1", app).class_id
    assert class_a != class_b
    start, end = _window()
    cycle_id = str(uuid4())  # SAME cycle id presented to two different classes

    payload_a = compute_partial_payload(class_a, start, end)
    payload_b = compute_partial_payload(class_b, start, end)
    _materialize(class_a, cycle_id, payload_a, start, end)
    _materialize(class_b, cycle_id, payload_b, start, end)

    # Two independent records — the uniqueness key is (class_id, payroll_cycle_id).
    assert InterpretationCycleRecord.query.filter_by(
        class_id=class_a, payroll_cycle_id=cycle_id
    ).count() == 1
    assert InterpretationCycleRecord.query.filter_by(
        class_id=class_b, payroll_cycle_id=cycle_id
    ).count() == 1
    # Class A's cycle is not visible under class B's scope beyond its own row.
    assert InterpretationCycleRecord.query.filter_by(class_id=class_a).count() == 1


def test_materialization_command_never_imports_analytics(app):
    import ast

    import app.services.interpretation.materialization as materialization
    import app.services.interpretation.reference_configuration as refconfig

    for module in (materialization, refconfig):
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        assert not any("analytics" in name.lower() for name in imported), imported
