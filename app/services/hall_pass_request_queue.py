"""Pending hall-pass request queue, shared by every application worker.

Pending hall-pass requests are operational workflow state, not canonical PROD
truth. Approval is the first durable PROD write, through FEAT-PROD-002
(DOM-PROD-001 §VIII.2 ``record_hall_pass_log``; MAP-UI-001 rows "Teacher views
hall-pass queue" and "Teacher approves or rejects pending hall-pass request").

The queue therefore stays non-durable — no table, no cookie — but it must be
visible to every gunicorn worker. Until 2026-10-01 it was a module-level dict,
which was correct only while production ran one worker: once a second worker
started, a request enqueued by one was invisible to the other, so the teacher's
page showed half the requests and Approve/Reject/Cancel answered "Pending
request not found." about half the time.

It now lives in Redis, following the pattern of the volatile student-setup
store (``app/services/student_setup.py``): a URL from app config or the
environment, one cached client per URL, short socket timeouts, a ``cth:``
key prefix, a fixed TTL that never slides, and a fail-closed error carrying no
connection details when the store is missing or unreachable. There is no
worker-local fallback, because a fallback is exactly the defect.

Layout — every key carries ``class_id``:

* ``cth:hall-pass-queue:{class_id}:request:{request_id}`` — one request, as
  JSON of the dataclass fields only (ids, destination, timestamp). No names.
* ``cth:hall-pass-queue:{class_id}:index`` — set of the class's request ids,
  so listing a class needs no key scan. A member whose request has expired is
  ignored on read and pruned by the next write to that class.

Lifetime: ``TTL_SECONDS`` (3 hours), fixed at enqueue and never extended. A
request can only be made while the student's work session is active, and every
active session is closed at the end of the class-local day (DOM-PROD-001 §XI.1
automatic transitions), so a request has no lawful meaning past that day. Three hours
outlasts the longest class block, so a teacher never loses a live request
mid-period, while yesterday's abandoned request never reappears.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from flask import current_app
from redis import Redis, RedisError

PREFIX = 'cth:hall-pass-queue:'
TTL_SECONDS = 3 * 60 * 60
# The index outlives its newest member by a margin, like the setup owner index.
INDEX_TTL_SECONDS = TTL_SECONDS + 60

# ``secrets.token_urlsafe(18)`` ids, with headroom. Anything else is not a
# request this queue issued, and is never turned into a key.
_REQUEST_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class HallPassQueueUnavailable(RuntimeError):
    """Deliberately carries no connection details or request values."""


@dataclass(frozen=True)
class PendingHallPassRequest:
    request_id: str
    class_id: str
    requested_by_seat_id: int
    destination: str
    requested_at_utc: object


@lru_cache(maxsize=4)
def _connection(url):
    return Redis.from_url(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)


def client():
    url = (
        current_app.config.get('HALL_PASS_QUEUE_REDIS_URL')
        or os.environ.get('HALL_PASS_QUEUE_REDIS_URL')
        or os.environ.get('REDIS_URL')
    )
    if not url:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.')
    try:
        return _connection(url)
    except (RedisError, ValueError):
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None


def _class_prefix(class_id: str) -> str:
    if not isinstance(class_id, str) or not class_id or ':' in class_id:
        raise ValueError('A pending hall-pass request requires a class_id.')
    return f'{PREFIX}{class_id}:'


def _index_key(class_id: str) -> str:
    return _class_prefix(class_id) + 'index'


def _request_key(class_id: str, request_id: str) -> str:
    return _class_prefix(class_id) + 'request:' + request_id


def _valid_request_id(request_id) -> bool:
    return isinstance(request_id, str) and bool(_REQUEST_ID.match(request_id))


def _encode(request: PendingHallPassRequest) -> str:
    requested_at = request.requested_at_utc
    if not isinstance(requested_at, datetime) or requested_at.tzinfo is None:
        raise ValueError('requested_at_utc must be a timezone-aware datetime.')
    return json.dumps({
        'request_id': request.request_id,
        'class_id': request.class_id,
        'requested_by_seat_id': int(request.requested_by_seat_id),
        'destination': request.destination,
        'requested_at_utc': requested_at.astimezone(timezone.utc).isoformat(),
    }, separators=(',', ':'))


def _decode(raw: str | None, class_id: str) -> PendingHallPassRequest | None:
    if not raw:
        return None
    record = json.loads(raw)
    if record.get('class_id') != class_id:
        return None
    return PendingHallPassRequest(
        request_id=record['request_id'],
        class_id=record['class_id'],
        requested_by_seat_id=int(record['requested_by_seat_id']),
        destination=record['destination'],
        requested_at_utc=datetime.fromisoformat(record['requested_at_utc']),
    )


def _store(request: PendingHallPassRequest, ttl_ms: int) -> None:
    conn = client()
    with conn.pipeline() as pipe:
        pipe.set(_request_key(request.class_id, request.request_id), _encode(request), px=ttl_ms)
        pipe.sadd(_index_key(request.class_id), request.request_id)
        pipe.expire(_index_key(request.class_id), INDEX_TTL_SECONDS)
        pipe.execute()


def enqueue_hall_pass_request(request: PendingHallPassRequest) -> PendingHallPassRequest:
    if not _valid_request_id(request.request_id):
        raise ValueError('Invalid hall-pass request id.')
    try:
        _store(request, TTL_SECONDS * 1000)
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
    return request


def get_pending_hall_pass_request(request_id: str, *, class_id: str) -> PendingHallPassRequest | None:
    if not _valid_request_id(request_id):
        return None
    try:
        raw = client().get(_request_key(class_id, request_id))
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
    return _decode(raw, class_id)


def _take(request_id: str, class_id: str):
    """Atomically remove one request; return (request, remaining_ttl_ms).

    GET, PTTL and DEL run in one MULTI/EXEC transaction, so of any number of
    workers or teachers racing for the same request exactly one receives it.
    """
    if not _valid_request_id(request_id):
        return None, 0
    key = _request_key(class_id, request_id)
    try:
        with client().pipeline() as pipe:  # transaction=True: MULTI ... EXEC
            pipe.get(key)
            pipe.pttl(key)
            pipe.delete(key)
            pipe.srem(_index_key(class_id), request_id)
            raw, ttl_ms, deleted, _ = pipe.execute()
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
    if not deleted:
        return None, 0
    return _decode(raw, class_id), ttl_ms


def pop_pending_hall_pass_request(request_id: str, *, class_id: str) -> PendingHallPassRequest | None:
    request, _ttl_ms = _take(request_id, class_id)
    return request


def claim_pending_hall_pass_request(request_id: str, *, class_id: str):
    """Take a request for resolution: ``(request, remaining_ttl_ms)``.

    The caller holds the only copy. On success it simply drops it; if the
    durable write fails it must hand it back with
    ``restore_pending_hall_pass_request`` so the request stays pending, as it
    did before claiming moved ahead of the write.
    """
    return _take(request_id, class_id)


def restore_pending_hall_pass_request(request: PendingHallPassRequest, ttl_ms: int) -> bool:
    """Put back a claimed request whose resolution failed, without extending it.

    The request regains only the lifetime it had when claimed. Returns False if
    that lifetime had already run out.
    """
    if not request or ttl_ms is None or ttl_ms <= 0:
        return False
    try:
        _store(request, int(ttl_ms))
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
    return True


def _class_requests(conn, class_id: str) -> list[tuple[str, PendingHallPassRequest | None]]:
    request_ids = sorted(conn.smembers(_index_key(class_id)))
    request_ids = [request_id for request_id in request_ids if _valid_request_id(request_id)]
    if not request_ids:
        return []
    raws = conn.mget([_request_key(class_id, request_id) for request_id in request_ids])
    return [
        (request_id, _decode(raw, class_id))
        for request_id, raw in zip(request_ids, raws)
    ]


def list_pending_hall_pass_requests_for_class(class_id: str) -> list[PendingHallPassRequest]:
    """Read-only: GET handlers call this, so it never prunes (INV-ARC-007)."""
    try:
        pairs = _class_requests(client(), class_id)
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
    requests = [request for _request_id, request in pairs if request is not None]
    return sorted(requests, key=lambda request: (request.requested_at_utc, request.request_id))


def clear_pending_hall_pass_requests_for_seat(*, class_id: str, seat_id: int) -> None:
    try:
        conn = client()
        pairs = _class_requests(conn, class_id)
        stale_ids = [
            request_id
            for request_id, request in pairs
            if request is None or request.requested_by_seat_id == seat_id
        ]
        if not stale_ids:
            return
        with conn.pipeline() as pipe:
            pipe.delete(*[_request_key(class_id, request_id) for request_id in stale_ids])
            pipe.srem(_index_key(class_id), *stale_ids)
            pipe.execute()
    except RedisError:
        raise HallPassQueueUnavailable('Hall-pass requests are temporarily unavailable.') from None
