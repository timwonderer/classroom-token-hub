"""Ticket-Log Correlation Pack (TLCP) helpers."""

from __future__ import annotations

import os
import random
import uuid
from datetime import timedelta

import sqlalchemy as sa
from flask import has_request_context, request, current_app

from app.extensions import db
from app.models import ActorRequestTrace, ClassEconomy, Seat
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now

CORRELATION_VERSION = 1
DEFAULT_TRACE_LIMIT = 20
DEFAULT_TRACE_TTL_DAYS = 7
# Bound on any lock wait in the independent after_request trace session. A
# trace is supplemental; a worker must never wait longer than this for one.
TRACE_LOCK_TIMEOUT = "2s"
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


def _sanitize_error_message(raw_message: str | None) -> str:
    if not raw_message:
        return ""
    compact = " ".join(str(raw_message).split())
    return compact[:500]


def _error_events_available(bind=None) -> bool:
    """Return True only when the ``error_events`` table physically exists.

    ``error_events`` was dropped by migration 7c3d4e5f6a7b (slated for
    absorption into operational_events, DOM-OPS-001, which is not yet built).
    Both the writer (app/__init__.py) and these readers must guard on the
    table's presence so the correlation surface degrades to "no errors"
    instead of raising when the table is absent. It must NEVER be confused
    with the tamper-evident ``audit_events`` chain, whose schema differs.
    """
    try:
        bind = bind if bind is not None else db.session.get_bind()
        return sa.inspect(bind).has_table("error_events")
    except Exception:
        return False


def _error_event_rows(sql: str, params: dict) -> list:
    """Run a guarded read against ``error_events``; [] when the table is absent."""
    if not _error_events_available():
        return []
    result = db.session.execute(sa.text(sql), params)
    return [dict(row) for row in result.mappings()]


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


def _log_invariant_violation(
    message: str,
    *,
    context: CanonicalContext | None = None,
    actor_type: str | None = None,
    class_id: str | None = None,
) -> None:
    extra = {
        "actor_type": "-",
        "actor_public_id": "-",
        "class_id": "-",
        "error_class": "InvariantViolation",
        "correlation_version": CORRELATION_VERSION,
    }
    if context is not None:
        extra.update(
            actor_type=context.actor_role,
            class_id=context.class_id,
        )
    if actor_type:
        extra["actor_type"] = actor_type
    if class_id:
        extra["class_id"] = class_id
    current_app.logger.error(f"TLCP-INVARIANT-VIOLATION: {message}", extra=extra)


# -------------------- SURFACE AND PRINCIPAL --------------------
#
# A request answers two questions that must not be conflated (INV-ARC-019 §V:
# "No identifier answers more than its assigned question"; §XIII: the
# authenticated principal and the active classroom context remain separate):
#
#   surface   -- what was requested. Read from the URL's endpoint.
#   principal -- who authenticated. Read from ``users.user_role`` of the
#                principal the session names, with or without class context.
#
# Until 2026-10-02 TLCP named a request a "sysadmin request" by its endpoint
# alone, and logged any class context on such a request as an invariant
# violation. A student whose Chromebook followed the landing page's operator
# sign-in link to /sysadmin/login therefore logged eight ERROR lines although
# no sysadmin principal existed. The invariant concerns the principal: a
# system administrator holds no class context (INV-CORE-000 §III.4; SPEC-OPS-004
# §V), and that holds on every surface.

SURFACE_APPLICATION = "application"
# Sysadmin endpoints that admit a caller with no sysadmin session: sign-in,
# sign-out, passkey sign-in, and the nginx auth check.
SURFACE_SYSADMIN_AUTHENTICATION = "sysadmin_authentication"
# Sysadmin endpoints admitted only by ``system_admin_required``.
SURFACE_SYSADMIN_CONSOLE = "sysadmin_console"
SYSADMIN_SURFACES = frozenset({SURFACE_SYSADMIN_AUTHENTICATION, SURFACE_SYSADMIN_CONSOLE})

PRINCIPAL_ANONYMOUS = "anonymous"
PRINCIPAL_STUDENT = "student"
PRINCIPAL_TEACHER = "teacher"
PRINCIPAL_SYSADMIN = "sysadmin"

