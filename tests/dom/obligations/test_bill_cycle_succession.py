"""Bill-cycle succession — DOM-OBL-001 v3.1 §V.7 / §VII.2.

One command, ``schedule_next_bill_cycle``, creates every non-terminal cycle. These
tests hold the contract, not the implementation:

- position is derived: an empty lineage yields cycle 1, a due lineage N+1, and the
  request has no cycle number to supply;
- eligibility is the domain's: succession before the latest cycle's
  ``next_assessment_at`` is denied, and succession after a terminal cycle is denied;
- replay is by command identity: same identity + same terms returns the original
  cycle; same identity + different terms fails closed;
- distinct commands racing for one successor: exactly one creates it, the other
  gets a succession conflict and does NOT fall forward into creating N+2, even
  though N+1 is itself already due.

The race tests use two real Postgres transactions on two threads, with the second
command demonstrably blocked on the first before the first commits.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.schedule_next_bill_cycle_feat import (
    COMMAND_NAME,
    ScheduleNextBillCycleRequest,
    execute_schedule_next_bill_cycle,
    schedule_next_bill_cycle,
)
from app.feats.terminate_bill_cycle_feat import execute_terminate_bill_cycle
from app.models import BillCycle, ObligationCommandReservation
from app.services import obligations_service
from app.services.obligations_service import (
    SuccessionAfterTerminalError,
    SuccessionConflictError,
    SuccessionEligibility,
    SuccessionNotDueError,
    SuccessionReplayMismatchError,
)
from tests.helpers.classroom_initializer import initialize


_BASE = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
_PERIOD = timedelta(days=7)
_BEFORE_ANYTHING = _BASE - timedelta(days=1)
_FAR_FUTURE = _BASE + timedelta(days=365)


def _boundary(k: int) -> datetime:
    """cycle_boundary_at of cycle k; cycle k is next assessed at _boundary(k + 1)."""
    return _BASE + _PERIOD * (k - 1)


def _succeed(class_id, internal_ref, key, k, reference, **overrides):
    """Request succession with the boundaries cycle k would carry."""
    terms = dict(
        cycle_boundary_at=_boundary(k),
        next_assessment_at=_boundary(k + 1),
        policy_uuid="policy-1",
    )
    terms.update(overrides)
    return execute_schedule_next_bill_cycle(
        class_id, internal_ref,
        idempotency_key=key, reference_time_utc=reference, **terms,
    )


def _cycle_numbers(class_id, internal_ref):
    return [
        row.cycle_number
        for row in BillCycle.query.filter_by(class_id=class_id, internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.asc())
    ]


def _reservations(class_id, internal_ref):
    return (
        ObligationCommandReservation.query
        .filter_by(class_id=class_id, internal_ref=internal_ref)
        .order_by(ObligationCommandReservation.id.asc())
        .all()
    )


# --------------------------------------------------------------------------- #
# Position is derived                                                          #
# --------------------------------------------------------------------------- #


def test_succession_of_empty_lineage_derives_cycle_1(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cycle = _succeed(classroom.class_id, "lineage:empty", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        assert cycle.cycle_number == 1
        [reservation] = _reservations(classroom.class_id, "lineage:empty")
        assert reservation.command_name == COMMAND_NAME
        assert reservation.idempotency_key == "k:1"
        assert reservation.bill_cycle_id == cycle.id


def test_succession_of_due_lineage_derives_next_cycle(app):
    """At exactly next_assessment_at the lineage is due ("arrived" is inclusive)."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:due", "k:1", 1, _BEFORE_ANYTHING)
        cycle2 = _succeed(classroom.class_id, "lineage:due", "k:2", 2, _boundary(2))
        db.session.commit()

        assert cycle2.cycle_number == 2
        assert _cycle_numbers(classroom.class_id, "lineage:due") == [1, 2]


def test_request_has_no_cycle_number_to_supply():
    fields = {f.name for f in dataclasses.fields(ScheduleNextBillCycleRequest)}
    assert "cycle_number" not in fields


def test_non_increasing_boundaries_are_rejected_without_writing(app):
    """§VII.2: next_assessment_at MUST be strictly later than cycle_boundary_at."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(ValueError, match="strictly after"):
            _succeed(
                classroom.class_id, "lineage:order", "k:1", 1, _BEFORE_ANYTHING,
                next_assessment_at=_boundary(1),  # equal, not later
            )
        assert _cycle_numbers(classroom.class_id, "lineage:order") == []
        assert _reservations(classroom.class_id, "lineage:order") == []


# --------------------------------------------------------------------------- #
# Eligibility is the domain's                                                  #
# --------------------------------------------------------------------------- #


def test_early_succession_is_denied_without_writing(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:early", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        with pytest.raises(SuccessionNotDueError):
            _succeed(
                classroom.class_id, "lineage:early", "k:2", 2,
                _boundary(2) - timedelta(seconds=1),
            )
        assert _cycle_numbers(classroom.class_id, "lineage:early") == [1]
        assert [r.idempotency_key for r in _reservations(classroom.class_id, "lineage:early")] == ["k:1"]


def test_fresh_identities_cannot_manufacture_cycles_ahead_of_time(app):
    """Without the eligibility rule, a new key per call would mint 2, 3, 4... at once."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:burst", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()
        for n in range(2, 5):
            with pytest.raises(SuccessionNotDueError):
                _succeed(classroom.class_id, "lineage:burst", f"k:{n}", n, _BEFORE_ANYTHING)
        assert _cycle_numbers(classroom.class_id, "lineage:burst") == [1]


