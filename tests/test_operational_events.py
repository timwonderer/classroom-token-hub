"""operational_events: table creation, record() persistence, and the sysadmin
dashboard 500 it was causing (finding 14). The sysadmin log viewers that read the
table were removed on 2026-10-07 (logs are read in Grafana; SPEC-OPS-004 1.4), so
persistence is checked against the table directly.

A prior migration (7c3d4e5f6a7b) dropped the legacy error_logs/error_events
tables on the stated rationale that they were "absorbed into
operational_events (DOM-OPS-001)" -- but no migration ever created that
replacement table, and record() never actually wrote to it (it only logged).
get_recent_error_events()/get_error_events() (since removed) had queried a table that never
existed since that drop landed. Confirmed live: GET /sysadmin/dashboard
500s with psycopg2.errors.UndefinedTable.
"""
from __future__ import annotations

import sqlalchemy as sa

from app.extensions import db
from app.services import operational_event_service as ops
from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin


def test_record_persists_a_row(app):
    with app.app_context():
        ops.record(
            event_type="TEST_EVENT",
            severity="critical",
            domain="test",
            details={"probe": "value"},
        )
        rows = db.session.execute(
            sa.text("SELECT level, message FROM operational_events WHERE message = 'test.TEST_EVENT'")
        ).all()
        assert [(row.level, row.message) for row in rows] == [("CRITICAL", "test.TEST_EVENT")]


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
