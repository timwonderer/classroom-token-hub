"""Pending hall-pass requests are ``pending_actions`` rows, shared by every worker.

Live production defect, 2026-10-01: production moved from one gunicorn worker
to two, and pending hall-pass requests lived in a module-level dict in each
process. A request enqueued by one worker was invisible to the other, so the
teacher's page showed only its own worker's requests, and Approve, Reject and
the student's Cancel answered "Pending request not found." whenever they landed
on the other worker — about half the time.

Owner ruling 2026-10-01: a pending request is a ``pending_actions`` row
(DOM-STORE-001 §VII.B, §IX) — persisted, no TTL, deleted only by lawful
resolution (approve, reject, the student's cancel) or with its seat or class.

The cross-worker tests use a real second Python process: it imports the
application on its own, shares nothing in memory with the test process, and
reaches the same test database.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext
from app.models import HallPassLog, HallPassSettings, PendingAction, Seat
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_available_hall_pass_grant, grant_hall_passes
from app.services.hall_pass_request_queue import (
    AUTHORITATIVE_FEAT,
    KIND,
    HallPassRequestNotFound,
    get_pending_hall_pass_request,
    list_pending_hall_pass_requests_for_class,
)
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import (
    initialize,
    initialize_as_student,
    initialize_as_teacher,
)
from tests.helpers.hall_pass_requests import seed_pending_hall_pass_request

REPO = Path(__file__).resolve().parents[1]
REQUESTED_AT = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)

# The second worker: a separate interpreter that imports the app on its own and
# answers one JSON command per line. It shares only the database with this
# process.
_WORKER = r"""
import json, os, sys
from datetime import datetime
from app import app

print(json.dumps({'ready': os.getpid()}), flush=True)
for line in sys.stdin:
    cmd = json.loads(line)
    try:
        with app.app_context():
            from app.extensions import db
            from app.services import hall_pass_request_queue as q
            if cmd['op'] == 'list':
                out = {'ids': [r.request_id for r in q.list_pending_hall_pass_requests_for_class(cmd['class_id'])]}
            else:
                from app.feats import hall_pass_request_feat as f
                from app.services.context_resolver import CanonicalContext
                ctx = CanonicalContext(**cmd['ctx'])
                if cmd['op'] == 'submit':
                    r = f.submit_hall_pass_request(
                        ctx=ctx, destination=cmd['destination'],
                        requested_at_utc=datetime.fromisoformat(cmd['requested_at_utc']),
                        idempotency_key='worker2:submit:' + cmd['nonce'])
                    out = {'request_id': r.request_id}
                else:
                    action = {'approve': f.approve_hall_pass_request,
                              'reject': f.reject_hall_pass_request,
                              'cancel': f.cancel_hall_pass_request}[cmd['op']]
                    action(ctx=ctx, request_id=cmd['request_id'],
                           idempotency_key='worker2:' + cmd['op'] + ':' + cmd['request_id'])
                    out = {'ok': True}
            db.session.remove()
    except Exception as exc:
        out = {'error': type(exc).__name__ + ': ' + str(exc)}
    print(json.dumps(out), flush=True)
