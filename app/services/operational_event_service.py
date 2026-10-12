from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from flask import current_app, g, has_request_context, request, session

from app.extensions import db
from app.utils.canonical_temporal_resolver import utc_now

# Severity levels considered surface-worthy for operator error dashboards.
_ERROR_LEVELS = ("ERROR", "CRITICAL")

# operational_events.level is a plain VARCHAR, not a DB-enforced enum (this
# codebase's convention -- see Issue.status). DOM-OPS-001 SS5 specifies
# DEBUG/INFO/WARN/ERROR/CRITICAL; record() accepts a slightly richer set of
# caller-facing severities (its only two call sites today both pass
# "warning") and maps them onto that fixed vocabulary here, once, so every
# writer answers "what level is this" the same way.
_LEVEL_BY_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARN",
    "warn": "WARN",
    "error": "ERROR",
    "critical": "CRITICAL",
    # Security-relevant but not itself a crash -- surfaced at ERROR so it is
    # not silently invisible to the same dashboard that watches for outages.
    "security": "ERROR",
}


def record(
    *,
    event_type: str,
    severity: str = "info",
    domain: str,
    route: Optional[str] = None,
    actor_seat_id: Optional[int] = None,
    class_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Record structured operational events in a stable, queryable shape.

    Logs (as before) AND persists a row to ``operational_events``
    (DOM-OPS-001 SS4: "Emit Structured Log -> Effect: Appends to
    operational_events"). The table did not exist until live-blocking
    finding 14; the migration that was supposed to create it only dropped its
    predecessors. Nothing in the console reads it: logs are read in Grafana
    (SPEC-OPS-004 1.4).

    Writes on a raw engine connection, not ``db.session``: this must be
    callable from anywhere, including inside an exception handler right after
    a business-transaction rollback, and it must never participate in that
    transaction's boundary (an error record surviving the very rollback it is
    documenting is the point). A raw connection also never touches
    ``db.session``'s FEAT-context enforcement (app/feats/base.py's
    before_flush/before_commit listeners are registered on the scoped session
    object, not on the engine) -- appropriate here, since this is cross-cutting
    observability, not a domain mutation, and wrapping every call site in a
    FEATContext for this would be the wrong layer entirely.

    Never raises: a failure to persist telemetry must not break the caller's
    actual operation.
    """
    if not event_type or not domain:
        return

    payload = {
        "event_type": event_type,
        "severity": severity,
        "domain": domain,
        "route": route or (request.path if has_request_context() else None),
        "actor_seat_id": (actor_seat_id if actor_seat_id is not None else (
            getattr(getattr(g, 'canonical_context', None), 'seat_id', None)
            if has_request_context() and getattr(getattr(g, 'canonical_context', None), 'class_id', None) == class_id
            else None
        )) if class_id else None,
        "class_id": class_id,
        "correlation_id": correlation_id,
        "details": details or {},
    }

    # Keep this as warning-or-info style operational telemetry, not exception noise.
    log_fn = current_app.logger.warning if severity in {"warning", "error", "critical", "security"} else current_app.logger.info
    log_fn("OPERATIONAL_EVENT %s", payload)

    level = _LEVEL_BY_SEVERITY.get((severity or "info").lower(), "INFO")
    try:
        with db.engine.connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO operational_events "
                    "(id, created_at, correlation_id, domain, level, message, payload) "
                    "VALUES (:id, :created_at, :correlation_id, :domain, :level, :message, :payload)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "created_at": utc_now(),
                    "correlation_id": correlation_id,
                    "domain": domain,
                    "level": level,
                    "message": f"{domain}.{event_type}",
                    "payload": json.dumps(payload),
                },
            )
            conn.commit()
    except Exception:  # noqa: BLE001 -- telemetry must never break the caller
        current_app.logger.exception("Failed to persist operational_events row")
