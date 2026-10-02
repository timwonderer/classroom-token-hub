"""Real Redis boundary checks for INV-ARC-018's volatile student setup state."""
import json
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from redis import ConnectionError

from app import app as flask_app
from app.services import student_setup as store


@pytest.fixture
def attempt():
    with flask_app.test_request_context('/'):
        owner = 'seat:test-' + secrets.token_hex(8)
        binding = secrets.token_hex(32)
        token = store.begin(owner, binding, ttl=120)
        store.generate(token, binding, lambda: 'pine-otter-riverAF')
        yield token, binding, owner
        store.forget_owner(owner)


def test_store_contains_no_plaintext_and_fixed_ttl_never_slides(attempt):
    token, binding, _ = attempt
    conn = store.client()
    key = store._key(token)
    initial = conn.pttl(key)
    assert 0 < initial <= 120_000
    raw = conn.get(key)
    assert 'pine-otter-riverAF' not in raw
    before = store.read(token, binding)
    for _ in range(3):
        store.generate(token, binding, lambda: pytest.fail('Existing username was regenerated'))
        assert store.verify(token, binding, 'page-token-0123456789012345', 'pine-otter-riverAF')[0]
        assert store.read(token, binding)['generation'] == before['generation']
        assert conn.pttl(key) <= initial


def test_expiry_and_wrong_scope_fail_closed(attempt):
    token, binding, _ = attempt
    with pytest.raises(store.SetupExpired):
        store.read(token, 'other-scope')
    store.client().expire(store._key(token), 0)
    for operation in (
        lambda: store.read(token, binding),
        lambda: store.verify(token, binding, 'page-token-0123456789012345', 'pine-otter-riverAF'),
        lambda: store.generate(token, binding, lambda: 'must-not-generate'),
    ):
        with pytest.raises(store.SetupExpired):
            operation()


def test_mismatch_revokes_previous_verification(attempt):
    token, binding, _ = attempt
    page = 'page-token-0123456789012345'
    assert store.verify(token, binding, page, 'pine-otter-riverAF') == (True, 1)
    assert store.verify(token, binding, page, 'wrong') == (False, 2)
    with pytest.raises(store.SetupExpired):
        store.take_verified(token, binding, page)


def test_only_one_concurrent_completion_consumes_the_proof(attempt):
    token, binding, _ = attempt
    page = 'page-token-0123456789012345'
    store.verify(token, binding, page, 'pine-otter-riverAF')
    def complete():
        with flask_app.app_context():
            try:
                taken = store.take_verified(token, binding, page)
                return store.username(taken)
            except store.SetupExpired:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: complete(), range(2)))
    assert results.count('pine-otter-riverAF') == 1 and results.count(None) == 1
    assert store.read(token, binding)['username'] is None


def test_failed_activation_restores_same_value_without_proof_or_extended_expiry(attempt):
    token, binding, _ = attempt
    page = 'page-token-0123456789012345'
    store.verify(token, binding, page, 'pine-otter-riverAF')
    ttl = store.client().pttl(store._key(token))
    taken = store.take_verified(token, binding, page)
    store.restore(token, binding, taken, collision=True)
    restored = store.read(token, binding)
    assert store.username(restored) == 'pine-otter-riverAF'
    assert not restored['verified_page'] and restored['collision']
    assert store.client().pttl(store._key(token)) <= ttl
    store.generate(token, binding, lambda: 'pine-badger-riverAF')
    assert store.username(store.read(token, binding)) == 'pine-badger-riverAF'


def test_replaced_or_destroyed_attempt_cannot_be_restored(attempt):
    token, binding, owner = attempt
    store.verify(token, binding, 'page-token-0123456789012345', 'pine-otter-riverAF')
    taken = store.take_verified(token, binding, 'page-token-0123456789012345')
    store.forget_owner(owner)
    with pytest.raises(store.SetupExpired):
        store.restore(token, binding, taken)
    assert store.client().get(store._key(token)) is None