"""


def _ctx(user, class_id, seat, role) -> dict:
    return {"user_id": user.id, "class_id": class_id, "seat_id": seat.id, "actor_role": role}


class SecondWorker:
    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, "-c", _WORKER],
            cwd=str(REPO), env=dict(os.environ), text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self.pid = self._read()["ready"]

    def _read(self) -> dict:
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("second worker exited")
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)

    def call(self, **command) -> dict:
        self.process.stdin.write(json.dumps(command) + "\n")
        self.process.stdin.flush()
        return self._read()

    def list_ids(self, class_id) -> list[str]:
        result = self.call(op="list", class_id=class_id)
        assert "ids" in result, result
        return result["ids"]

    def submit(self, classroom, student) -> str:
        result = self.call(
            op="submit", ctx=_ctx(student.user, classroom.class_id, student.seat, "student"),
            destination="Bathroom", requested_at_utc=REQUESTED_AT.isoformat(), nonce=str(time.time_ns()),
        )
        assert "request_id" in result, result
        return result["request_id"]

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=20)


@pytest.fixture
def second_worker():
    worker = SecondWorker()
    assert worker.pid != os.getpid()
    yield worker
    worker.close()


def _seed_hall_pass_policy(class_id: str) -> None:
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"hall_pass_policy:{class_id}"):
        predecessor = (
            HallPassSettings.query
            .filter_by(class_id=class_id, availability_state="IN_USE")
            .first()
        )
        if predecessor is not None:
            predecessor.availability_state = "RETIRED"
            db.session.flush()
        db.session.add(HallPassSettings(
            class_id=class_id,
            max_queue_limit=10,
            pass_type_payload=[{"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}],
        ))
        db.session.flush()


def _grant(student, passes: int, tag: str = "grant") -> None:
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{tag}:{student.seat.id}"):
        grant_hall_passes(student.seat, passes, correlation_id=f"corr-{tag}-{student.seat.id}")


def _ready_class(classroom, *, passes: int = 1) -> None:
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _seed_hall_pass_policy(classroom.class_id)
    if passes:
        _grant(classroom.students[0], passes)


def _seed(classroom, student=None):
    student = student or classroom.students[0]
    return seed_pending_hall_pass_request(
        class_id=classroom.class_id, seat_id=student.seat.id, requested_at_utc=REQUESTED_AT,
    ).request_id


def _rows(class_id):
    db.session.expire_all()
    return PendingAction.query.filter_by(class_id=class_id, authoritative_feat=AUTHORITATIVE_FEAT).all()


# --------------------------------------------------------------------------
# Cross-worker visibility — the production defect
# --------------------------------------------------------------------------

def test_request_from_one_worker_is_listed_and_approved_by_another(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        _ready_class(classroom)

    request_id = second_worker.submit(classroom, student)

    page = client.get("/admin/hall-pass")
    assert page.status_code == 200
    assert request_id.encode() in page.data, "the teacher's page must list the other worker's request"

    response = client.post(f"/api/hall-pass/request/{request_id}/approve")
    assert response.status_code == 200, response.data
    assert response.get_json()["status"] == "success"

    with app.app_context():
        logs = HallPassLog.query.filter_by(class_id=classroom.class_id).all()
        assert [log.requested_by_seat_id for log in logs] == [student.seat.id]
        assert _rows(classroom.class_id) == []

    assert second_worker.list_ids(classroom.class_id) == [], "approval must remove it for every worker"


def test_request_from_one_worker_is_rejected_by_another(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)

    request_id = second_worker.submit(classroom, classroom.students[0])

    response = client.post(f"/api/hall-pass/request/{request_id}/reject")
    assert response.status_code == 200, response.data
    assert second_worker.list_ids(classroom.class_id) == []
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0


def test_request_resolved_by_one_worker_is_gone_for_the_other(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        request_id = _seed(classroom)

    assert second_worker.list_ids(classroom.class_id) == [request_id]
    teacher_ctx = _ctx(classroom.teacher_user, classroom.class_id, classroom.teacher_seat, "teacher")
    assert second_worker.call(op="reject", ctx=teacher_ctx, request_id=request_id) == {"ok": True}

    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 404
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0
        assert list_pending_hall_pass_requests_for_class(classroom.class_id) == []


def test_student_cancel_reaches_a_request_another_worker_enqueued(app, client, second_worker):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)

    request_id = second_worker.submit(classroom, student)

    response = client.post(f"/api/hall-pass/request/{request_id}/cancel")
    assert response.status_code == 200, response.data
    assert second_worker.list_ids(classroom.class_id) == []

    # A second cancel, from either worker, finds nothing.
    assert client.post(f"/api/hall-pass/request/{request_id}/cancel").status_code == 404


def test_student_cannot_cancel_another_students_request(app, client, second_worker):
    classroom, _student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        request_id = _seed(classroom, classroom.students[1])

    assert client.post(f"/api/hall-pass/request/{request_id}/cancel").status_code == 404
    assert second_worker.list_ids(classroom.class_id) == [request_id]


def test_pending_request_survives_a_worker_restart(app, client):
    """Persisted, no TTL: a worker that starts after the request still sees it."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        request_id = _seed(classroom)

    restarted = SecondWorker()
    try:
        assert restarted.list_ids(classroom.class_id) == [request_id]
    finally:
        restarted.close()
    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 200


