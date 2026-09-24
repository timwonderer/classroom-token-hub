"""Interim insurance genesis and bill-cycle termination (DOM-OBL-001 §V.7).

DOM-OBL-001 v3.1 has two bill-cycle operations, succession and termination.
Succession (``schedule_next_bill_cycle``) is held by
tests/dom/obligations/test_bill_cycle_succession.py.

``establish_bill_cycle`` survives only as insurance purchase's interim genesis
path, until the insurance lineage migrates to succession. These tests keep that
interim command honest while it exists: it produces cycle 1 and refuses to run
twice for one lineage. Termination, the second operation, appends a terminal row.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import BillCycle
from app.services import obligations_service
from app.services.obligations_service import BillCycleLifecycleError
from app.feats.establish_bill_cycle_feat import execute_establish_bill_cycle
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _boundaries(offset_days=0):
    now = utc_now()
    cycle_boundary_at = now + timedelta(days=30 + offset_days)
    next_assessment_at = now + timedelta(days=60 + offset_days)
    return cycle_boundary_at, next_assessment_at


# --------------------------------------------------------------------------- #
# Genesis                                                                      #
# --------------------------------------------------------------------------- #


def test_genesis_establishes_cycle_1(app):
    """establish_bill_cycle creates cycle 1 for a fresh lineage."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        cycle = execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-1:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
        )
        db.session.commit()
        assert cycle.cycle_number == 1
        assert cycle.internal_ref == "insurance:seat-1:policy-x"


def test_second_genesis_fails_regardless_of_idempotency(app):
    """A second genesis for the same lineage fails even as a fresh invocation.

    Each call to execute_establish_bill_cycle opens its own FEAT context (a
    distinct invocation with its own implicit idempotency scope). The genesis
    invariant is enforced against authoritative Obligations state, so the second
    attempt raises rather than manufacturing another cycle 1.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-1:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
        )
        db.session.commit()

        with pytest.raises(BillCycleLifecycleError, match="no prior cycle"):
            execute_establish_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="insurance:seat-1:policy-x",
                cycle_boundary_at=cb,
                next_assessment_at=na,
            )

        # Still exactly one cycle for the lineage.
        cycles = obligations_service.get_bill_cycles_for_internal_ref(
            "insurance:seat-1:policy-x"
        )
        assert [c.cycle_number for c in cycles] == [1]


def test_genesis_rejects_bad_temporal_ordering(app):
    """next_assessment_at must be after cycle_boundary_at."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        now = utc_now()
        with pytest.raises(ValueError, match="next_assessment_at"):
            execute_establish_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="insurance:seat-2:policy-x",
                cycle_boundary_at=now + timedelta(days=60),
                next_assessment_at=now + timedelta(days=30),  # before boundary
            )


# --------------------------------------------------------------------------- #
# Termination (insurance cancellation stops recurrence)                       #
# --------------------------------------------------------------------------- #

from app.feats.terminate_bill_cycle_feat import execute_terminate_bill_cycle  # noqa: E402


def test_terminate_appends_terminal_cycle_with_null_next_assessment(app):
    """Termination appends cycle N+1 with next_assessment_at = NULL (DOM-OBL-001
    §160/§241) — no further recurrence — carrying the coverage boundary forward."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-t1:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
            policy_uuid="policy-x",
        )
        db.session.commit()

        terminal = execute_terminate_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-t1:policy-x",
        )
        db.session.commit()

        assert terminal.cycle_number == 2
        assert terminal.next_assessment_at is None  # terminal — recurrence stopped
        # Coverage runs through the last paid period's end = prior next_assessment_at.
        assert terminal.cycle_boundary_at == na
        assert terminal.policy_uuid == "policy-x"  # identity carried forward
        # latest is now terminal
        latest = obligations_service.get_latest_bill_cycle(
            "insurance:seat-t1:policy-x"
        )
        assert latest.next_assessment_at is None


def test_terminate_is_idempotent_no_second_terminal_row(app):
    """Terminating an already-terminal lineage is a safe no-op (no second row)."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-t2:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
        )
        db.session.commit()

        first = execute_terminate_bill_cycle(
            class_id=classroom.class_id, internal_ref="insurance:seat-t2:policy-x"
        )
        db.session.commit()
        second = execute_terminate_bill_cycle(
            class_id=classroom.class_id, internal_ref="insurance:seat-t2:policy-x"
        )
        db.session.commit()

        assert first.id == second.id  # same terminal row returned
        cycles = obligations_service.get_bill_cycles_for_internal_ref(
            "insurance:seat-t2:policy-x"
        )
        assert [c.cycle_number for c in cycles] == [1, 2]  # not [1, 2, 3]


def test_terminate_requires_existing_lineage(app):
    """Terminating a lineage that was never established fails closed."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        with pytest.raises(BillCycleLifecycleError, match="nothing to terminate"):
            execute_terminate_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="insurance:seat-nope:policy-x",
            )


def test_terminate_rejects_class_scope_mismatch(app):
    """A lineage in another class cannot be terminated under a mismatched class_id."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-t3:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
        )
        db.session.commit()
        with pytest.raises(BillCycleLifecycleError, match="class scope mismatch"):
            execute_terminate_bill_cycle(
                class_id="some-other-class-id",
                internal_ref="insurance:seat-t3:policy-x",
            )


def test_terminate_does_not_rewrite_prior_cycles(app):
    """Prior cycles remain immutable after termination (DOM-OBL-001 §IX.7)."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        cb, na = _boundaries()
        genesis = execute_establish_bill_cycle(
            class_id=classroom.class_id,
            internal_ref="insurance:seat-t4:policy-x",
            cycle_boundary_at=cb,
            next_assessment_at=na,
        )
        db.session.commit()
        genesis_next = genesis.next_assessment_at

        execute_terminate_bill_cycle(
            class_id=classroom.class_id, internal_ref="insurance:seat-t4:policy-x"
        )
        db.session.commit()

        cycle1 = next(
            c for c in obligations_service.get_bill_cycles_for_internal_ref(
                "insurance:seat-t4:policy-x"
            ) if c.cycle_number == 1
        )
        assert cycle1.next_assessment_at == genesis_next  # unchanged
