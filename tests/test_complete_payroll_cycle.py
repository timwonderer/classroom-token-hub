"""Slice 8.3d — FEAT-PROD-004 Complete Payroll Cycle orchestration.

Individual business behavior is certified underneath (8.2b/8.2c/8.3b/8.3c/substrate),
so this suite is mostly about transactional atomicity and the replay seam:

* normal run → PROD events + one ITR record + one completion anchor, all sharing
  the cycle identity;
* nothing is activated at the boundary: a change saved for later is an
  effective-dated row that time puts in force (DOM-CLASS-003 §VII);
* replay after commit → same payroll_cycle_id AND zero downstream work (spied);
* failure at every step → nothing persists, the completion anchor never survives;
* commit failure → no completed-run state subsequently resolves.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
import app.feats.complete_payroll_cycle as orch
from app.feats.complete_payroll_cycle import complete_payroll_cycle
from app.models import (
    AttendanceSession,
    EconomicEngine,
    InterpretationCycleRecord,
    PayrollEvent,
)
from app.services.class_configuration_query_service import (
    economic_engine_effective_at,
    get_current_economic_engine,
)
from app.services.context_resolver import CanonicalContext
from app.services.payroll.cycle_completion import resolve_completed_run
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize

_DOWNSTREAM = [
    "allocate_payroll_cycle_id",
    "settle_class_payroll_cycle",
    "compute_partial_payload",
    "materialize_interpretation_cycle",
    "record_run_completion",
]


def _raiser(msg):
    def _fn(*args, **kwargs):
        raise RuntimeError(msg)
    return _fn


def _ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user_id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id, actor_role="teacher",
    )


def _seed_run(classroom):
    """Seed attendance for two seats. Returns (cid, start, end)."""
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    start, end = now - timedelta(hours=1), now + timedelta(hours=1)

    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        for seat in (sA, sB):
            db.session.add(AttendanceSession(
                target_seat_id=seat.seat_id, class_id=cid,
                actor_seat_id=teacher_seat_id, reason_code="start_work",
                timestamp=now - timedelta(minutes=30),
            ))
            # Closed: payroll settles finished sessions only (DOM-PROD-001 §VI.3).
            db.session.add(AttendanceSession(
                target_seat_id=seat.seat_id, class_id=cid,
                actor_seat_id=teacher_seat_id, status="inactive",
                reason_code="done_for_day", timestamp=now - timedelta(minutes=10),
            ))
        db.session.flush()

    return cid, start, end


def _seed_pending_engine(cid, effective_at):
    """Append an engine version dated for later: pending until ``effective_at``."""
    current = get_current_economic_engine(cid)
    now = utc_now()
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"engine:{cid}"):
        pending = EconomicEngine(
            class_id=cid, previous_version_id=current.economic_version_id,
            economy_policy_mode="tight", created_at=now, effective_at=effective_at,
        )
        db.session.add(pending)
        db.session.flush()
    return current.economic_version_id, pending.economic_version_id


def _run(classroom, key, start, end):
    with FEATContext("FEAT-PROD-004", idempotency_key=key):
        return complete_payroll_cycle(
            ctx=_ctx(classroom), idempotency_key=key,
            cycle_started_at=start, cycle_completed_at=end,
            run_mechanism="TEACHER",
        )


def _expect_rollback(classroom, key, start, end):
    with pytest.raises(RuntimeError):
        _run(classroom, key, start, end)


def _assert_nothing_persisted(cid, key):
    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 0
    assert resolve_completed_run(cid, key) is None


# --------------------------------------------------------------------------- #
# Normal run                                                                  #
# --------------------------------------------------------------------------- #


def test_normal_run_completes_the_economic_cycle(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_run(classroom)
    key = f"run:{uuid4()}"

    result = _run(classroom, key, start, end)
    cycle = result.payroll_cycle_id

    assert result.created is True
    # PROD: payroll events for the two attended seats, all stamped with the cycle.
    events = PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle, payroll_event_type="payroll"
    ).all()
    assert len(events) == len(result.settled_seat_ids) == 2

    # ITR: exactly one immutable, complete record bound to the cycle.
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle).one()
    assert record.id == result.interpretation_record_id
    assert record.observations_json["coverage"]["complete"] is True

    # Completion anchor written last — the run is now resolvable.
    assert result.completion_created is True
    assert resolve_completed_run(cid, key) == cycle


def test_the_boundary_activates_nothing_a_pending_row_waits_for_its_date(app):
    """A version dated past the boundary stays pending through the run: the run
    neither activates it nor writes any engine row (DOM-CLASS-003 §VII)."""
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_run(classroom)
    later = end + timedelta(days=1)
    in_force_id, pending_id = _seed_pending_engine(cid, later)
    engine_rows = EconomicEngine.query.filter_by(class_id=cid).count()
    key = f"run:{uuid4()}"

    result = _run(classroom, key, start, end)

    assert result.created is True
    assert EconomicEngine.query.filter_by(class_id=cid).count() == engine_rows
    assert economic_engine_effective_at(cid, end).economic_version_id == in_force_id
    assert economic_engine_effective_at(cid, later).economic_version_id == pending_id
    assert resolve_completed_run(cid, key) == result.payroll_cycle_id


# --------------------------------------------------------------------------- #
# Replay: same id, zero downstream work                                       #
# --------------------------------------------------------------------------- #


def test_replay_returns_same_id_and_does_zero_downstream_work(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_run(classroom)
    key = f"run:{uuid4()}"

    first = _run(classroom, key, start, end)

    # Spy on every downstream operation; a replay must call none of them.
    spies = {}
    for name in _DOWNSTREAM:
        spy = MagicMock(name=name)
        monkeypatch.setattr(orch, name, spy)
        spies[name] = spy

    replay = _run(classroom, key, start, end)

    assert replay.payroll_cycle_id == first.payroll_cycle_id
    assert replay.created is False
    for name, spy in spies.items():
        spy.assert_not_called()

    # And no duplicate rows appeared.
    assert PayrollEvent.query.filter_by(class_id=cid, payroll_cycle_id=first.payroll_cycle_id).count() == 2
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1


# --------------------------------------------------------------------------- #
# Failure injection at every step → nothing persists                         #
# --------------------------------------------------------------------------- #


def test_prod_failure_persists_nothing(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "settle_class_payroll_cycle", _raiser("PROD fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_itr_compute_failure_rolls_back_payroll(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    # Real PROD settlement flushes events, then compute fails → must roll back.
    monkeypatch.setattr(orch, "compute_partial_payload", _raiser("ITR compute fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_itr_materialization_failure_rolls_back(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "materialize_interpretation_cycle", _raiser("ITR materialize fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_completion_anchor_failure_rolls_back_everything(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_run(classroom)
    key = f"run:{uuid4()}"
    monkeypatch.setattr(orch, "record_run_completion", _raiser("completion fail"))

    _expect_rollback(classroom, key, start, end)
    _assert_nothing_persisted(cid, key)


def test_commit_failure_leaves_no_resolvable_completed_run(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end, *_ = _seed_run(classroom)
    key = f"run:{uuid4()}"

    # The full pipeline succeeds, then the caller's transaction aborts before
    # commit (simulating a commit-time failure): nothing may survive.
    with pytest.raises(RuntimeError):
        with FEATContext("FEAT-PROD-004", idempotency_key=key):
            complete_payroll_cycle(
                ctx=_ctx(classroom), idempotency_key=key,
                cycle_started_at=start, cycle_completed_at=end,
                run_mechanism="TEACHER",
            )
            raise RuntimeError("commit fails")

    _assert_nothing_persisted(cid, key)
