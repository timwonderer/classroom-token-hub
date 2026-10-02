"""Pending hall-pass requests are shared by every gunicorn worker.

Live production defect, 2026-10-01: production moved from one gunicorn worker
to two, and pending hall-pass requests lived in a module-level dict in each
process. A request enqueued by one worker was invisible to the other, so the
teacher's page showed only its own worker's requests, and Approve, Reject and
the student's Cancel answered "Pending request not found." whenever they landed
on the other worker — about half the time.

The queue now lives in Redis (``app/services/hall_pass_request_queue.py``).
The headline tests here use a real second Python process as the second worker:
it imports the application separately, so it shares nothing in memory with the
test process, and it reaches the same isolated Redis the conftest started.

Each test below failed against main before the fix (recorded in the PR).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import HallPassLog, HallPassSettings
from app.services import hall_pass_request_queue as queue
from app.services.entitlement_service import grant_hall_passes
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    enqueue_hall_pass_request,
    get_pending_hall_pass_request,
    list_pending_hall_pass_requests_for_class,
    pop_pending_hall_pass_request,
)
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import (
    initialize,
    initialize_as_student,
    initialize_as_teacher,
)

REPO = Path(__file__).resolve().parents[1]
REQUESTED_AT = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)

# The second worker: a separate interpreter that imports the app on its own and
# answers one JSON command per line. Nothing in it is shared with this process
# except the Redis URL it is handed.
_WORKER = r"""
import json, os, sys
from datetime import datetime
from app import app
from app.services import hall_pass_request_queue as q

app.config['HALL_PASS_QUEUE_REDIS_URL'] = os.environ['HPQ_TEST_REDIS_URL']
print(json.dumps({'ready': os.getpid()}), flush=True)
for line in sys.stdin:
    cmd = json.loads(line)
    try:
        with app.app_context():
            if cmd['op'] == 'enqueue':
                q.enqueue_hall_pass_request(q.PendingHallPassRequest(
                    request_id=cmd['request_id'],
                    class_id=cmd['class_id'],
                    requested_by_seat_id=cmd['seat_id'],
                    destination=cmd['destination'],
                    requested_at_utc=datetime.fromisoformat(cmd['requested_at_utc']),
                ))
                out = {'ok': True}
            elif cmd['op'] == 'list':
                out = {'ids': [r.request_id for r in q.list_pending_hall_pass_requests_for_class(cmd['class_id'])]}
            elif cmd['op'] == 'pop':
                popped = q.pop_pending_hall_pass_request(cmd['request_id'], class_id=cmd['class_id'])
                out = {'popped': popped is not None}
            else:
                out = {'error': 'unknown op'}
    except Exception as exc:
        out = {'error': repr(exc)}
    print(json.dumps(out), flush=True)
