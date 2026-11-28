"""Races around consuming TOTP-replacement step-up evidence (SPEC-IDEN-002 §V, TOTP replacement step-up).

Real concurrent Postgres transactions, not mocks: a second connection holds the principal row
lock (as another credential command in flight does) while the consumption waits on it, and
commits the competing change before releasing it. The consumption must then decide on what is
committed, and read the clock only after it holds both locks.

Each assertion below was watched to fail with its lock or recheck removed (recorded in the pull
request); the properties are: exactly one of two consumptions of the same token, or of the same
challenge, commits; a consumption never authorizes against a retired credential, an advanced
generation, a superseded operation or a destroyed principal; and a destruction takes the principal
lock before any other row, so it cannot deadlock against a consumption.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import text

from app import db
from app.feats.base import FEATContext
from app.feats.credential_operations_feat import authorize_totp_replacement
from app.models import CredentialOperation, CredentialOperationStage, User
from app.services import credential_lifecycle as lifecycle
from app.services.context_resolver import BoundaryContext
from tests.dom.identity.test_totp_step_up_evidence import AWAITING, Rig, at, base, rig, text as instant  # noqa: F401
from tests.helpers import temporal
from tests.helpers.passkey import fake_passwordless  # noqa: F401  (fixture)


def _outcome(app, call):
    """Run ``call`` in its own app context and session; ``("ok", value)`` or ``("refused", category)``."""
    with app.app_context():
        try:
            return ("ok", call())
        except lifecycle.CredentialOperationRefused as refused:
            return ("refused", refused.category)
        finally:
            db.session.remove()


def _waiting_on_a_lock(count=1, timeout=15):
    """Block until ``count`` backends wait for a lock held by another."""
    deadline = monotonic() + timeout
    with db.engine.connect() as conn:
        while monotonic() < deadline:
            waiting = conn.execute(text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()")).scalar_one()
            if waiting >= count:
                return
            sleep(0.05)
    raise AssertionError(f"fewer than {count} backends reached a lock wait")


@contextmanager
def _holding_the_principal_lock(user_id):
    """Another connection that holds the principal row, as a competing credential command would."""
    with db.engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})
            yield conn


def _authorized(rig, base, now_ms, ts_ms=10_000, exp_ms=70_000, *, challenge, token=None):
    token = token or rig.token(ts_ms, exp_ms, base)
    return lambda: authorize_totp_replacement(
        user_id=rig.user_id, session_nonce=rig.nonce_value, token=token, challenge=challenge)


@pytest.fixture
def raced(rig, base):
    """A rig with a challenge stored at ``base``, the committed nonce captured for threads."""
    rig.nonce_value = rig.nonce
    rig.challenge = rig.issue(base)
    db.session.commit()
    return rig


def _states(rig):
    db.session.expire_all()
    return [(o.stage, o.step_up_token_id) for o in CredentialOperation.query.filter_by(user_id=rig.user_id)]


# ---------------------------------------------------------------------------
# the same evidence, or the same challenge, consumed twice at once
# ---------------------------------------------------------------------------

def test_FEAT_IDEN_106__the_same_token_consumed_twice_at_once_commits_exactly_once(raced, base):
    token = raced.token(10_000, 70_000, base)
    with temporal.pinned_clock(at(base, 30_000)), ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: _outcome(raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token)),
            range(2)))

    assert sorted(kind for kind, _ in results) == ["ok", "refused"], results
    assert [category for kind, category in results if kind == "refused"] == ["operation_not_open"]
    ((stage, token_id),) = _states(raced)
    assert stage is CredentialOperationStage.AUTHORIZED and token_id


def test_FEAT_IDEN_106__one_challenge_answered_by_two_tokens_commits_exactly_once(raced, base):
    tokens = [raced.token(10_000, 70_000, base), raced.token(11_000, 71_000, base)]
    with temporal.pinned_clock(at(base, 30_000)), ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda token: _outcome(raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token)),
            tokens))

    assert sorted(kind for kind, _ in results) == ["ok", "refused"], results
    ((stage, token_id),) = _states(raced)
    assert stage is CredentialOperationStage.AUTHORIZED and token_id


# ---------------------------------------------------------------------------
# the clock is read after the locks, not before the wait for them
# ---------------------------------------------------------------------------

def test_FEAT_IDEN_106__a_consumption_that_waits_for_the_lock_reads_the_clock_afterwards(raced, base):
    token = raced.token(10_000, 70_000, base)  # expiresAt = base + 70 s
    with temporal.movable_clock(at(base, 30_000)) as clock, ThreadPoolExecutor(max_workers=1) as pool:
        with _holding_the_principal_lock(raced.user_id):
            waiting = pool.submit(
                _outcome, raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token))
            _waiting_on_a_lock()
            assert not waiting.done()
            clock.now = at(base, 70_000)  # the evidence expires while the consumption waits
        result = waiting.result(timeout=20)

    assert result == ("refused", "step_up_expired")
    ((stage, token_id),) = _states(raced)
    assert stage is AWAITING and token_id is None


def test_FEAT_IDEN_106__the_same_wait_with_time_to_spare_still_authorizes(raced, base):
    """The control: the identical interleaving authorizes when nothing expired."""
    token = raced.token(10_000, 70_000, base)
    with temporal.movable_clock(at(base, 30_000)) as clock, ThreadPoolExecutor(max_workers=1) as pool:
        with _holding_the_principal_lock(raced.user_id):
            waiting = pool.submit(
                _outcome, raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token))
            _waiting_on_a_lock()
            clock.now = at(base, 31_000)
        assert waiting.result(timeout=20)[0] == "ok"


# ---------------------------------------------------------------------------
# a competing credential command commits while the consumption waits
# ---------------------------------------------------------------------------

def _race(raced, base, competing):
    """Consume while ``competing(conn)`` runs on the lock-holding connection; the consumption's outcome."""
    token = raced.token(10_000, 70_000, base)
    with temporal.pinned_clock(at(base, 30_000)), ThreadPoolExecutor(max_workers=1) as pool:
        with _holding_the_principal_lock(raced.user_id) as conn:
            waiting = pool.submit(
                _outcome, raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token))
            _waiting_on_a_lock()
            competing(conn)
        return waiting.result(timeout=20)


