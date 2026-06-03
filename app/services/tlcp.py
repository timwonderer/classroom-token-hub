"""Ticket-Log Correlation Pack (TLCP) helpers."""

from __future__ import annotations

import os
import random
import uuid
from datetime import timedelta

import sqlalchemy as sa
from flask import has_request_context, request, session

from app.auth import (
    get_current_admin,
    get_current_seat,
    get_current_system_admin,
    get_logged_in_student,
)
from app.extensions import db
from app.models import ActorRequestTrace, ErrorEvent, ClassEconomy, Seat, TicketCorrelationPack
from app.utils.time import utc_now

CORRELATION_VERSION = 1
DEFAULT_TRACE_LIMIT = 20
DEFAULT_TRACE_TTL_DAYS = 7
DEFAULT_ERROR_WINDOW_HOURS = 2
DEFAULT_RECENT_ERROR_MINUTES = 15
DEFAULT_TRACE_FETCH_MULTIPLIER = 4
TTL_CLEANUP_PROBABILITY = 0.01  # ~1% of requests trigger global TTL cleanup
DEFAULT_NOISE_ENDPOINT_PREFIXES = (
    "/static/",
    "/sw.js",
    "/favicon.ico",
    "/api/set-timezone",
)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _resolve_class_id(join_code: str | None) -> str | None:
    if not join_code:
        return None
    join_code = ClassEconomy.query.filter_by(join_code=join_code).first()
    return join_code.class_id if join_code else None


def _sanitize_error_message(raw_message: str | None) -> str:
    if not raw_message:
        return ""
    compact = " ".join(str(raw_message).split())
    return compact[:500]


def _teacher_seat_public_id(*, admin_id: int | None, class_id: str | None) -> str | None:
    if not admin_id or not class_id:
        return None
    class_row = ClassEconomy.query.filter_by(class_id=class_id, teacher_id=admin_id).first()
    if not class_row:
        return None
    seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    return seat.public_id if seat else None


def _student_seat_public_id(*, student_id: int | None, class_id: str | None) -> str | None:
    if not student_id or not class_id:
        return None
    seat = Seat.query.filter_by(student_id=student_id, class_id=class_id).first()
    return seat.public_id if seat else None


def _noise_endpoint_prefixes() -> tuple[str, ...]:
    raw = os.getenv("TLCP_NOISE_ENDPOINT_PREFIXES")
    if not raw:
        return DEFAULT_NOISE_ENDPOINT_PREFIXES
    prefixes = tuple(part.strip() for part in raw.split(",") if part.strip())
    return prefixes or DEFAULT_NOISE_ENDPOINT_PREFIXES


def _is_noise_endpoint(endpoint: str | None) -> bool:
    if not endpoint:
        return True
    return any(endpoint.startswith(prefix) for prefix in _noise_endpoint_prefixes())


def resolve_actor_context() -> dict | None:
    """Resolve request actor context for correlation logging."""
    if not has_request_context():
        return None

    join_code = None
    class_id = None
    actor_public_id = None

    current_seat = get_current_seat()
    if current_seat and current_seat.student_id:
        actor_type = "student"
        actor_id = current_seat.student_id
        join_code = current_seat.join_code or session.get("current_join_code")
        class_id = current_seat.class_id or session.get("current_class_id") or _resolve_class_id(join_code)
        actor_public_id = current_seat.public_id
    elif (student := get_logged_in_student()) is not None:
        actor_type = "student"
        actor_id = student.id
        join_code = session.get("current_join_code")
        class_id = session.get("current_class_id") or _resolve_class_id(join_code) or student.class_id
        actor_public_id = _student_seat_public_id(student_id=actor_id, class_id=class_id)
    elif (admin := get_current_admin()) is not None:
        actor_type = "teacher"
        actor_id = admin.id
        join_code = session.get("current_join_code")
        class_id = session.get("current_class_id") or _resolve_class_id(join_code)
        actor_public_id = _teacher_seat_public_id(admin_id=actor_id, class_id=class_id)
    elif (sysadmin := get_current_system_admin()) is not None:
        actor_type = "sysadmin"
        actor_id = sysadmin.id
    else:
        return None

    endpoint = request.url_rule.rule if request.url_rule and request.url_rule.rule else request.path
    return {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_public_id": actor_public_id,
        "class_id": class_id,
        "endpoint": endpoint,
        "method": request.method,
    }


def persist_request_trace(
    context: dict | None,
    request_id: str | None,
    status_code: int | None,
    *,
    _session=None,
) -> None:
    """Persist request trace rows with bounded retention.

    Pass ``_session`` to use an isolated SQLAlchemy session instead of the
    default request-scoped ``db.session``.  The caller is responsible for
    committing (or rolling back) the provided session.
    """
    if not context or not context.get("actor_public_id"):
        return

    sess = _session if _session is not None else db.session

    trace_limit = _int_env("TLCP_TRACE_LIMIT", DEFAULT_TRACE_LIMIT)
    ttl_days = _int_env("TLCP_TRACE_TTL_DAYS", DEFAULT_TRACE_TTL_DAYS)
    now = utc_now()
    ttl_cutoff = now - timedelta(days=ttl_days)

    request_id = request_id or uuid.uuid4().hex

    trace = ActorRequestTrace(
        actor_type=context.get("actor_type"),
        actor_public_id=context.get("actor_public_id"),
        class_id=context.get("class_id"),
        request_id=request_id,
        method=context.get("method"),
        endpoint=context.get("endpoint"),
        status_code=status_code,
        created_at=now,
    )
    sess.add(trace)
    sess.flush()

    ids_to_keep = (
        sess.query(ActorRequestTrace.id)
        .filter(
            ActorRequestTrace.actor_type == context.get("actor_type"),
            ActorRequestTrace.actor_public_id == context.get("actor_public_id"),
        )
        .order_by(ActorRequestTrace.created_at.desc(), ActorRequestTrace.id.desc())
        .limit(trace_limit)
        .subquery()
    )

    sess.query(ActorRequestTrace).filter(
        ActorRequestTrace.actor_type == context.get("actor_type"),
        ActorRequestTrace.actor_public_id == context.get("actor_public_id"),
        ~ActorRequestTrace.id.in_(sa.select(ids_to_keep.c.id)),
    ).delete(synchronize_session=False)

    # Run global TTL cleanup probabilistically to avoid O(table) contention on every hot-path call.
    if random.random() < TTL_CLEANUP_PROBABILITY:
        sess.query(ActorRequestTrace).filter(
            ActorRequestTrace.created_at < ttl_cutoff
        ).delete(synchronize_session=False)

        sess.query(ErrorEvent).filter(
            ErrorEvent.created_at < ttl_cutoff
        ).delete(synchronize_session=False)


