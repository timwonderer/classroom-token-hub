import logging
import json
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import ErrorEvent
from flask import g, session
from gunicorn_json_logging import GunicornJsonFormatter
from werkzeug.exceptions import BadRequest
from wsgi import log_error_to_db


def test_unhandled_exception_logs_request_id_and_route(caplog):
    app = create_app()
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    @app.route("/_boom")
    def _boom():
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger=app.logger.name)

    with app.test_client() as client:
        response = client.get("/_boom", headers={"X-Request-Id": "test-request-id"})

    assert response.status_code == 500
    assert response.headers.get("X-Request-Id") == "test-request-id"

    matching_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Unhandled exception"
    ]
    assert matching_records, "Expected an Unhandled exception log entry."

    record = matching_records[0]
    assert getattr(record, "route", None) == "/_boom"
    assert getattr(record, "method", None) == "GET"
    assert getattr(record, "request_id", None) == "test-request-id"
    assert getattr(record, "error_class", None) == "RuntimeError"


def test_request_logger_exception_infers_error_class_from_exc_info(caplog):
    app = create_app()

    caplog.set_level(logging.ERROR, logger=app.logger.name)

    with app.test_request_context("/_probe", method="GET", headers={"X-Request-Id": "probe-request-id"}):
        for fn in app.before_request_funcs.get(None, []):
            fn()
        try:
            raise ValueError("probe failure")
        except Exception:
            app.logger.exception("Probe exception log")

    matching_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Probe exception log"
    ]
    assert matching_records, "Expected Probe exception log entry."

    record = matching_records[0]
    assert getattr(record, "request_id", None) == "probe-request-id"
    assert getattr(record, "method", None) == "GET"
    assert getattr(record, "endpoint", None) == "/_probe"
    assert getattr(record, "error_class", None) == "ValueError"
    assert getattr(record, "error_message", None) == "probe failure"


def test_default_log_formatter_emits_json_with_request_context():
    app = create_app()
    handler = app.logger.handlers[0]

    with app.test_request_context("/_json_log", method="POST", headers={"X-Request-Id": "json-log-request"}):
        for fn in app.before_request_funcs.get(None, []):
            fn()

        record = app.logger.makeRecord(
            app.logger.name,
            logging.INFO,
            __file__,
            0,
            "Structured log probe",
            args=(),
            exc_info=None,
            extra={"route": "/_json_log"},
        )
        for log_filter in handler.filters:
            assert log_filter.filter(record) is True

        payload = json.loads(handler.format(record))

    assert payload["message"] == "Structured log probe"
    assert payload["request_id"] == "json-log-request"
    assert payload["method"] == "POST"
    assert payload["endpoint"] == "/_json_log"
    assert payload["route"] == "/_json_log"
    assert payload["level"] == "INFO"
    assert "timestamp" in payload


def test_default_log_formatter_preserves_custom_extra_fields():
    app = create_app()
    handler = app.logger.handlers[0]

    record = app.logger.makeRecord(
        app.logger.name,
        logging.INFO,
        __file__,
        0,
        "Structured extra probe",
        args=(),
        exc_info=None,
        extra={
            "failure_total": 3,
            "failed_checks": [{"name": "money_supply_integrity", "failure_count": 3}],
            "details": "Money supply drift",
        },
    )

    payload = json.loads(handler.format(record))

    assert payload["failure_total"] == 3
    assert payload["failed_checks"] == [{"name": "money_supply_integrity", "failure_count": 3}]
    assert payload["details"] == "Money supply drift"


def test_handled_http_error_creates_structured_error_event(client):
    app = client.application

    with app.app_context():
        db.create_all()
        ErrorEvent.query.delete()
        db.session.commit()

    with app.test_request_context("/_bad_request", method="GET", headers={"X-Request-Id": "handled-error-request"}):
        session["is_admin"] = True
        session["admin_id"] = 123
        for fn in app.before_request_funcs.get(None, []):
            fn()
        log_error_to_db(
            error_type="400 Bad Request",
            error_message="Bad request on /_bad_request: probe bad request",
            stack_trace=None,
        )

    with app.app_context():
        row = ErrorEvent.query.order_by(ErrorEvent.id.desc()).first()
        assert row is not None
        assert row.request_id == "handled-error-request"
        assert row.actor_type == "teacher"
        assert row.endpoint == "/_bad_request"
        assert row.method == "GET"
        assert row.error_class == "400 Bad Request"
        assert "probe bad request" in (row.error_message or "")


def test_gunicorn_access_formatter_uses_pacific_timestamp(monkeypatch):
    monkeypatch.setenv("GUNICORN_ACCESS_LOG_TIMEZONE", "America/Los_Angeles")
    formatter = GunicornJsonFormatter()
    record = logging.LogRecord(
        name="gunicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(B)s \"%(f)s\" \"%(a)s\"",
        args={
            "h": "127.0.0.1",
            "l": "-",
            "u": "-",
            "t": "[14/Apr/2026:04:38:49 +0000]",
            "r": "GET /sw.js HTTP/1.0",
            "m": "GET",
            "U": "/sw.js",
            "q": "",
            "H": "HTTP/1.0",
            "s": "304",
            "B": "0",
            "f": "https://app.classroomtokenhub.com/sw.js",
            "a": "Mozilla/5.0",
            "L": "0.001634",
            "D": "1634",
            "p": "<96018>",
        },
        exc_info=None,
    )
    record.created = datetime.fromisoformat("2026-04-14T04:38:50.001634+00:00").timestamp()

    payload = json.loads(formatter.format(record))

    assert payload["timestamp"] == "2026-04-14T04:38:50.001634+00:00"
    assert payload["timestamp_local"] == "[13/Apr/2026:21:38:50 -0700]"
    assert "[13/Apr/2026:21:38:50 -0700]" in payload["message"]
    assert "[14/Apr/2026:04:38:49 +0000]" not in payload["message"]
