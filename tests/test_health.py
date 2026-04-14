import logging
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
            "failure_total": 0,
            "checks": [
                {"name": "money_supply_integrity", "status": "PASS", "failure_count": 0},
                {"name": "ledger_consistency", "status": "PASS", "failure_count": 0},
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
    assert resp.json["failure_total"] == 0


def test_health_invariants_fail(monkeypatch, client):
    """Any check failing → 500 with status FAIL."""
    import app.services.invariant_runner as runner

    def mock_run_invariants():
        return {
            "status": "FAIL",
            "failed_count": 1,
            "failure_total": 3,
            "checks": [
                {
                    "name": "money_supply_integrity",
                    "status": "FAIL",
                    "details": "Money supply drift: 1000¢ vs 900¢ (delta: +100¢)",
                    "failure_count": 3,
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
    assert resp.json["failure_total"] == 3
    assert resp.json["checks"][0]["details"] == "Money supply drift: 1000¢ vs 900¢ (delta: +100¢)"


def test_run_invariants_logs_check_summaries(monkeypatch, caplog):
    import app.services.invariant_runner as runner

    def check_pass():
        return {"name": "ledger_balance_consistency", "status": "PASS"}

    def check_fail():
        return {
            "name": "money_supply_integrity",
            "status": "FAIL",
            "details": "Money supply drift: cached balances total 1000¢, ledger totals 900¢ (delta: +100¢)",
            "failure_count": 3,
        }

    monkeypatch.setattr(runner, "_CHECKS", [check_pass, check_fail])
    monkeypatch.setattr(
        runner,
        "utc_now",
        lambda: type("MockNow", (), {"isoformat": lambda self: "2026-01-01T00:00:00+00:00"})(),
    )
    caplog.set_level(logging.INFO, logger=runner.logger.name)

    result = runner.run_invariants()

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 1
    assert result["failure_total"] == 3

    summary_records = [
        record for record in caplog.records if record.getMessage() == "invariant_check_summary"
    ]
    assert len(summary_records) == 2

    failed_summary = next(record for record in summary_records if getattr(record, "check", None) == "money_supply_integrity")
    assert getattr(failed_summary, "check_status", None) == "FAIL"
    assert getattr(failed_summary, "failure_count", None) == 3
    assert "Money supply drift" in getattr(failed_summary, "details", "")