VERDICT_INVARIANT_VIOLATION = "invariant_violation"
VERDICT_SURFACE_PRINCIPAL_MISMATCH = "surface_principal_mismatch"

SURFACE_PRINCIPAL_MISMATCH_TOKEN = "TLCP-SURFACE-PRINCIPAL-MISMATCH"

# The closed outcome vocabulary of SPEC-OPS-003 §VI. No TLCP-local labels:
# SUCCESS            -- the route completed its operation;
# EXPECTED_DENIAL    -- the route deliberately rejected the request under an
#                       authorization or validation rule;
# SYSTEM_FAILURE     -- the route could not complete (an unhandled failure).
OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_EXPECTED_DENIAL = "EXPECTED_DENIAL"
OUTCOME_SYSTEM_FAILURE = "SYSTEM_FAILURE"

# Endpoints whose operation is to make the caller a sysadmin principal: they
# complete only when the session names a sysadmin afterwards.
_SIGN_IN_ENDPOINTS = frozenset({"sysadmin.login", "sysadmin.passkey_auth_finish"})
# Endpoints that complete for any caller. ``GET /sysadmin/logout`` clears the
# session's principal whoever holds it (a tracked follow-up, unchanged here),
# so for a student or teacher it is a completed operation, not a denial.
_COMPLETES_FOR_ANY_PRINCIPAL = frozenset({"sysadmin.logout"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def classify_surface(blueprint: str | None, view_function) -> str:
    """Name the surface a request asked for. Pure; reads no request state."""
    if blueprint != "sysadmin":
        return SURFACE_APPLICATION
    if getattr(view_function, "admits_only_system_admin", False):
        return SURFACE_SYSADMIN_CONSOLE
    return SURFACE_SYSADMIN_AUTHENTICATION


def classify_request(*, surface: str, principal: str, class_context_present: bool) -> str | None:
    """Classify one request from both dimensions. Pure.

    sysadmin principal + class context, any surface -> invariant violation
    student/teacher principal on a sysadmin surface -> surface/principal mismatch
    anything else                                    -> nothing to record
    """
    if principal == PRINCIPAL_SYSADMIN and class_context_present:
        return VERDICT_INVARIANT_VIOLATION
    if surface in SYSADMIN_SURFACES and principal in (PRINCIPAL_STUDENT, PRINCIPAL_TEACHER):
        return VERDICT_SURFACE_PRINCIPAL_MISMATCH
    return None


def classify_outcome(
    *,
    surface: str,
    endpoint: str | None,
    method: str,
    status_code: int | None,
    principal_after: str,
) -> str:
    """Classify a non-sysadmin principal's sysadmin-surface request. Pure.

    Uses the SPEC-OPS-003 §VI vocabulary, read after the view ran, per the
    contract of the route that owns the outcome (§VII):

    - an unhandled failure (the app's 5xx error handler)    -> SYSTEM_FAILURE
    - ``sysadmin.logout``: completes for any principal       -> SUCCESS
    - password or passkey sign-in: the session now names a
      sysadmin                                               -> SUCCESS
      ...a GET/HEAD/OPTIONS that only rendered the form      -> SUCCESS
      ...a submission that left no sysadmin principal        -> EXPECTED_DENIAL
    - other sign-in endpoints (passkey start, the Grafana
      auth check) answer a refusal with their own 4xx        -> EXPECTED_DENIAL
      and otherwise complete                                 -> SUCCESS
    - the console admits only a sysadmin, so a student or
      teacher is refused admission                           -> EXPECTED_DENIAL
    """
    if status_code is not None and status_code >= 500:
        return OUTCOME_SYSTEM_FAILURE
    if endpoint in _COMPLETES_FOR_ANY_PRINCIPAL:
        return OUTCOME_SUCCESS
    if principal_after == PRINCIPAL_SYSADMIN:
        return OUTCOME_SUCCESS
    if surface == SURFACE_SYSADMIN_CONSOLE:
        return OUTCOME_EXPECTED_DENIAL
    if endpoint in _SIGN_IN_ENDPOINTS:
        if (method or "").upper() in _SAFE_METHODS:
            return OUTCOME_SUCCESS
        return OUTCOME_EXPECTED_DENIAL
    if status_code is not None and 400 <= status_code < 500:
        return OUTCOME_EXPECTED_DENIAL
    return OUTCOME_SUCCESS


def _principal_user(context):
    """The ``User`` the request authenticated as, or None.

    A ``CanonicalContext`` carries the authenticated ``users.id`` (DOM-IDEN-006
    §VII). Without one -- signed out, a sysadmin (who is refused class context),
    or a context that failed to resolve -- the principal is the one the session
    names, as ``resolve_canonical_context`` reads it.
    """
    from flask import session

    from app.models import User
    from app.utils.user_ids import parse_user_id, session_user_id

    if isinstance(context, CanonicalContext):
        user_id = parse_user_id(context.user_id)
    else:
        user_id = session_user_id(session)
    if user_id is None:
        return None
    return db.session.get(User, user_id)


def _principal_role(user) -> str:
    if user is None:
        return PRINCIPAL_ANONYMOUS
    role = getattr(user.user_role, "value", user.user_role)
    if role in (PRINCIPAL_STUDENT, PRINCIPAL_TEACHER, PRINCIPAL_SYSADMIN):
        return role
    return PRINCIPAL_ANONYMOUS


def _carried_class_context(context, user) -> tuple[bool, str | None]:
    """Whether this request carries class context, and the class id if known.

    Any carrier counts: a resolved ``CanonicalContext``; the ``class_id`` the
    session holds; or the principal's persisted ``last_active_class_id`` /
    ``last_active_seat_id``, from which canonical context is resolved
    (DOM-IDEN-006 §VIII). For a sysadmin the resolver refuses class context
    outright, so only the raw carriers can show that one is attached.
    """
    from flask import session

    if isinstance(context, CanonicalContext):
        return True, context.class_id
    session_class_id = session.get("class_id")
    if session_class_id:
        return True, str(session_class_id)
    if user is not None:
        if getattr(user, "last_active_class_id", None):
            return True, str(user.last_active_class_id)
        if getattr(user, "last_active_seat_id", None):
            return True, None
    return False, None


def observe_request(context) -> dict | None:
    """Record both dimensions of the current request, once, at the boundary."""
    if not has_request_context():
        return None
    view_function = current_app.view_functions.get(request.endpoint) if request.endpoint else None
    surface = classify_surface(request.blueprint, view_function)
    user = _principal_user(context)
    principal = _principal_role(user)
    class_context_present, class_id = _carried_class_context(context, user)
    return {
        "surface": surface,
        "principal": principal,
        "class_context_present": class_context_present,
        "class_id": class_id,
        "endpoint": request.endpoint,
        "method": request.method,
        "verdict": classify_request(
            surface=surface,
            principal=principal,
            class_context_present=class_context_present,
        ),
    }


def record_surface_principal_mismatch(observation: dict | None, status_code: int | None = None) -> None:
    """Log a non-sysadmin principal's request to a sysadmin surface, at INFO.

    Called after the response, so the outcome is read rather than guessed. It
    is not a violation: the sysadmin surface is reachable by anyone, and
    admission there keys off the principal (``system_admin_required``). A
    refused sign-in is an ``EXPECTED_DENIAL``, which is evidence that the rule
    was enforced (SPEC-OPS-003 §VI), so it is recorded at INFO, not WARNING or
    ERROR. ``principal_after`` shows a sign-in that changed who the session
    names. No username or name is recorded; the actor fields carry the seat's
    ``public_id`` and ``class_id`` as every TLCP line does.
    """
    if not observation or observation.get("verdict") != VERDICT_SURFACE_PRINCIPAL_MISMATCH:
        return
    principal_after = _principal_role(_principal_user(None))
    outcome = classify_outcome(
        surface=observation["surface"],
        endpoint=observation.get("endpoint"),
        method=observation["method"],
        status_code=status_code,
        principal_after=principal_after,
    )
    fields = {
        "tlcp_surface": observation["surface"],
        "tlcp_principal": observation["principal"],
        "tlcp_class_context": "present" if observation["class_context_present"] else "absent",
        "tlcp_outcome": outcome,
        "tlcp_principal_after": principal_after,
    }
    current_app.logger.info(
        "%s: surface=%s principal=%s class_context=%s outcome=%s principal_after=%s method=%s",
        SURFACE_PRINCIPAL_MISMATCH_TOKEN,
        fields["tlcp_surface"],
        fields["tlcp_principal"],
        fields["tlcp_class_context"],
        fields["tlcp_outcome"],
        fields["tlcp_principal_after"],
        observation["method"],
        extra=fields,
    )


def resolve_actor_context(context: CanonicalContext | None, *, observation: dict | None = None) -> dict | None:
    """Convert canonical request context into correlation logging fields.

    TLCP correlates requests; it does not decide authority. It runs in
    ``before_request``, before any route has admitted the request, so it
    cannot know whether a route needs class context at all. Admission does:
    ``login_required``, ``admin_required`` and ``system_admin_required`` fail
    closed when the context a route needs is missing, and
    ``resolve_canonical_context`` logs each contradiction it finds in a
    signed-in session (a seat pointer in another class, a missing seat, a
    missing class) at WARNING.

    So an absent context is simply a request with no actor to correlate --
    a health probe, a sign-in page, a sysadmin page, an unmatched URL, a
    capability-token page -- and records nothing. Until 2026-09-27 this branch
    logged ``TLCP-INVARIANT-VIOLATION: missing canonical context`` for any
    such request whose endpoint was missing from two hand-kept allowlists:
    345 ERROR lines in the first five production hours, every one a signed-out
    request, and none of them a violation.

    Only a context that is present and contradictory is a violation here:

        Sysadmin principal + class context,     -> invariant violation, no trace
          on any surface                           (INV-CORE-000 §III.4; see
                                                   classify_request)
        Context present, seat exists            -> correlate
        Context present, seat missing           -> invariant violation, no trace
        Context absent                          -> nothing to correlate

    A student or teacher on a sysadmin surface is not a violation: the URL
    names what was requested, not who requested it (INV-ARC-019 §V, §XIII).
    It is correlated as usual and recorded once, after the response, as
    ``TLCP-SURFACE-PRINCIPAL-MISMATCH`` (``record_surface_principal_mismatch``).
    """
    if not has_request_context():
        return None

    if observation is None:
        observation = observe_request(context)

    if observation and observation["verdict"] == VERDICT_INVARIANT_VIOLATION:
        _log_invariant_violation(
            "sysadmin principal carries canonical class context "
            f"(surface={observation['surface']})",
            actor_type=PRINCIPAL_SYSADMIN,
            class_id=observation["class_id"],
        )
        return None

    if context is None:
        return None

    seat = db.session.get(Seat, context.seat_id)
    if not seat:
        _log_invariant_violation("missing canonical seat", context=context)
        return None

    actor_type = seat.role
    class_id = context.class_id
    actor_public_id = seat.public_id

    endpoint = request.url_rule.rule if request.url_rule and request.url_rule.rule else request.path
    return {
        "actor_type": actor_type,
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
    if not context or not context.get("actor_public_id") or not context.get("class_id"):
        return

    sess = _session if _session is not None else db.session
    # after_request may run after this request destroyed its own class/seat.
    # Never recreate a trace from the pre-deletion cached request context.
    # Share-lock the seat so a concurrent seat deletion cannot miss this trace.
    # This writer runs in its own session after the response; a seat that is
    # locked for deletion or update is skipped rather than waited on, since a
    # trace is supplemental diagnostics (DOM-SUP-001 §X).
    #
    # The trace's class_id foreign key takes FOR KEY SHARE on the class row at
    # INSERT. Take it here first, skip-locked, in the class-then-seat order every
    # class-scoped command uses, so the FK check reuses it and never waits. When
    # the class row is held FOR UPDATE (destruction, unclaim, or this request's
    # own still-open transaction, as in OPS-DB-001) the trace is skipped.
    class_exists = sess.query(ClassEconomy.class_id).filter_by(
        class_id=context["class_id"],
    ).with_for_update(read=True, key_share=True, skip_locked=True).first()
    if class_exists is None:
        return
    actor_exists = sess.query(Seat.id).filter_by(
        public_id=context["actor_public_id"], class_id=context["class_id"],
        role=context.get("actor_type"),
    ).with_for_update(read=True, skip_locked=True).first()
    if actor_exists is None:
        return

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

        # Prune the correlation error log (NOT the tamper-evident audit_events
        # chain). Guarded because error_events may be absent (see
        # _error_events_available); a missing table must be a no-op.
        if _error_events_available(sess.get_bind()):
            sess.execute(
                sa.text("DELETE FROM error_events WHERE created_at < :cutoff"),
                {"cutoff": ttl_cutoff},
            )


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
    """Persist a short-lived error event for ticket correlation.

    Writes to the ``error_events`` correlation log via guarded raw SQL so the
    schema stays decoupled from any ORM model and the call degrades to a no-op
    when the table is absent (see _error_events_available). This is NOT the
    tamper-evident ``audit_events`` chain.
    """
    if not actor_type or not actor_public_id:
        return
    if not _error_events_available():
        return

    db.session.execute(
        sa.text(
            """
            INSERT INTO error_events
                (request_id, actor_type, actor_public_id, class_id,
                 endpoint, method, error_class, error_message,
                 correlation_version, created_at)
            VALUES
                (:request_id, :actor_type, :actor_public_id, :class_id,
                 :endpoint, :method, :error_class, :error_message,
                 :correlation_version, :created_at)
            """
        ),
        {
            "request_id": request_id,
            "actor_type": actor_type,
            "actor_public_id": actor_public_id,
            "class_id": class_id,
            "endpoint": endpoint,
            "method": method,
            "error_class": error_class,
            "error_message": _sanitize_error_message(error_message),
            "correlation_version": CORRELATION_VERSION,
            "created_at": utc_now(),
        },
    )


def has_recent_error_for_actor(
    actor_type: str,
    actor_public_id: str,
    recent_minutes: int | None = None,
) -> bool:
    """Return True when the actor has a recent error event.

    Degrades to False when the ``error_events`` table is absent.
    """
    minutes = recent_minutes or _int_env("TLCP_RECENT_ERROR_MINUTES", DEFAULT_RECENT_ERROR_MINUTES)
    cutoff = utc_now() - timedelta(minutes=minutes)
    rows = _error_event_rows(
        """
        SELECT id FROM error_events
        WHERE actor_type = :actor_type
          AND actor_public_id = :actor_public_id
          AND created_at >= :cutoff
        LIMIT 1
        """,
        {
            "actor_type": actor_type,
            "actor_public_id": actor_public_id,
            "cutoff": cutoff,
        },
    )
    return bool(rows)


def create_ticket_correlation_pack(
    *,
    issue_id: int,
    actor_type: str,
    actor_public_id: str,
    class_id: str | None,
    ticket_created_at,
    include_recent_error: bool = True,
) -> dict:
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
    error_rows = (
        _error_event_rows(
            """
            SELECT request_id, endpoint, method, error_class, error_message,
                   class_id, created_at
            FROM error_events
            WHERE actor_type = :actor_type
              AND actor_public_id = :actor_public_id
              AND created_at >= :window_start
              AND created_at <= :ticket_created_at
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """,
            {
                "actor_type": actor_type,
                "actor_public_id": actor_public_id,
                "window_start": error_window_start,
                "ticket_created_at": ticket_created_at,
                "limit": trace_limit,
            },
        )
        if include_recent_error
        else []
    )

    if include_recent_error and not error_rows:
        ttl_cutoff = ticket_created_at - timedelta(days=ttl_days)
        error_rows = _error_event_rows(
            """
            SELECT request_id, endpoint, method, error_class, error_message,
                   class_id, created_at
            FROM error_events
            WHERE actor_type = :actor_type
              AND actor_public_id = :actor_public_id
              AND created_at >= :ttl_cutoff
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            {
                "actor_type": actor_type,
                "actor_public_id": actor_public_id,
                "ttl_cutoff": ttl_cutoff,
            },
        )

    def _iso(value):
        return value.isoformat() if value is not None and hasattr(value, "isoformat") else value

    error_refs_json = [
        {
            "timestamp": _iso(row.get("created_at")),
            "endpoint": row.get("endpoint"),
            "request_id": row.get("request_id"),
            "error_class": row.get("error_class"),
            "error_message": row.get("error_message"),
            "method": row.get("method"),
            "class_id": row.get("class_id"),
        }
        for row in error_rows
    ]

    return {
        "issue_id": issue_id,
        "correlation_version": CORRELATION_VERSION,
        "actor_type": actor_type,
        "actor_public_id": actor_public_id,
        "class_id": class_id,
        "request_trace_json": request_trace_json,
        "error_refs_json": error_refs_json,
        "created_at": utc_now(),
    }