# --------------------------------------------------------------------------
# Class isolation
# --------------------------------------------------------------------------

def test_requests_are_isolated_by_class(app, client):
    first = initialize("chemistry_p1", app)
    second = initialize_as_teacher("ap_csp_p3", client, app)
    with app.app_context():
        _ready_class(first)
        _ready_class(second)
        first_id = _seed(first)
        second_id = _seed(second)

        assert [r.request_id for r in list_pending_hall_pass_requests_for_class(first.class_id)] == [first_id]
        assert [r.request_id for r in list_pending_hall_pass_requests_for_class(second.class_id)] == [second_id]
        assert get_pending_hall_pass_request(first_id, class_id=second.class_id) is None

    # The second class's teacher can neither approve nor reject the first's request.
    assert client.post(f"/api/hall-pass/request/{first_id}/approve").status_code == 404
    assert client.post(f"/api/hall-pass/request/{first_id}/reject").status_code == 404
    assert client.post(f"/api/hall-pass/request/{second_id}/reject").status_code == 200

    with app.app_context():
        assert [r.request_id for r in list_pending_hall_pass_requests_for_class(first.class_id)] == [first_id]
        assert list_pending_hall_pass_requests_for_class(second.class_id) == []


# --------------------------------------------------------------------------
# Race safety
# --------------------------------------------------------------------------

def test_concurrent_approvals_in_two_sessions_issue_one_pass(app):
    """Two approvals of the same request, each in its own session and database
    connection. The first locks and deletes the row and then pauses inside its
    durable write; the second is observed blocked on that row lock; when the
    first commits, the second finds nothing. Two passes are available, so
    without the lock both would succeed."""
    import app.feats.prod as prod
    from app.feats.hall_pass_request_feat import approve_hall_pass_request

    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _ready_class(classroom, passes=2)
        request_id = _seed(classroom)
    teacher_ctx = CanonicalContext(**_ctx(classroom.teacher_user, classroom.class_id, classroom.teacher_seat, "teacher"))

    first_inside_write = threading.Event()
    release_first = threading.Event()
    real_record = prod._record_hall_pass_log_impl

    def paused_record(**kwargs):
        if threading.current_thread().name == "approve-1":
            first_inside_write.set()
            assert release_first.wait(30)
        return real_record(**kwargs)

    results: dict[str, object] = {}

    def approve(name):
        with app.app_context():
            try:
                approve_hall_pass_request(
                    ctx=teacher_ctx, request_id=request_id,
                    idempotency_key=f"hall_pass_approve:{classroom.class_id}:{request_id}",
                )
                results[name] = "issued"
            except HallPassRequestNotFound:
                results[name] = "not_found"
            except Exception as exc:  # surfaced in the assertion below
                results[name] = repr(exc)
            finally:
                db.session.remove()

    prod._record_hall_pass_log_impl = paused_record
    try:
        first = threading.Thread(target=approve, args=("approve-1",), name="approve-1")
        first.start()
        assert first_inside_write.wait(30)

        second = threading.Thread(target=approve, args=("approve-2",), name="approve-2")
        second.start()
        with app.app_context():
            waiting = 0
            for _ in range(300):
                waiting = db.session.execute(text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND query ILIKE '%pending_actions%'"
                )).scalar()
                db.session.rollback()
                if waiting:
                    break
                time.sleep(0.05)
            db.session.remove()
        assert waiting == 1, "the second approval must be blocked on the first one's row lock"
        assert "approve-2" not in results

        release_first.set()
        first.join(30)
        second.join(30)
    finally:
        release_first.set()
        prod._record_hall_pass_log_impl = real_record

    assert results == {"approve-1": "issued", "approve-2": "not_found"}
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 1
        assert _rows(classroom.class_id) == []
        # One of the two passes is still available.
        assert get_available_hall_pass_grant(classroom.students[0].seat.id, classroom.class_id) is not None