def test_succession_after_terminal_cycle_is_denied(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:ended", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()
        execute_terminate_bill_cycle(class_id=classroom.class_id, internal_ref="lineage:ended")
        db.session.commit()

        with pytest.raises(SuccessionAfterTerminalError):
            _succeed(classroom.class_id, "lineage:ended", "k:3", 3, _FAR_FUTURE)
        assert _cycle_numbers(classroom.class_id, "lineage:ended") == [1, 2]


def test_eligibility_query_reports_each_state(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cid, ref = classroom.class_id, "lineage:states"

        def state(reference):
            return obligations_service.get_succession_eligibility(
                cid, ref, reference_time_utc=reference
            )[0]

        assert state(_BEFORE_ANYTHING) is SuccessionEligibility.EMPTY
        _succeed(cid, ref, "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()
        assert state(_boundary(2) - timedelta(seconds=1)) is SuccessionEligibility.NOT_DUE
        assert state(_boundary(2)) is SuccessionEligibility.DUE
        execute_terminate_bill_cycle(class_id=cid, internal_ref=ref)
        db.session.commit()
        assert state(_FAR_FUTURE) is SuccessionEligibility.TERMINAL


# --------------------------------------------------------------------------- #
# Replay is by command identity                                                #
# --------------------------------------------------------------------------- #


def test_exact_replay_returns_original_cycle_and_writes_nothing(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        first = _succeed(classroom.class_id, "lineage:replay", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()
        again = _succeed(classroom.class_id, "lineage:replay", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        assert again.id == first.id
        assert _cycle_numbers(classroom.class_id, "lineage:replay") == [1]
        assert len(_reservations(classroom.class_id, "lineage:replay")) == 1


def test_replay_is_decided_before_eligibility(app):
    """A late retry of an executed command replays even after the lineage moved on,
    rather than being judged against today's lineage state."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        first = _succeed(classroom.class_id, "lineage:late-retry", "k:1", 1, _BEFORE_ANYTHING)
        _succeed(classroom.class_id, "lineage:late-retry", "k:2", 2, _boundary(2))
        db.session.commit()

        retried = _succeed(classroom.class_id, "lineage:late-retry", "k:1", 1, _FAR_FUTURE)
        assert retried.id == first.id
        assert _cycle_numbers(classroom.class_id, "lineage:late-retry") == [1, 2]


@pytest.mark.parametrize("changed", [
    {"next_assessment_at": _boundary(2) + timedelta(hours=1)},
    {"cycle_boundary_at": _boundary(1) - timedelta(hours=1)},
    {"policy_uuid": "policy-2"},
    {"grace_boundary_at": _boundary(1) + timedelta(days=3)},
])
def test_same_identity_with_different_terms_fails_closed(app, changed):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:mismatch", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        with pytest.raises(SuccessionReplayMismatchError):
            _succeed(classroom.class_id, "lineage:mismatch", "k:1", 1, _BEFORE_ANYTHING, **changed)
        assert _cycle_numbers(classroom.class_id, "lineage:mismatch") == [1]
        assert len(_reservations(classroom.class_id, "lineage:mismatch")) == 1


def test_identity_reused_for_another_lineage_is_a_mismatch(app):
    """internal_ref is part of the command's terms, not its identity scope."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:a", "k:shared", 1, _BEFORE_ANYTHING)
        db.session.commit()

        with pytest.raises(SuccessionReplayMismatchError):
            _succeed(classroom.class_id, "lineage:b", "k:shared", 1, _BEFORE_ANYTHING)
        assert _cycle_numbers(classroom.class_id, "lineage:b") == []


def test_identity_scope_is_per_class(app):
    """The same key in two classes names two commands."""
    first = initialize("chemistry_p1", app)
    second = initialize("ap_csp_p3", app)
    with app.app_context():
        a = _succeed(first.class_id, f"lineage:{first.class_id}", "k:1", 1, _BEFORE_ANYTHING)
        b = _succeed(second.class_id, f"lineage:{second.class_id}", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        assert a.id != b.id
        assert a.class_id == first.class_id and b.class_id == second.class_id


def test_another_class_cannot_extend_a_lineage_it_does_not_own(app):
    """Eligibility is read within the requesting class, so a foreign lineage looks
    empty; the derived cycle 1 then collides and fails closed as a conflict."""
    owner = initialize("chemistry_p1", app)
    intruder = initialize("ap_csp_p3", app)
    with app.app_context():
        _succeed(owner.class_id, "lineage:owned", "k:1", 1, _BEFORE_ANYTHING)
        db.session.commit()

        with pytest.raises(SuccessionConflictError):
            _succeed(intruder.class_id, "lineage:owned", "k:x", 1, _BEFORE_ANYTHING)
        assert _cycle_numbers(owner.class_id, "lineage:owned") == [1]
        assert _cycle_numbers(intruder.class_id, "lineage:owned") == []


# --------------------------------------------------------------------------- #
# Races (two real transactions)                                                #
# --------------------------------------------------------------------------- #


def _await_blocked_backend(app, timeout=15.0):
    """Wait until some backend is waiting on a lock another transaction holds."""
    deadline = time.monotonic() + timeout
    with app.app_context():
        with db.engine.connect() as conn:
            while time.monotonic() < deadline:
                waiting = conn.execute(sa.text(
                    "SELECT count(*) FROM pg_locks WHERE NOT granted"
                )).scalar()
                if waiting:
                    return True
                time.sleep(0.05)
    return False


def _race(app, class_id, internal_ref, key_a, key_b, reference):
    """Command A creates the successor and holds its transaction open until
    command B has evaluated the same lineage state and blocked behind A."""
    a_holding = threading.Event()
    release_a = threading.Event()
    outcomes = {}

    def request(key):
        return ScheduleNextBillCycleRequest(
            class_id=class_id, internal_ref=internal_ref,
            cycle_boundary_at=_boundary(2), next_assessment_at=_boundary(3),
            policy_uuid="policy-1", idempotency_key=key, reference_time_utc=reference,
        )

    def command_a():
        with app.app_context():
            try:
                with FEATContext("FEAT-OBL-002", idempotency_key=key_a):
                    outcomes["a"] = schedule_next_bill_cycle(request(key_a)).id
                    a_holding.set()
                    assert release_a.wait(timeout=20)
            except BaseException as exc:  # surfaced by the assertions below
                outcomes["a_error"] = exc
                a_holding.set()
            finally:
                db.session.remove()

    def command_b():
        with app.app_context():
            try:
                with FEATContext("FEAT-OBL-002", idempotency_key=key_b):
                    outcomes["b"] = schedule_next_bill_cycle(request(key_b)).id
            except BaseException as exc:
                outcomes["b_error"] = exc
            finally:
                db.session.remove()

    thread_a = threading.Thread(target=command_a)
    thread_a.start()
    assert a_holding.wait(timeout=20)
    assert "a_error" not in outcomes, outcomes.get("a_error")

    thread_b = threading.Thread(target=command_b)
    thread_b.start()
    blocked = _await_blocked_backend(app)
    release_a.set()
    thread_a.join(timeout=20)
    thread_b.join(timeout=20)
    assert blocked, "command B never blocked behind command A; the race was not exercised"
    return outcomes


@pytest.fixture
def due_lineage(app):
    """A lineage at cycle 1, with cycle 1 AND the would-be cycle 2 both due at the
    race's reference time, so falling forward to cycle 3 would be possible."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _succeed(classroom.class_id, "lineage:race", "setup:1", 1, _BEFORE_ANYTHING)
        db.session.commit()
    db.session.remove()
    return classroom.class_id, "lineage:race"


def test_distinct_commands_racing_for_one_successor_conflict_without_falling_forward(app, due_lineage):
    class_id, internal_ref = due_lineage
    outcomes = _race(app, class_id, internal_ref, "race:a", "race:b", _FAR_FUTURE)

    assert "a" in outcomes, outcomes
    assert isinstance(outcomes.get("b_error"), SuccessionConflictError), outcomes
    with app.app_context():
        # Cycle 2 is due at _FAR_FUTURE, so a loser that re-derived against the
        # advanced lineage would have created cycle 3.
        assert _cycle_numbers(class_id, internal_ref) == [1, 2]
        assert [r.idempotency_key for r in _reservations(class_id, internal_ref)] == [
            "setup:1", "race:a",
        ]


def test_same_command_racing_itself_is_a_replay_not_a_conflict(app, due_lineage):
    class_id, internal_ref = due_lineage
    outcomes = _race(app, class_id, internal_ref, "race:same", "race:same", _FAR_FUTURE)

    assert "a" in outcomes and "b" in outcomes, outcomes
    assert outcomes["a"] == outcomes["b"]
    with app.app_context():
        assert _cycle_numbers(class_id, internal_ref) == [1, 2]
        assert len(_reservations(class_id, internal_ref)) == 2