"""


class SecondWorker:
    def __init__(self, url: str):
        env = dict(os.environ, HPQ_TEST_REDIS_URL=url)
        self.process = subprocess.Popen(
            [sys.executable, "-c", _WORKER],
            cwd=str(REPO), env=env, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        ready = self._read()
        self.pid = ready["ready"]

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

    def enqueue(self, *, request_id, class_id, seat_id, destination="Bathroom"):
        result = self.call(
            op="enqueue", request_id=request_id, class_id=class_id, seat_id=seat_id,
            destination=destination, requested_at_utc=REQUESTED_AT.isoformat(),
        )
        assert result == {"ok": True}, result

    def list_ids(self, class_id) -> list[str]:
        result = self.call(op="list", class_id=class_id)
        assert "ids" in result, result
        return result["ids"]

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)


@pytest.fixture(scope="module")
def second_worker(hall_pass_request_queue_store):
    # Start the isolated server from this process before the worker connects.
    queue._connection(hall_pass_request_queue_store).ping()
    worker = SecondWorker(hall_pass_request_queue_store)
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


def _ready_class(classroom, *, passes: int = 1) -> None:
    student = classroom.students[0]
    enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
    _seed_hall_pass_policy(classroom.class_id)
    if passes:
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
            grant_hall_passes(student.seat, passes, correlation_id=f"corr-grant-{student.seat.id}")


def _request(classroom, request_id, *, seat_id=None, at=REQUESTED_AT):
    return PendingHallPassRequest(
        request_id=request_id,
        class_id=classroom.class_id,
        requested_by_seat_id=seat_id or classroom.students[0].seat.id,
        destination="Bathroom",
        requested_at_utc=at,
    )


# --------------------------------------------------------------------------
# Cross-worker visibility — the production defect
# --------------------------------------------------------------------------

def test_request_from_one_worker_is_listed_and_approved_by_another(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with app.app_context():
        _ready_class(classroom)

    second_worker.enqueue(request_id="req-xworker", class_id=classroom.class_id, seat_id=student.seat.id)

    page = client.get("/admin/hall-pass")
    assert page.status_code == 200
    assert b"req-xworker" in page.data, "the teacher's page must list the other worker's request"

    response = client.post("/api/hall-pass/request/req-xworker/approve")
    assert response.status_code == 200, response.data
    assert response.get_json()["status"] == "success"

    with app.app_context():
        logs = HallPassLog.query.filter_by(class_id=classroom.class_id).all()
        assert [log.requested_by_seat_id for log in logs] == [student.seat.id]

    assert second_worker.list_ids(classroom.class_id) == [], "approval must remove it for every worker"


def test_request_from_one_worker_is_rejected_by_another(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)

    second_worker.enqueue(request_id="req-xreject", class_id=classroom.class_id,
                          seat_id=classroom.students[0].seat.id)

    response = client.post("/api/hall-pass/request/req-xreject/reject")
    assert response.status_code == 200, response.data
    assert second_worker.list_ids(classroom.class_id) == []
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0


def test_request_removed_by_one_worker_is_gone_for_the_other(app, client, second_worker):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        enqueue_hall_pass_request(_request(classroom, "req-popped-elsewhere"))

    assert second_worker.list_ids(classroom.class_id) == ["req-popped-elsewhere"]
    assert second_worker.call(op="pop", request_id="req-popped-elsewhere",
                              class_id=classroom.class_id) == {"popped": True}

    response = client.post("/api/hall-pass/request/req-popped-elsewhere/approve")
    assert response.status_code == 404
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0


def test_student_cancel_reaches_a_request_another_worker_enqueued(app, client, second_worker):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    second_worker.enqueue(request_id="req-cancel", class_id=classroom.class_id, seat_id=student.seat.id)

    response = client.post("/api/hall-pass/request/req-cancel/cancel")
    assert response.status_code == 200, response.data
    assert second_worker.list_ids(classroom.class_id) == []

    # A second cancel, from either worker, finds nothing.
    assert client.post("/api/hall-pass/request/req-cancel/cancel").status_code == 404


def test_student_cannot_cancel_another_students_request(app, client, second_worker):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    other_seat_id = classroom.students[1].seat.id

    second_worker.enqueue(request_id="req-not-mine", class_id=classroom.class_id, seat_id=other_seat_id)

    assert client.post("/api/hall-pass/request/req-not-mine/cancel").status_code == 404
    assert second_worker.list_ids(classroom.class_id) == ["req-not-mine"]


# --------------------------------------------------------------------------
# Class isolation
# --------------------------------------------------------------------------

def test_requests_are_isolated_by_class_even_with_the_same_request_id(app, client):
    """Every key carries class_id: one class can neither see nor resolve another's."""
    first = initialize("chemistry_p1", app)
    second = initialize_as_teacher("ap_csp_p3", client, app)
    with app.app_context():
        _ready_class(first)
        _ready_class(second)
        enqueue_hall_pass_request(_request(first, "req-shared"))
        enqueue_hall_pass_request(_request(second, "req-shared"))
        enqueue_hall_pass_request(_request(first, "req-first-only"))

        first_ids = [(r.request_id, r.requested_by_seat_id)
                     for r in list_pending_hall_pass_requests_for_class(first.class_id)]
        second_ids = [(r.request_id, r.requested_by_seat_id)
                      for r in list_pending_hall_pass_requests_for_class(second.class_id)]
        assert sorted(first_ids) == sorted([
            ("req-first-only", first.students[0].seat.id),
            ("req-shared", first.students[0].seat.id),
        ])
        assert second_ids == [("req-shared", second.students[0].seat.id)]
        assert get_pending_hall_pass_request("req-first-only", class_id=second.class_id) is None

    # The second class's teacher cannot reach the first class's request ...
    assert client.post("/api/hall-pass/request/req-first-only/approve").status_code == 404
    # ... and rejecting the shared id touches only their own class.
    assert client.post("/api/hall-pass/request/req-shared/reject").status_code == 200

    with app.app_context():
        assert {r.request_id for r in list_pending_hall_pass_requests_for_class(first.class_id)} == {
            "req-first-only", "req-shared",
        }
        assert list_pending_hall_pass_requests_for_class(second.class_id) == []

        # Every key the queue writes is namespaced by the class it belongs to.
        keys = list(queue.client().scan_iter(match=queue.PREFIX + "*"))
        mine = [key for key in keys if first.class_id in key or second.class_id in key]
        # The first class's two requests and index; the second class's request
        # was rejected, and Redis drops its emptied index.
        assert len(mine) == 3
        for key in keys:
            scope = key[len(queue.PREFIX):].split(":", 1)[0]
            assert len(str(uuid.UUID(scope))) == 36, key


# --------------------------------------------------------------------------
# Lifetime
# --------------------------------------------------------------------------