def test_FEAT_IDEN_106__a_credential_retired_while_the_consumption_waits_is_not_authorized(raced, base):
    def retire(conn):  # passkey revocation's committed effect: the binding is gone, the generation advanced
        conn.execute(text("DELETE FROM passkey_credentials WHERE user_id = :id"), {"id": raced.user_id})
        conn.execute(text("UPDATE users SET credential_generation = credential_generation + 1 WHERE id = :id"),
                     {"id": raced.user_id})

    assert _race(raced, base, retire) == ("refused", "stale_generation")
    ((stage, token_id),) = _states(raced)
    assert stage is AWAITING and token_id is None


def test_FEAT_IDEN_106__a_binding_removed_without_a_generation_change_is_still_refused(raced, base):
    def remove_binding(conn):
        conn.execute(text("DELETE FROM passkey_credentials WHERE user_id = :id"), {"id": raced.user_id})

    assert _race(raced, base, remove_binding) == ("refused", "step_up_credential")
    ((stage, token_id),) = _states(raced)
    assert stage is AWAITING and token_id is None


def test_FEAT_IDEN_106__a_generation_advanced_while_the_consumption_waits_is_refused(raced, base):
    def advance(conn):
        conn.execute(text("UPDATE users SET credential_generation = credential_generation + 1 WHERE id = :id"),
                     {"id": raced.user_id})

    assert _race(raced, base, advance) == ("refused", "stale_generation")


def test_FEAT_IDEN_106__recovery_superseding_the_operation_while_the_consumption_waits_is_refused(raced, base):
    def supersede(conn):  # SATAR success: the generation advances and the open operation is cancelled
        conn.execute(text("UPDATE users SET credential_generation = credential_generation + 1 WHERE id = :id"),
                     {"id": raced.user_id})
        conn.execute(text(
            "UPDATE credential_operations SET stage = 'cancelled', step_up_challenge_hash = NULL "
            "WHERE user_id = :id"), {"id": raced.user_id})

    assert _race(raced, base, supersede) == ("refused", "operation_not_open")
    ((stage, token_id),) = _states(raced)
    assert stage is CredentialOperationStage.CANCELLED and token_id is None


def test_FEAT_IDEN_106__a_principal_destroyed_while_the_consumption_waits_leaves_no_authorized_operation(raced, base):
    def destroy(conn):  # the principal row goes; its operations go with it (ON DELETE CASCADE)
        conn.execute(text("DELETE FROM credential_operations WHERE user_id = :id"), {"id": raced.user_id})
        conn.execute(text("DELETE FROM passkey_credentials WHERE user_id = :id"), {"id": raced.user_id})
        conn.execute(text("UPDATE classes SET teacher_user_id = NULL WHERE teacher_user_id = :id"), {"id": raced.user_id})
        conn.execute(text("DELETE FROM seats WHERE user_id = :id"), {"id": raced.user_id})
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": raced.user_id})

    assert _race(raced, base, destroy) == ("refused", "ineligible_principal")
    assert _states(raced) == []


