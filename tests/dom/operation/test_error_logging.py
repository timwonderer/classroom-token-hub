import logging
import re

from app import create_app


def test_DOM_OPS_001__unhandled_exception_logs_request_id_and_route(caplog):
    app = create_app()
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    @app.route("/_boom")
    def _boom():
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger=app.logger.name)

    # Well-formed, so only non-adoption -- not a format check -- can reject it.
    caller_id = "0" * 23 + "123456789"

    with app.test_client() as client:
        response = client.get("/_boom", headers={"X-Request-Id": caller_id})

    assert response.status_code == 500
    request_id = response.headers.get("X-Request-Id")
    # Generated at the entry point, never the caller's (DOM-OPS-001 INV-OPS-004).
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert request_id != caller_id

    matching_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Unhandled exception"
    ]
    assert matching_records, "Expected an Unhandled exception log entry."

    record = matching_records[0]
    assert getattr(record, "route", None) == "/_boom"
    assert getattr(record, "method", None) == "GET"
    assert getattr(record, "request_id", None) == request_id
