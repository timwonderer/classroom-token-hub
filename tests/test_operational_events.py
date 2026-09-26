"""operational_events: table creation, the record()/read round trip, and the
sysadmin dashboard 500 it was causing (finding 14).

A prior migration (7c3d4e5f6a7b) dropped the legacy error_logs/error_events
tables on the stated rationale that they were "absorbed into
operational_events (DOM-OPS-001)" -- but no migration ever created that
replacement table, and record() never actually wrote to it (it only logged).
get_recent_error_events()/get_error_events() have queried a table that never
existed since that drop landed. Confirmed live: GET /sysadmin/dashboard
500s with psycopg2.errors.UndefinedTable.
"""
from __future__ import annotations

from app.services import operational_event_service as ops
from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin


def test_record_persists_a_row_readable_by_get_error_events(app):
    with app.app_context():
        ops.record(
            event_type="TEST_EVENT",
            severity="critical",
            domain="test",
            details={"probe": "value"},
        )
        rows = ops.get_error_events()
        assert any(r["error_type"] == "CRITICAL" and r["error_message"] == "test.TEST_EVENT" for r in rows)


def test_get_recent_error_events_respects_the_limit_and_level_filter(app):
    with app.app_context():
        for i in range(3):
            ops.record(event_type=f"EVT_{i}", severity="error", domain="test")
        ops.record(event_type="NOT_AN_ERROR", severity="info", domain="test")

        rows = ops.get_recent_error_events(limit=2)
        assert len(rows) == 2
        assert all(r["error_type"] in ("ERROR", "CRITICAL") for r in rows)
        assert all(r["error_message"] != "test.NOT_AN_ERROR" for r in rows)


def test_record_never_raises_even_if_persistence_fails(app, monkeypatch):
    """Telemetry must not break the caller's actual operation."""
    with app.app_context():
        def _boom(*a, **kw):
            raise RuntimeError("simulated persistence failure")
        monkeypatch.setattr(ops.json, "dumps", _boom)
        ops.record(event_type="WILL_FAIL_TO_PERSIST", severity="error", domain="test")  # must not raise


def test_sysadmin_dashboard_does_not_500(app, client):
    sysadmin = create_sysadmin(username="ops_events_operator")
    login_sysadmin(client, "ops_events_operator", sysadmin.id)

    response = client.get("/sysadmin/dashboard")

    assert response.status_code == 200