def test_pending_request_expires_after_its_fixed_ttl(app, client, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom)
        assert queue.TTL_SECONDS == 3 * 60 * 60

        enqueue_hall_pass_request(_request(classroom, "req-ttl-default"))
        key = queue._request_key(classroom.class_id, "req-ttl-default")
        initial = queue.client().pttl(key)
        assert 0 < initial <= queue.TTL_SECONDS * 1000
        # Reading never extends it.
        get_pending_hall_pass_request("req-ttl-default", class_id=classroom.class_id)
        list_pending_hall_pass_requests_for_class(classroom.class_id)
        assert queue.client().pttl(key) <= initial

        monkeypatch.setattr(queue, "TTL_SECONDS", 1)
        enqueue_hall_pass_request(_request(classroom, "req-ttl-short"))
        time.sleep(1.3)
        assert get_pending_hall_pass_request("req-ttl-short", class_id=classroom.class_id) is None
        assert [r.request_id for r in list_pending_hall_pass_requests_for_class(classroom.class_id)] == [
            "req-ttl-default",
        ]

    assert client.post("/api/hall-pass/request/req-ttl-short/approve").status_code == 404


# --------------------------------------------------------------------------
# Race safety
# --------------------------------------------------------------------------

def test_concurrent_pops_yield_the_request_exactly_once(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        enqueue_hall_pass_request(_request(classroom, "req-race"))

    def take(_):
        with app.app_context():
            return pop_pending_hall_pass_request("req-race", class_id=classroom.class_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(take, range(8)))
    assert sum(result is not None for result in results) == 1


def test_double_approve_writes_one_hall_pass_log(app, client, monkeypatch):
    """The request is claimed before the durable write, so a second approval —
    from another teacher, tab or worker — cannot reach FEAT-PROD-002 at all.

    The FEAT's idempotency key is not a deduplication guard (nothing refuses a
    second write with the same key), so with two passes available the old
    get-then-write-then-pop order let two approvals write two logs and spend
    two passes.
    """
    from app.routes import api as api_routes

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom, passes=2)
        enqueue_hall_pass_request(_request(classroom, "req-double"))

    seen_during_write = []
    real_record = api_routes.record_hall_pass_log

    def record_and_look(**kwargs):
        # Another worker looking while this approval writes must find nothing.
        seen_during_write.append([
            request.request_id
            for request in list_pending_hall_pass_requests_for_class(classroom.class_id)
        ])
        return real_record(**kwargs)

    monkeypatch.setattr(api_routes, "record_hall_pass_log", record_and_look)

    first = client.post("/api/hall-pass/request/req-double/approve")
    second = client.post("/api/hall-pass/request/req-double/approve")

    assert first.status_code == 200, first.data
    assert second.status_code == 404
    assert seen_during_write == [[]]
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 1


def test_refused_approval_leaves_the_request_pending_without_extending_it(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _ready_class(classroom, passes=0)
        enqueue_hall_pass_request(_request(classroom, "req-no-pass"))
        key = queue._request_key(classroom.class_id, "req-no-pass")
        before = queue.client().pttl(key)

    refused = client.post("/api/hall-pass/request/req-no-pass/approve")
    assert refused.status_code == 400

    with app.app_context():
        restored = get_pending_hall_pass_request("req-no-pass", class_id=classroom.class_id)
        assert restored == _request(classroom, "req-no-pass")
        assert 0 < queue.client().pttl(key) <= before
        student = classroom.students[0]
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant-late:{student.seat.id}"):
            grant_hall_passes(student.seat, 1, correlation_id=f"corr-late-{student.seat.id}")

    assert client.post("/api/hall-pass/request/req-no-pass/approve").status_code == 200


# --------------------------------------------------------------------------
# Stored value
# --------------------------------------------------------------------------

def test_stored_value_is_minimal_and_time_round_trips_aware(app):
    classroom = initialize("chemistry_p1", app)
    pacific = timezone(timedelta(hours=-7))
    requested_at = datetime(2026, 10, 1, 8, 45, 12, 345678, tzinfo=pacific)
    with app.app_context():
        enqueue_hall_pass_request(_request(classroom, "req-shape", at=requested_at))

        stored = get_pending_hall_pass_request("req-shape", class_id=classroom.class_id)
        assert stored.requested_at_utc == requested_at
        assert stored.requested_at_utc.tzinfo is not None
        assert stored.requested_at_utc.utcoffset() == timedelta(0)

        raw = json.loads(queue.client().get(queue._request_key(classroom.class_id, "req-shape")))
        assert set(raw) == {"request_id", "class_id", "requested_by_seat_id", "destination", "requested_at_utc"}
        student = classroom.students[0]
        assert student.first_name not in json.dumps(raw)
        assert student.last_name not in json.dumps(raw)

        with pytest.raises(ValueError):
            enqueue_hall_pass_request(_request(classroom, "req-naive", at=datetime(2026, 10, 1, 8, 45)))
