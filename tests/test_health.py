import pytest
from sqlalchemy.exc import SQLAlchemyError
from app import db


def test_health_ok(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.data == b'ok'


def test_health_db_error(monkeypatch, client):
    def raise_error(*args, **kwargs):
        raise SQLAlchemyError("fail")
    monkeypatch.setattr(db.session, 'execute', raise_error)
    resp = client.get('/health')
    assert resp.status_code == 500
    assert resp.is_json
    assert resp.json['error'] == 'Database error'


# ── /health/invariants ────────────────────────────────────────────────────────

def test_health_invariants_pass(monkeypatch, client):
    """All checks passing → 200 with status PASS."""
    import app.services.invariant_runner as runner

    def mock_run_invariants():
        return {
            "status": "PASS",
            "failed_count": 0,
            "checks": [
                {"name": "money_supply_integrity", "status": "PASS"},
                {"name": "ledger_consistency", "status": "PASS"},
            ],
            "duration_ms": 5,
            "timestamp": "2026-01-01T00:00:00Z",
        }

    monkeypatch.setattr(runner, "run_invariants", mock_run_invariants)
    resp = client.get('/health/invariants')
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.json["status"] == "PASS"
    assert resp.json["failed_count"] == 0


def test_health_invariants_fail(monkeypatch, client):
    """Any check failing → 500 with status FAIL."""
    import app.services.invariant_runner as runner

    def mock_run_invariants():
        return {
            "status": "FAIL",
            "failed_count": 1,
            "checks": [
                {
                    "name": "money_supply_integrity",
                    "status": "FAIL",
                    "details": "Money supply drift: 1000¢ vs 900¢ (delta: +100¢)",
                },
            ],
            "duration_ms": 8,
            "timestamp": "2026-01-01T00:00:00Z",
        }

    monkeypatch.setattr(runner, "run_invariants", mock_run_invariants)
    resp = client.get('/health/invariants')
    assert resp.status_code == 500
    assert resp.is_json
    assert resp.json["status"] == "FAIL"
    assert resp.json["failed_count"] == 1
