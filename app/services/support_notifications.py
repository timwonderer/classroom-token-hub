"""Post-commit, non-identifying Support alerts (DOM-SUP-001 §XI)."""

import http.client
import json
import logging
import re
from urllib.parse import quote

from flask import current_app
from sqlalchemy import event

from app.extensions import db
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.opaque_refs import make_opaque_ref


_PENDING = "support_ifttt_notifications"
_LABELS = {
    "teacher_ticket": "New teacher support ticket",
    "student_escalation": "Student support ticket escalated by teacher",
}


def schedule_support_notification(issue_id, *, event_type):
    """Freeze only allow-listed values inside the owning Support transaction.

    This is transaction-local memory, not a durable queue. Never retain an ORM
    object or query classroom data during delivery.
    """
    if not current_app.config.get("SUPPORT_IFTTT_EVENT") and not current_app.config.get("SUPPORT_IFTTT_KEY"):
        return
    session = db.session()
    transaction = session.get_nested_transaction() or session.get_transaction()
    if transaction is None:
        raise RuntimeError("Support notifications require the ticket transaction.")
    payload = {
        "value1": _LABELS[event_type],
        "value2": make_opaque_ref("issue", issue_id),
        "value3": utc_now().isoformat(),
    }
    session.info.setdefault(_PENDING, []).append((transaction, payload))


def _log_outcome(level, message, *args):
    # RequestIdFilter respects explicit fields. Supply inert values so the
    # production formatter cannot attach actor/class/request context to alerts.
    current_app.logger.log(level, message, *args, extra={
        "request_id": "-", "actor_type": "-", "actor_public_id": "-",
        "class_id": "-", "endpoint": "-", "method": "-",
        "error_class": "-", "error_message": "-", "correlation_version": "-",
    })


def _deliver(payload):
    """One HTTPS attempt; delivery cannot change the committed ticket outcome."""
    connection = None
    try:
        event_name = current_app.config.get("SUPPORT_IFTTT_EVENT", "")
        key = current_app.config.get("SUPPORT_IFTTT_KEY", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", event_name) or not key:
            _log_outcome(logging.WARNING, "support_notification_delivery_failed reason=configuration")
            return
        # Use the fixed IFTTT host with no redirects, retries or HTTP-client
        # tracing. The credential is in IFTTT's path; never log the URL, response
        # body or exception text. HTTPSConnection does not enable debug logging.
        connection = http.client.HTTPSConnection("maker.ifttt.com", timeout=3)
        connection.request(
            "POST",
            f"/trigger/{quote(event_name, safe='')}/with/key/{quote(key, safe='')}",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if 200 <= response.status < 300:
            _log_outcome(logging.INFO, "support_notification_delivered")
        else:
            _log_outcome(logging.WARNING, "support_notification_delivery_failed reason=http_status status=%s", response.status)
    except Exception:
        _log_outcome(logging.WARNING, "support_notification_delivery_failed reason=transport")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass  # A close failure cannot turn a committed filing into failure.


@event.listens_for(db.session, "after_commit")
def _send_committed_support_notifications(session):
    # SQLAlchemy emits after_commit for SAVEPOINT releases too. Only the outer
    # commit proves the ticket durable; the payload needs no DB reads here.
    if session.in_nested_transaction():
        return
    for _, payload in session.info.pop(_PENDING, []):
        _deliver(payload)


@event.listens_for(db.session, "after_soft_rollback")
def _discard_rolled_back_support_notifications(session, previous_transaction):
    pending = session.info.get(_PENDING, [])
    retained = []
    for transaction, payload in pending:
        ancestor = transaction
        while ancestor is not None and ancestor is not previous_transaction:
            ancestor = ancestor.parent
        if ancestor is None:
            retained.append((transaction, payload))
    if retained:
        session.info[_PENDING] = retained
    else:
        session.info.pop(_PENDING, None)


@event.listens_for(db.session, "after_transaction_end")
def _clear_ended_support_transaction(session, transaction):
    if transaction.parent is None:
        # Also discard on Session.close(), which ends an uncommitted transaction
        # without emitting after_soft_rollback. Successful delivery already popped
        # the payloads in after_commit.
        session.info.pop(_PENDING, None)
