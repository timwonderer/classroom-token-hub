"""Volatile student setup state (FEAT-IDEN-002 / SPEC-IDEN-001).

Only the opaque capability is kept in the browser. Redis is a dedicated,
non-persistent instance shared by all workers. No database or cookie fallback.
Username values use the approved Fernet facility even inside this volatile store.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from functools import lru_cache

from flask import current_app
from redis import Redis, RedisError, WatchError

from app.hash_utils import hash_username_lookup
from app.utils.encryption import _get_fernet

PREFIX = 'cth:student-setup:'
TTL_SECONDS = 1800


class SetupUnavailable(RuntimeError):
    """Deliberately carries no connection details or submitted values."""


class SetupExpired(ValueError):
    pass


@lru_cache(maxsize=4)
def _connection(url):
    return Redis.from_url(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)


def client():
    url = current_app.config.get('STUDENT_SETUP_REDIS_URL') or os.environ.get('STUDENT_SETUP_REDIS_URL')
    if not url:
        raise SetupUnavailable('Temporary setup storage is unavailable.')
    try:
        conn = _connection(url)
        config = conn.config_get('save', 'appendonly', 'slowlog-log-slower-than')
        replication = conn.info('replication')
        persistence = conn.info('persistence')
        if (config.get('save') != '' or config.get('appendonly') != 'no'
                or str(config.get('slowlog-log-slower-than')) != '-1'
                or replication.get('role') != 'master'
                or replication.get('connected_slaves') != 0
                or persistence.get('rdb_bgsave_in_progress') != 0
                or persistence.get('aof_enabled') != 0):
            raise SetupUnavailable('Temporary setup storage is not memory-only.')
        return conn
    except RedisError:
        raise SetupUnavailable('Temporary setup storage is unavailable.') from None


def scope(seat, user, *, recovery_authorization=None):
    if user is not None:
        owner = f'user:{user.id}'
        values = [owner, recovery_authorization]
    else:
        owner = f'seat:{seat.id}'
        values = [owner, seat.class_id, seat.claim_generation]
    digest = hmac.new(current_app.secret_key.encode(),
                      json.dumps(values, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    return owner, digest


def _key(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        raise SetupExpired('Setup expired. Please start again.')
    return PREFIX + hashlib.sha256(token.encode()).hexdigest()


def begin(owner, binding, ttl=TTL_SECONDS):
    conn = client()
    token = secrets.token_urlsafe(32)
    key = _key(token)
    record = dict(owner=owner, scope=binding, generation=secrets.token_urlsafe(16),
                  username=None, verified_page=None, attempts=0, collision=False,
                  completing=False)
    try:
        with conn.pipeline() as pipe:
            pipe.set(key, json.dumps(record), ex=max(1, min(TTL_SECONDS, int(ttl))))
            pipe.sadd(PREFIX + 'owner:' + owner, key)
            pipe.expire(PREFIX + 'owner:' + owner, TTL_SECONDS + 60)
            pipe.execute()
    except RedisError:
        raise SetupUnavailable('Temporary setup storage is unavailable.') from None
    return token


def discard(token):
    if not token:
        return
    try:
        client().delete(_key(token))
    except SetupExpired:
        return
    except RedisError:
        raise SetupUnavailable('Temporary setup storage is unavailable.') from None


def forget_owner(owner):
    """Erase volatile identity material before destructive lifecycle mutation.

    A rollback may require repeating setup; it must never preserve a deleted
    identity's username. Callers already hold the owning identity/seat locks.
    """
    conn = client()
    index = PREFIX + 'owner:' + owner
    try:
        keys = conn.smembers(index)
        conn.delete(index, *keys)
    except RedisError:
        raise SetupUnavailable('Temporary setup storage is unavailable.') from None


def read(token, binding):
    try:
        raw = client().get(_key(token))
        record = json.loads(raw) if raw else None
        if not record or not hmac.compare_digest(record['scope'], binding):
            raise SetupExpired('Setup expired. Please start again.')
        return record
    except RedisError:
        raise SetupUnavailable('Temporary setup storage is unavailable.') from None


def username(record):
    encrypted = record.get('username')
    return _get_fernet().decrypt(encrypted.encode()).decode() if encrypted else None


def _change(token, binding, operation):
    conn = client()
    key = _key(token)
    for _ in range(8):
        try:
            with conn.pipeline() as pipe:
                pipe.watch(key)
                raw = pipe.get(key)
                record = json.loads(raw) if raw else None
                if not record or not hmac.compare_digest(record['scope'], binding):
                    raise SetupExpired('Setup expired. Please start again.')
                result = operation(record)
                pipe.multi()
                # No sliding expiry, including retries, verification and collisions.
                pipe.set(key, json.dumps(record), keepttl=True, xx=True)
                if not pipe.execute()[0]:
                    raise SetupExpired('Setup expired. Please start again.')
                return result
        except WatchError:
            continue
        except RedisError:
            raise SetupUnavailable('Temporary setup storage is unavailable.') from None
    raise SetupUnavailable('Setup is busy. Please try again.')


def generate(token, binding, builder):
    def update(record):
        if record['completing']:
            raise SetupExpired('Setup is being completed.')
        if record['username'] and not record['collision']:
            return
        value = builder()
        record.update(username=_get_fernet().encrypt(value.encode()).decode(),
                      generation=secrets.token_urlsafe(16), verified_page=None,
                      attempts=0, collision=False)
    _change(token, binding, update)


def verify(token, binding, page_token, typed):
    if not isinstance(page_token, str) or not 20 <= len(page_token) <= 128:
        raise SetupExpired('The setup page expired. Please reload it.')
    def update(record):
        if not record['username'] or record['completing'] or record['collision']:
            raise SetupExpired('Setup expired. Please start again.')
        matched = hmac.compare_digest(hash_username_lookup(typed), hash_username_lookup(username(record)))
        record['attempts'] += 1
        record['verified_page'] = page_token if matched else None
        return matched, record['attempts']
    return _change(token, binding, update)


def take_verified(token, binding, page_token):
    """Atomically consume the proof and erase the username before activation.

    A tombstone prevents duplicate completions. On a refused database mutation,
    restore may put the same value back only while this exact attempt still lives.
    """
    def update(record):
        if (not record['username'] or record['completing'] or not page_token
                or not record['verified_page']
                or not hmac.compare_digest(record['verified_page'], page_token)):
            raise SetupExpired('Confirm your saved username before setting your credentials.')
        taken = dict(record)
        record.update(username=None, verified_page=None, completing=True,
                      completion_lookup=hash_username_lookup(username(taken)))
        return taken
    return _change(token, binding, update)


def restore(token, binding, taken, *, collision=False):
    def update(record):
        if not record['completing'] or record['generation'] != taken['generation']:
            raise SetupExpired('Setup expired. Please start again.')
        record.update(username=taken['username'], verified_page=None,
                      completing=False, collision=collision, completion_lookup=None)
    _change(token, binding, update)


def completion_is_valid(token, binding, generation, value):
    """Recheck the consumed proof under the FEAT's identity locks, after waits."""
    try:
        record = read(token, binding)
    except SetupExpired:
        return False
    return (record['completing'] and record['generation'] == generation
            and bool(record.get('completion_lookup'))
            and hmac.compare_digest(record['completion_lookup'], hash_username_lookup(value)))
