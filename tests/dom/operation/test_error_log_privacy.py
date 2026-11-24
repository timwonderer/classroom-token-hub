"""Error logs and request traces carry neither the raw URL nor a caller's request id.

INV-ARC-005 §V and DOM-OPS-001 §7 keep personal data and internal ids out of
logs: a URL's path and query can hold a student's name (``?student=``) or an
internal id (``?class_id=``), so logs name the route pattern instead.
DOM-OPS-001 INV-OPS-004 has the request id generated at the entry point, so a
caller's ``X-Request-Id`` is never adopted, echoed, logged or persisted.
"""

import logging
import re

import wsgi  # noqa: F401 -- registers the error handlers on import
from app.extensions import db
from app.models import ActorRequestTrace
from tests.helpers.classroom_initializer import initialize_as_student

SENTINEL = "Zelda-Sentinel-4417"
GENERATED_ID = re.compile(r"[0-9a-f]{32}")


def _logged(caplog):
    return "\n".join(f"{record.getMessage()} {vars(record)}" for record in caplog.records)


def test_DOM_OPS_001__unmatched_404_logs_neither_path_nor_query(client, app, caplog):
    caplog.set_level(logging.INFO)

    response = client.get(f"/no-such-{SENTINEL}?student={SENTINEL}&class_id={SENTINEL}")

    assert response.status_code == 404
    assert SENTINEL not in _logged(caplog)
    assert any(r.getMessage() == "404 Not Found: <unmatched>" for r in caplog.records)


def test_DOM_OPS_001__matched_404_logs_the_route_pattern_not_the_url(client, app, caplog):
    caplog.set_level(logging.INFO)

    response = client.get(f"/docs/{SENTINEL}?student={SENTINEL}")

    assert response.status_code == 404
    assert SENTINEL not in _logged(caplog)
    assert any(r.getMessage() == "404 Not Found: /docs/<path:doc_path>" for r in caplog.records)


def test_INV_OPS_004__caller_request_id_is_not_adopted_echoed_or_logged(client, app, caplog):
    caplog.set_level(logging.INFO)

    response = client.get(
        f"/no-such-{SENTINEL}",
        headers={"X-Request-Id": SENTINEL, "X-Correlation-Id": SENTINEL},
    )

    assert response.status_code == 404
    echoed = response.headers.get("X-Request-Id")
    assert echoed != SENTINEL and GENERATED_ID.fullmatch(echoed)
    assert SENTINEL not in _logged(caplog)


def test_INV_OPS_004__caller_request_id_is_not_persisted_to_the_trace(client, app, tlcp_trace_enabled):
    _, student = initialize_as_student("chemistry_p1", client, app)

    response = client.get("/student/dashboard", headers={"X-Request-Id": SENTINEL})

    assert response.status_code == 200
    db.session.expire_all()
    request_ids = [
        row.request_id
        for row in ActorRequestTrace.query.filter_by(actor_public_id=student.seat.public_id)
    ]
    assert request_ids, "Expected the dashboard request to be traced."
    assert SENTINEL not in request_ids
    assert response.headers.get("X-Request-Id") in request_ids
