import pytest
from sqlalchemy.exc import SQLAlchemyError
from app import db


def test_DOM_OPS_001__health_ok(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.data == b'ok'


def test_DOM_OPS_001__health_db_error(monkeypatch, client):
    def raise_error(*args, **kwargs):
        raise SQLAlchemyError("fail")
    # The /health probe issues db.session.scalar(text('SELECT 1')). Patch the
    # method production actually invokes; patching db.session.execute does not
    # intercept it (Session.scalar routes through _execute_internal on the real
    # Session, not the scoped_session proxy), so the probe would run for real.
    monkeypatch.setattr(db.session, 'scalar', raise_error)
    resp = client.get('/health')
    assert resp.status_code == 500
    assert resp.is_json
    assert resp.json['error'] == 'Database error'


def test_DOM_OPS_001__bounded_status_signals(client):
    resp = client.get('/health/status')
    assert resp.status_code == 200
    assert 'observed_at' in resp.json
    assert {signal['key'] for signal in resp.json['signals']} >= {
        'login', 'attendance', 'payroll', 'database', 'invariant_verification'
    }
    assert all('class_id' not in signal for signal in resp.json['signals'])


def test_DOM_OPS_001__deep_health_surface_is_retired(client):
    assert client.get('/health/deep').status_code == 404