@pytest.mark.parametrize('unsafe', [
    {'save': '60 1'}, {'appendonly': 'yes'}, {'slowlog-log-slower-than': '10000'},
])
def test_unsafe_persistence_configuration_is_refused(attempt, monkeypatch, unsafe):
    conn = store.client()
    config = conn.config_get('save', 'appendonly', 'slowlog-log-slower-than')
    config.update(unsafe)
    with monkeypatch.context() as patch:
        patch.setattr(conn, 'config_get', lambda *args: config)
        with pytest.raises(store.SetupUnavailable):
            store.read(attempt[0], attempt[1])


def test_replication_and_store_outage_are_refused_without_sensitive_errors(attempt, monkeypatch):
    conn = store.client()
    real_info = conn.info
    with monkeypatch.context() as patch:
        patch.setattr(conn, 'info', lambda section: {'role': 'master', 'connected_slaves': 1} if section == 'replication' else real_info(section))
        with pytest.raises(store.SetupUnavailable):
            store.read(attempt[0], attempt[1])
    with monkeypatch.context() as patch:
        def unavailable(*args):
            raise ConnectionError('sensitive-connection-detail')
        patch.setattr(conn, 'config_get', unavailable)
        with pytest.raises(store.SetupUnavailable) as error:
            store.read(attempt[0], attempt[1])
        assert 'sensitive-connection-detail' not in str(error.value)
        assert error.value.__suppress_context__


def test_shipped_redis_configuration_denies_persistence_commands(tmp_path, monkeypatch):
    import shutil
    import subprocess
    import time
    from pathlib import Path
    from redis import Redis, ResponseError

    # Use a short Unix socket path (macOS has a small sockaddr_un limit).
    import tempfile
    with tempfile.TemporaryDirectory(prefix='cth-conf-', dir='/tmp') as directory:
        config = (Path(__file__).resolve().parents[1] / 'infra/student-setup/redis.conf').read_text()
        config = config.replace('/run/cth-student-setup', directory)
        path = Path(directory) / 'redis.conf'
        path.write_text(config)
        process = subprocess.Popen([shutil.which('redis-server'), str(path)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            socket = Path(directory) / 'redis.sock'
            for _ in range(500):
                if socket.exists():
                    break
                assert process.poll() is None, 'Shipped Redis configuration was rejected'
                time.sleep(.01)
            assert socket.exists()
            with flask_app.test_request_context('/'):
                monkeypatch.setitem(flask_app.config, 'STUDENT_SETUP_REDIS_URL', 'unix://' + str(socket))
                token = store.begin('seat:config-test', 'config-binding')
                store.generate(token, 'config-binding', lambda: 'test-saved-username')
                assert store.username(store.read(token, 'config-binding')) == 'test-saved-username'
                conn = Redis(unix_socket_path=str(socket), decode_responses=True)
                for command in [('SAVE',), ('BGSAVE',), ('CONFIG', 'SET', 'save', '60 1'),
                                ('REPLICAOF', '127.0.0.1', '1'), ('MONITOR',)]:
                    with pytest.raises(ResponseError, match='permissions|NOPERM'):
                        conn.execute_command(*command)
                with pytest.raises(ResponseError, match='permissions|NOPERM'):
                    conn.set('unscoped-key', 'not-allowed')
        finally:
            process.terminate()
            process.wait(timeout=5)
        assert not list(Path(directory).glob('*.rdb'))
        assert not list(Path(directory).glob('appendonly*'))


def test_completion_guard_checks_live_generation_scope_and_value(attempt):
    token, binding, _ = attempt
    value = 'pine-otter-riverAF'
    page = 'page-token-0123456789012345'
    generation = store.read(token, binding)['generation']
    assert not store.completion_is_valid(token, binding, generation, value)
    store.verify(token, binding, page, value)
    store.take_verified(token, binding, page)
    assert store.completion_is_valid(token, binding, generation, value)
    assert not store.completion_is_valid(token, binding, 'another-generation', value)
    assert not store.completion_is_valid(token, 'another-scope', generation, value)
    assert not store.completion_is_valid(token, binding, generation, 'unverified-value')
    store.discard(token)
    assert not store.completion_is_valid(token, binding, generation, value)