def save_error_event(
    *,
    request_id: str | None,
    actor_type: str | None,
    actor_public_id: str | None,
    class_id: str | None,
    endpoint: str | None,
    method: str | None,
    error_class: str,
    error_message: str | None,
) -> None:
    """Persist a short-lived error event for ticket correlation."""
    if not actor_type or not actor_public_id:
        return

    db.session.add(
        ErrorEvent(
            request_id=request_id,
            actor_type=actor_type,
            actor_public_id=actor_public_id,
            class_id=class_id,
            endpoint=endpoint,
            method=method,
            error_class=error_class,
            error_message=_sanitize_error_message(error_message),
            correlation_version=CORRELATION_VERSION,
            created_at=utc_now(),
        )
    )


def has_recent_error_for_actor(
    actor_type: str,
    actor_public_id: str,
    recent_minutes: int | None = None,
) -> bool:
    """Return True when the actor has a recent error event."""
    minutes = recent_minutes or _int_env("TLCP_RECENT_ERROR_MINUTES", DEFAULT_RECENT_ERROR_MINUTES)
    cutoff = utc_now() - timedelta(minutes=minutes)
    return (
        db.session.query(ErrorEvent.id)
        .filter(
            ErrorEvent.actor_type == actor_type,
            ErrorEvent.actor_public_id == actor_public_id,
            ErrorEvent.created_at >= cutoff,
        )
        .first()
        is not None
    )


def create_ticket_correlation_pack(
    *,
    issue_id: int,
    actor_type: str,
    actor_public_id: str,
    class_id: str | None,
    ticket_created_at,
    include_recent_error: bool = True,
) -> TicketCorrelationPack:
    """Create immutable correlation snapshot for a ticket."""
    trace_limit = _int_env("TLCP_TRACE_LIMIT", DEFAULT_TRACE_LIMIT)
    ttl_days = _int_env("TLCP_TRACE_TTL_DAYS", DEFAULT_TRACE_TTL_DAYS)
    error_window_hours = _int_env("TLCP_ERROR_WINDOW_HOURS", DEFAULT_ERROR_WINDOW_HOURS)

    fetch_limit = trace_limit * _int_env("TLCP_TRACE_FETCH_MULTIPLIER", DEFAULT_TRACE_FETCH_MULTIPLIER)
    trace_rows = (
        ActorRequestTrace.query.filter_by(
            actor_type=actor_type,
            actor_public_id=actor_public_id,
        )
        .order_by(ActorRequestTrace.created_at.desc(), ActorRequestTrace.id.desc())
        .limit(fetch_limit)
        .all()
    )

    prioritized = [row for row in trace_rows if not _is_noise_endpoint(row.endpoint)]
    noisy = [row for row in trace_rows if _is_noise_endpoint(row.endpoint)]
    ranked_rows = (prioritized + noisy)[:trace_limit]

    request_trace_json = [
        {
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "method": row.method,
            "endpoint": row.endpoint,
            "request_id": row.request_id,
            "status_code": row.status_code,
            "class_id": row.class_id,
        }
        for row in ranked_rows
    ]

    error_window_start = ticket_created_at - timedelta(hours=error_window_hours)
    errors_query = (
        ErrorEvent.query.filter(
            ErrorEvent.actor_type == actor_type,
            ErrorEvent.actor_public_id == actor_public_id,
            ErrorEvent.created_at >= error_window_start,
            ErrorEvent.created_at <= ticket_created_at,
        )
        .order_by(ErrorEvent.created_at.desc(), ErrorEvent.id.desc())
    )
    error_rows = errors_query.limit(trace_limit).all() if include_recent_error else []

    if include_recent_error and not error_rows:
        ttl_cutoff = ticket_created_at - timedelta(days=ttl_days)
        latest_error = (
            ErrorEvent.query.filter(
                ErrorEvent.actor_type == actor_type,
                ErrorEvent.actor_public_id == actor_public_id,
                ErrorEvent.created_at >= ttl_cutoff,
            )
            .order_by(ErrorEvent.created_at.desc(), ErrorEvent.id.desc())
            .first()
        )
        if latest_error:
            error_rows = [latest_error]

    error_refs_json = [
        {
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "endpoint": row.endpoint,
            "request_id": row.request_id,
            "error_class": row.error_class,
            "error_message": row.error_message,
            "method": row.method,
            "class_id": row.class_id,
        }
        for row in error_rows
    ]

    pack = TicketCorrelationPack(
        issue_id=issue_id,
        correlation_version=CORRELATION_VERSION,
        actor_type=actor_type,
        actor_public_id=actor_public_id,
        class_id=class_id,
        request_trace_json=request_trace_json,
        error_refs_json=error_refs_json,
        created_at=utc_now(),
    )
    db.session.add(pack)
    return pack
