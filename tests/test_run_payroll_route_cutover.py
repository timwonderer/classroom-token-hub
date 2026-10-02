"""Slice 8.3e — manual /run_payroll route cutover to FEAT-PROD-004.

Proves that a real HTTP manual-payroll invocation drives the entire canonical
economic-cycle lifecycle through FEAT-PROD-004 (the route no longer owns a
per-seat loop), and that replaying the same manual command reproduces none of it.

    POST /admin/run_payroll
        → PayrollEvent rows (stamped with the run's payroll_cycle_id)
        → one interpretation_cycle_record
        → payroll_cycle_completion anchor
"""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    InterpretationCycleRecord,
    PayrollEvent,
)
from app.services.payroll.cycle_completion import resolve_completed_run
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize_as_teacher


def _seed(classroom):
    """Closed attendance for one seat."""
    cid = classroom.class_id
    student = classroom.students[0]
    now = utc_now()
    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid,
            actor_seat_id=classroom.teacher_seat_id, reason_code="start_work",
            timestamp=now - timedelta(minutes=30),
        ))
        # Closed: payroll settles finished sessions only (DOM-PROD-001 §VI.3).
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid,
            actor_seat_id=classroom.teacher_seat_id, status="inactive",
            reason_code="done_for_day", timestamp=now - timedelta(minutes=10),
        ))
        db.session.flush()
    return cid


def test_manual_run_payroll_drives_full_lifecycle_and_replay_is_inert(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = _seed(classroom)
    token = "tok-http-1"

    response = client.post("/admin/run_payroll", data={"idempotency_token": token})
    assert response.status_code in (200, 302), response.data
    assert b"Database error" not in response.data

    # The manual command produced a resolvable completed run.
    key = f"manual-payroll:{cid}:{token}"
    cycle_id = resolve_completed_run(cid, key)
    assert cycle_id is not None

    # PROD: payroll events stamped with the run's cycle id.
    events = PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id, payroll_event_type="payroll"
    ).all()
    assert len(events) >= 1

    # ITR: exactly one immutable, complete record bound to the cycle.
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle_id).one()
    assert record.observations_json["coverage"]["complete"] is True

    # --- Replay the SAME manual command: it must reproduce nothing. ---
    events_before = PayrollEvent.query.filter_by(class_id=cid).count()

    replay = client.post("/admin/run_payroll", data={"idempotency_token": token})
    assert replay.status_code in (200, 302), replay.data

    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_before
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1
    # Still resolves to the original cycle id — no second cycle allocated.
    assert resolve_completed_run(cid, key) == cycle_id