def test_second_approval_after_the_first_is_not_found(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom, passes=2)
        request_id = _seed(classroom)

    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 200
    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 404
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 1


def test_refused_approval_leaves_the_request_pending(app, client):
    """DOM-STORE-001 §VII.B: a failed resolution leaves the pending action intact."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom, passes=0)
        request_id = _seed(classroom)
        submitted_at = _rows(classroom.class_id)[0].submitted_at

    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 400

    with app.app_context():
        rows = _rows(classroom.class_id)
        assert [row.pending_action_id for row in rows] == [request_id]
        assert rows[0].submitted_at == submitted_at
        _grant(classroom.students[0], 1, tag="late-grant")

    assert client.post(f"/api/hall-pass/request/{request_id}/approve").status_code == 200


# --------------------------------------------------------------------------
# The row
# --------------------------------------------------------------------------

def test_submission_writes_a_typed_pending_action_and_replaces_the_seats_earlier_one(app):
    from app.feats.hall_pass_request_feat import submit_hall_pass_request

    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with app.app_context():
        _ready_class(classroom)
        ctx = CanonicalContext(**_ctx(student.user, classroom.class_id, student.seat, "student"))
        earlier = submit_hall_pass_request(
            ctx=ctx, destination="Bathroom", requested_at_utc=REQUESTED_AT, idempotency_key="t:submit:1",
        )
        later_at = datetime(2026, 10, 1, 15, 35, tzinfo=timezone.utc)
        later = submit_hall_pass_request(
            ctx=ctx, destination="Bathroom", requested_at_utc=later_at, idempotency_key="t:submit:2",
        )

        rows = _rows(classroom.class_id)
        assert [row.pending_action_id for row in rows] == [later.request_id] != [earlier.request_id]
        row = rows[0]
        assert row.seat_id == student.seat.id
        assert row.authoritative_feat == "FEAT-PROD-002"
        assert row.payload == {"kind": KIND, "requested_by_seat_id": student.seat.id, "destination": "Bathroom"}
        assert row.correlation_id == f"{KIND}:{classroom.class_id}:{later.request_id}"
        assert row.entitlement_id == get_available_hall_pass_grant(student.seat.id, classroom.class_id).entitlement_id
        assert row.submitted_at == later_at
        assert student.first_name not in json.dumps(row.payload)

        stored = get_pending_hall_pass_request(later.request_id, class_id=classroom.class_id)
        assert stored.requested_at_utc == later_at and stored.requested_at_utc.tzinfo is not None


def test_reading_the_queue_writes_nothing(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        request_id = _seed(classroom)

    for path in ("/admin/hall-pass", "/admin/"):
        assert client.get(path).status_code == 200
    with app.app_context():
        assert [row.pending_action_id for row in _rows(classroom.class_id)] == [request_id]


# --------------------------------------------------------------------------
# Membership by existence (INV-ARC-013)
# --------------------------------------------------------------------------

def test_removing_a_student_with_a_pending_request_removes_the_request(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        request_id = _seed(classroom)
        seat_id = classroom.students[0].seat.id

    response = client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": [seat_id], **valid_destruction_gate("DELETE STUDENTS")},
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    with app.app_context():
        db.session.expire_all()
        assert db.session.get(Seat, seat_id) is None
        assert db.session.get(PendingAction, request_id) is None