# ---------------------------------------------------------------------------
# destruction takes the principal lock before any other row (both entry paths)
# ---------------------------------------------------------------------------

def _row_is_free(table, where, params):
    """Whether a third connection can lock the row at once (NOWAIT): nobody else holds it."""
    with db.engine.connect() as conn:
        with conn.begin():
            try:
                conn.execute(text(f"SELECT 1 FROM {table} WHERE {where} FOR UPDATE NOWAIT"), params)
                return True
            except Exception as exc:  # noqa: BLE001 -- psycopg's LockNotAvailable, wrapped by SQLAlchemy
                assert "lock" in str(exc).lower(), exc
                return False


def _pause_consumption_after_the_principal_lock(monkeypatch):
    """Make a consumption stop, holding the principal lock, just before it locks its operation row."""
    holding, release = Event(), Event()
    real = lifecycle._lock_operation

    def paused(operation_id):
        holding.set()
        assert release.wait(30), "the test never released the paused consumption"
        return real(operation_id)

    monkeypatch.setattr(lifecycle, "_lock_operation", paused)
    return holding, release, lambda: monkeypatch.setattr(lifecycle, "_lock_operation", real)


def _destroy_stale(user_id):
    from app.services import teacher_lifecycle

    # ``destroy_stale_teacher`` is itself the FEAT-IDEN-007 command; it locks the principal first.
    return lambda: teacher_lifecycle.destroy_stale_teacher(
        user_id=user_id, correlation_id=f"corr_{uuid.uuid4().hex}", idempotency_key=f"stale:{uuid.uuid4().hex}")


def _destroy_account(user_id):
    from app.services.teacher_destruction import _destroy_teacher_account_rows

    def run():
        with FEATContext("FEAT-IDEN-007", idempotency_key=f"test:destroy:{uuid.uuid4().hex}"):
            return _destroy_teacher_account_rows(
                canonical_context=BoundaryContext(user_id=user_id, actor_role="teacher"))
    return run


@pytest.mark.parametrize("entry", ["account_destruction", "stale_purge"])
def test_FEAT_IDEN_106__destruction_waits_on_the_principal_lock_before_touching_any_other_row(
        raced, base, monkeypatch, entry):
    """Without the principal lock at the start of ``_destroy_teacher_account_rows`` the destruction would
    take the class row (and the rest of its teardown) while a consumption holds the principal and waits on
    its operation row: the lock-order inversion this closes."""
    if entry == "stale_purge":
        from app.services import teacher_lifecycle
        monkeypatch.setattr(teacher_lifecycle, "teacher_account_is_stale", lambda user, now: True)
    destroy = _destroy_account(raced.user_id) if entry == "account_destruction" else _destroy_stale(raced.user_id)
    class_id = raced.classroom.class_id
    token = raced.token(10_000, 70_000, base)
    holding, release, restore = _pause_consumption_after_the_principal_lock(monkeypatch)

    with temporal.pinned_clock(at(base, 30_000)), ThreadPoolExecutor(max_workers=2) as pool:
        consuming = pool.submit(
            _outcome, raced.app, _authorized(raced, base, 30_000, challenge=raced.challenge, token=token))
        assert holding.wait(20)  # the consumption holds the principal row
        destroying = pool.submit(_outcome, raced.app, destroy)
        _waiting_on_a_lock()  # the destruction is queued behind the principal lock...
        # ...and has locked nothing else: the teacher's class row is free for a third connection.
        assert _row_is_free("classes", "class_id = :c", {"c": class_id}), (
            "the destruction took other rows before the principal lock")
        release.set()
        consumed = consuming.result(timeout=30)
        destroyed = destroying.result(timeout=60)

    restore()
    assert consumed[0] == "ok", consumed       # the consumption committed first, under its own locks
    assert destroyed[0] == "ok", destroyed     # then the destruction ran: no deadlock, no stranded lock
    db.session.expire_all()
    assert db.session.get(User, raced.user_id) is None
    assert CredentialOperation.query.filter_by(user_id=raced.user_id).count() == 0  # nothing authorized survives
